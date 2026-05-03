import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Add discovery_agent to path
DISCOVERY_AGENT_ROOT = BACKEND_ROOT / "services" / "discovery_agent"
if str(DISCOVERY_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(DISCOVERY_AGENT_ROOT))

# Mock environment
os.environ["DISCOVERY_AGENT_MOCK_MODELS"] = "1"
os.environ["DISCOVERY_AGENT_FORCE_CONDA_RUN"] = "0"

from mcp_agent import discovery_agent_run_pipeline
import time

def test():
    print("Starting pipeline run (MOCKED)...")
    result = discovery_agent_run_pipeline(
        protein="KRAS",
        disease="colorectal cancer",
        run_id="test_mock_run",
        iterations=1,
        num_smiles=2
    )
    print("Pipeline result:")
    print(result)

if __name__ == "__main__":
    test()
