import os
import sys
import asyncio
from pathlib import Path

# Add backend to sys.path
_backend_root = Path(__file__).resolve().parents[2]
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

from mcp_agent import discovery_agent_run_pipeline

async def main():
    protein = "KRAS"
    disease = "colorectal cancer"
    run_id = "direct_test_run"
    
    print(f"Running pipeline directly for {protein} + {disease}")
    
    result = discovery_agent_run_pipeline(
        protein=protein,
        disease=disease,
        run_id=run_id,
        iterations=1,  # Fast test
        num_smiles=2,   # Fast test
        model="meta/llama-3.1-70b-instruct"
    )
    
    print("\nPipeline Result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
