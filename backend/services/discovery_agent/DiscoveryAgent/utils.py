from langchain.memory import ConversationBufferMemory
from langchain.chains import RetrievalQA
from openai import OpenAIError
from rdkit import Chem
import requests
import os
import ast
import importlib.util
import json
import re
import pandas as pd

# from dZiner paper
def RetrievalQABypassTokenLimit(vector_store, RetrievalQA_prompt, llm, k=10, fetch_k=50, min_k=2, chain_type="stuff"):
    while k >= min_k:
        try:
            retriever = vector_store.as_retriever(
                search_type="mmr",
                search_kwargs={"k": k, "fetch_k": fetch_k},
            )
            qa_chain = RetrievalQA.from_chain_type( 
                llm=llm,
                chain_type=chain_type,
                retriever=retriever,
                memory=ConversationBufferMemory(
                        ))
            
            # Check to see if we hit the token limit
            result = qa_chain.run({"query": RetrievalQA_prompt})
            return result  # If successful, return the result and exit the function

        except OpenAIError as e:
            # Check if it's a token limit error
            print(e)
            if 'maximum context length' in str(e):
                print(f"\nk={k} results hitting the token limit. Reducing k and retrying...\n")
                k -= 1
            else:
                # Re-raise other OpenAI errors
                raise e
            

def download_pdf(url: str, title: str, paper_dir: str):
    """
    Downloads a PDF from a given URL and saves it with a sanitized title.

    **Args:**
        url (str): The URL of the PDF.
        title (str): The title of the paper.

    **Returns:**
        str: The file path of the downloaded PDF.
    """
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            # Sanitize filename
            filename = "".join(c if c.isalnum() else "_" for c in title)[:100] + ".pdf"
            # create PAPER_DIR if it doesn't exist
            if not os.path.exists(paper_dir):
                os.makedirs(paper_dir)
            file_path = os.path.join(paper_dir, filename)

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)

            return file_path
        else:
            print(f"Failed to download: {title} ({url})")
            return None
    except Exception as e:
        print(f"Error downloading {title}: {str(e)}")
        return None
    

def get_tool_decorated_functions(filepath):
    """
    Parse a Python file, find all functions decorated with @tool,
    dynamically import the module, and return the function objects.

    Args:
        filepath (str): Path to the Python file to analyze.

    Returns:
        list: List of function objects decorated with @tool.
    """
    # Step 1: Parse the AST and find decorated functions
    with open(filepath, "r", encoding="utf-8") as f:
        node = ast.parse(f.read(), filename=filepath)

    decorated_func_names = []
    for n in ast.walk(node):
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if isinstance(d, ast.Name) and d.id == "tool":
                    decorated_func_names.append(n.name)
                elif isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool":
                    decorated_func_names.append(n.name)

    # Step 2: Import the module dynamically
    module_name = os.path.splitext(os.path.basename(filepath))[0]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Step 3: Extract function objects
    tools = [getattr(module, name) for name in decorated_func_names]

    return tools


def custom_serializer(obj):
    """
    Custom serializer for objects that are not JSON serializable.
    Converts the object to string, or returns a placeholder for non-serializable objects.

    Args:
        obj: Any Python object.

    Returns:
        str: String representation of the object or a placeholder.
    """
    try:
        return str(obj)
    except:
        return f"<<Non-serializable: {type(obj).__name__}>>"
    

_JSON_BLOCK_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _parse_refinement_output(raw: str, *, original_smiles: str) -> dict:
    """Parse the refinement agent's output into Updated_SMILES/Property/Rationale.

    Priority:
    1. A JSON object with keys ``updated_smiles`` / ``property`` / ``rationale``.
    2. Legacy ``</s>``-separated triple, kept for backward compatibility.
    3. Fallback that keeps the original SMILES and records the failure in
       ``refinement_failed``.
    """
    if raw is None:
        return {
            "Updated_SMILES": original_smiles,
            "Property": "",
            "Rationale": "No response from refinement agent.",
            "refinement_failed": True,
        }

    text = str(raw).strip()

    for match in _JSON_BLOCK_RE.finditer(text):
        candidate = match.group(0)
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        keys = {k.lower(): k for k in obj.keys()}
        if "updated_smiles" in keys:
            return {
                "Updated_SMILES": str(obj[keys["updated_smiles"]]).strip(),
                "Property": str(obj.get(keys.get("property", "property"), "")).strip(),
                "Rationale": str(obj.get(keys.get("rationale", "rationale"), "")).strip(),
                "refinement_failed": False,
            }

    if "</s>" in text:
        parts = [p.strip() for p in text.split("</s>")]
        if len(parts) >= 3:
            return {
                "Updated_SMILES": parts[0],
                "Property": parts[1],
                "Rationale": "</s>".join(parts[2:]).strip(),
                "refinement_failed": False,
            }

    return {
        "Updated_SMILES": original_smiles,
        "Property": "",
        "Rationale": f"Could not parse refinement output; kept original SMILES. Raw: {text[:200]}",
        "refinement_failed": True,
    }


def process_dataset_with_agent(file_path: str, protein: str, tools: list, agent) -> pd.DataFrame:
    """Run LLM-driven refinement over each row of a property CSV.

    The agent is expected to return a JSON object
    ``{"updated_smiles": ..., "property": ..., "rationale": ...}``. The parser
    also accepts the legacy ``</s>``-separated format. When parsing fails the
    **original SMILES is preserved** and ``refinement_failed`` is set to
    ``True`` so the row is never silently dropped.
    """
    df = pd.read_csv(file_path)
    results = []

    tool_names = [t.name for t in tools]
    tool_desc = [t.description for t in tools]

    for _, row in df.iterrows():
        entry = row.to_dict()
        keys_to_remove = [k for k in entry.keys() if "Probability" in k or "Interpretation" in k]
        for k in keys_to_remove:
            entry.pop(k, None)

        smiles = row.get("SMILES")
        prompt = (
            f"Propose a modified version of the given SMILES that addresses its weakness as a drug candidate. "
            f"Consider that the given molecule is targeting {protein}. "
            f"The molecule's properties are: {entry}."
        )

        input_data = {
            "input": prompt,
            "tools": tools,
            "tool_names": tool_names,
            "tool_desc": tool_desc,
        }

        try:
            response = agent.invoke(input_data)
            raw = response.get("output", "") if isinstance(response, dict) else str(response)
            parsed = _parse_refinement_output(raw, original_smiles=str(smiles))
        except Exception as e:
            parsed = {
                "Updated_SMILES": str(smiles) if smiles is not None else "",
                "Property": "",
                "Rationale": f"Agent error: {e}",
                "refinement_failed": True,
            }

        results.append({"SMILES": smiles, **parsed})

    return pd.DataFrame(results)

