import os
import sys
from pathlib import Path

# Add backend to sys.path
_backend_root = Path(__file__).resolve().parents[3]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

try:
    import dx_lab_env
    dx_lab_env.load_shared_dotenv()
except Exception as e:
    print(f"Error loading dotenv: {e}")

# Add discovery_agent root to sys.path
_agent_root = Path(__file__).resolve().parent
if str(_agent_root) not in sys.path:
    sys.path.insert(0, str(_agent_root))

from DiscoveryAgent.tools import retrieval as R

protein = "KRAS"
disease = "colorectal cancer"

print(f"Testing extraction for {protein} + {disease}")

print("1. UniProt lookup...")
ids = R.get_uniprot_ids.invoke({"protein_name": protein.strip()})
print(f"IDs: {ids}")

if isinstance(ids, str) or not ids:
    print("UniProt lookup failed")
    sys.exit(1)

uniprot_id = ids[0][0]

print(f"2. Fetching FASTA for {uniprot_id}...")
fasta_raw = R.fetch_uniprot_fasta.invoke({"uniprot_id": uniprot_id})
print(f"Fasta length: {len(str(fasta_raw)) if fasta_raw else 0}")

print("3. Serper search for seed drugs...")
try:
    # Use the same logic as mcp_agent.py
    query = f"FDA approved drug targeting {protein} {disease}"
    print(f"Query: {query}")
    blob = R.search.invoke({"query": query})
    print(f"Search result (first 100 chars): {str(blob)[:100]}")
except Exception as e:
    print(f"Search failed: {e}")

print("4. ChEMBL SMILES resolution...")
# Test with a known candidate if search fails or for testing
candidates = ["Sotorasib", "Adagrasib"]
for name in candidates:
    print(f"Fetching SMILES for {name}...")
    smi = R.get_drug_smiles.invoke({"drug_name": name})
    print(f"SMILES: {smi}")

print("Extraction logic test completed.")
