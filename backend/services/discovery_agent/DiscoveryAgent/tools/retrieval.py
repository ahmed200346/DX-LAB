# Built-in and standard library
import os
import re
import time
import json
import requests
from collections import defaultdict

# Third-party libraries (LangChain, ChEMBL)
from langchain.tools import tool
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from DiscoveryAgent.llm import chat_llm, embeddings_client
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.vectorstores import FAISS
from chembl_webresource_client.new_client import new_client
# Local utilities
from DiscoveryAgent.utils import download_pdf, RetrievalQABypassTokenLimit
from configs.tool_globals import UNIPROT_NUM_IDS, MAX_PAPERS, PAPER_DIR
# breakpoint()
# UNIPROT_NUM_IDS = 1
# MAX_PAPERS = 10 # Number of papers to download for molecule optimization guideline
# PAPER_DIR = "papers"  # Directory to store downloaded papers
# EMBEDDING_MODEL = 'text-embedding-3-large' 

@tool
def search(query):
    '''
    This tool performs a search on Google using SerpAPI and returns relevant information for the query.
    It is particularly used for identifying existing drug molecules associated with a specific target protein.
    '''
    search = GoogleSerperAPIWrapper(engine='google', serpapi_api_key=os.getenv("SERPER_API_KEY"))
    results = search.run(query)
    return results

@tool
def get_uniprot_ids(protein_name: str):
# def get_uniprot_info(protein_name: str):
    """
    Searches for UniProt IDs based on a given protein name and returns the IDs.
    Strictly pass the protein name itself, like "TP53" or "EGFR".
    """
    import requests

    base_url = "https://rest.uniprot.org/uniprotkb/search"
    sym = protein_name.strip()
    # Plain text search ("KRAS AND organism_id:9606") ranks unrelated hits first (e.g. MAPKAP1).
    # Prefer Swiss-Prot gene matches, then broader reviewed search, then legacy query.
    query_candidates = [
        f"(gene:{sym}) AND organism_id:9606 AND reviewed:true",
        f"{sym} AND organism_id:9606 AND reviewed:true",
        f"{sym} AND organism_id:9606",
    ]
    # Gene field does not tolerate spaces; split "BCL-2" style tokens for a second gene attempt.
    if " " in sym or "-" in sym:
        compact = re.sub(r"[\s\-]+", "", sym)
        if compact != sym and re.match(r"^[A-Za-z0-9]+$", compact):
            query_candidates.insert(1, f"(gene:{compact}) AND organism_id:9606 AND reviewed:true")

    try:
        for query in query_candidates:
            params = {
                "query": query,
                "format": "json",
                "size": UNIPROT_NUM_IDS,
            }
            response = requests.get(base_url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            if "results" in data and len(data["results"]) > 0:
                return [
                    (d["primaryAccession"], d["proteinDescription"]["recommendedName"]["fullName"]["value"])
                    for d in data["results"]
                    if "primaryAccession" in d
                ]

        return f"No UniProt IDs found for '{protein_name}'."

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    
@tool
def fetch_uniprot_fasta(uniprot_id):
    """
    Fetch the FASTA sequence using the UniProt ID.
    """
    fasta_url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
    response = requests.get(fasta_url, timeout=60)
    
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch FASTA for {uniprot_id}. Status Code: {response.status_code}")
        return None


@tool
def save_results(input_str: str) -> str:
    """
    Save content to a file. Input should be a valid JSON string.
    """
    
    try:
        input_str = input_str.strip()
        if '\n' in input_str:  # Check if the input string contains newlines
            input_str - input_str.replace('\n', '')
        data = json.loads(input_str)
        filename = "extraction.json" #data["save_name"]+".json"
  
        with open(filename, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4))
        return f"Saved to {filename}"

    except json.JSONDecodeError:
        # Fallback: save raw input as text
        fallback_filename = "extraction.txt"
        with open(fallback_filename, "w", encoding="utf-8") as f:
            f.write(input_str)
        return f"Saved raw input to {fallback_filename}"
    
    except Exception as e:
        return f"Failed to write file: {e}"


@tool
def get_drug_smiles(drug_name: str):
    """
    Fetch the drug molecule SMILES of a given drug name from ChEMBL.

    The returned SMILES is salt-stripped and canonicalized with RDKit so that
    downstream pooling, prediction, and Boltz stages always see a single
    organic fragment. Returns ``None`` if ChEMBL has no hit or the structure
    cannot be parsed after standardization.
    """
    from DiscoveryAgent.chem import standardize  # type: ignore

    molecule = new_client.molecule
    mols = molecule.filter(pref_name__iexact=drug_name)

    matching_mols = defaultdict(list)

    for mol in mols:
        if 'molecule_structures' in mol and mol['molecule_structures']:
            matching_mols[mol['molecule_chembl_id']].append(mol['molecule_structures']['canonical_smiles'])

    if not matching_mols:
        print(f"No SMILES found for {drug_name}.")
        return None

    anchor_chembl_id = list(matching_mols.keys())[0]
    anchor_smiles = matching_mols[anchor_chembl_id][0]

    canonical = standardize(anchor_smiles)
    if canonical is None:
        print(f"ChEMBL returned an unparseable SMILES for {drug_name}: {anchor_smiles!r}.")
        return None

    return canonical




@tool
def question_answering(query: str):
    '''
    This tool performs question and answering using the downloaded research papers through a Retrieval-Augmented Generation (RAG) approach.
    It constructs a vector storage of all document embeddings and then performs retrieval and response generation using the provided query.
    '''
    # check if the files exist in the directory
    if not os.path.exists(PAPER_DIR):
        return "No papers found in the directory. Use generic design guidelines instead."

    documents = []
    # Iterate over the downloaded papers
    for paper_file in os.listdir(PAPER_DIR):
        # Check if the file is a PDF
        if not paper_file.endswith('.pdf'):
            continue

        # Construct the full file path
        paper_file_path = os.path.join(PAPER_DIR, paper_file)
        try:
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
            pages = PyPDFLoader(paper_file_path).load_and_split()
            sliced_pages = text_splitter.split_documents(pages)
            documents.extend(sliced_pages)
        except Exception as e:
            print(f"Error processing {paper_file_path}: {e}")
            continue

    # Construct VectorStore only once
    try:
        if documents:
            faiss_vectorstore = FAISS.from_documents(documents, embeddings_client())
            llm = chat_llm(temperature=0.3)
            response = RetrievalQABypassTokenLimit(faiss_vectorstore, query, llm)
            # Perform RAG for the query
            #response = retriever(query)
            return response
        else:
            return "No valid documents found to construct vector storage."
    except Exception as e:
        print(f"Error constructing vector store or during retrieval: {e}")
        return "Error in retrieval process."

@tool
def download_relevant_papers(query: str):
    """
    Searches for and downloads relevant academic papers related to a given research query.
    This function uses the Semantic Scholar API to search for papers and download them if they are open access.
    Query should be constructed in a way that it can be used to search for relevant papers.
    **Example Usage:**
        download_relevant_papers("drug molecule for <<target protein>>", year: "2023-")
        do not use year unless it is specified in instructions.
    """
    import re
    
    print(f"Searching for papers on: {query}")

    papers_downloaded = []
    print(f"Searching for papers on: {query}")

    # Parse year from query string (e.g., year: "2023-")
    year_match = re.search(r'year:\s*"([^"]+)"', query, re.IGNORECASE)
    if year_match:
        year = year_match.group(1)
    else:
        year = None

    # Step 1: Search Semantic Scholar
    SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
    headers = {"x-api-key": "P5pZs85BTC4MGCCNIQaDPaO2ktEIVZI08JKKBTox"}  # Replace with a valid API key

    # params = {
    #     "query": query,
    #     "fields": "title,url,abstract,isOpenAccess,openAccessPdf",
    #     "limit": MAX_PAPERS,
    #     "sort": "citationCount:desc"
    # }

    params = {
    "query": query,
    "fields": "title,url,abstract,isOpenAccess,openAccessPdf",
    "limit": MAX_PAPERS
    }

    # Only add year if parsed from query
    if year:
        params["year"] = year

    MAX_RETRIES = 3
    RETRY_WAIT = 5  # seconds

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                SEMANTIC_SCHOLAR_API, headers=headers, params=params, timeout=30
            )
            if response.status_code == 200:
                break

            print(
                f"Error fetching papers from Semantic Scholar. Status Code: {response.status_code}. "
                f"Attempt {attempt}/{MAX_RETRIES}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
        except requests.exceptions.RequestException as e:
            print(
                f"Error fetching papers from Semantic Scholar. Error: {e}. "
                f"Attempt {attempt}/{MAX_RETRIES}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)

    if response is not None and response.status_code == 200:
        try:
            results = response.json().get("data", [])
        except ValueError as e:
            print(f"Error parsing Semantic Scholar response JSON: {e}")
            return papers_downloaded

        for paper in results:
            title = paper.get("title", "Untitled")  # Default to 'Untitled' if title is missing
            open_access_pdf = paper.get("openAccessPdf")  # Get the dictionary (could be None)

            if isinstance(open_access_pdf, dict):  # Ensure it's a dictionary
                pdf_url = open_access_pdf.get("url")
                if pdf_url:
                    file_path = download_pdf(pdf_url, title, PAPER_DIR)
                    if file_path:
                        papers_downloaded.append(file_path)
                    time.sleep(2)
    else:
        print("Error fetching papers from Semantic Scholar after retries.")

    return papers_downloaded
