#!/usr/bin/env python
"""
DiscoveryAgent Pipeline Runner - Drug Discovery Automation

Usage:
    # Pipeline: set protein + disease in YAML, or pass --protein / --disease
    conda run -n DiscoveryAgent python run_discovery_agent.py --config pipeline_config.yaml

    # Override target without editing the file (one line)
    conda run -n DiscoveryAgent python run_discovery_agent.py -c pipeline_config.yaml --protein "EGFR" --disease "non-small cell lung cancer"

    # Q&A mode (RAG-based) - requires terminal with stdin support
    conda activate DiscoveryAgent && python run_discovery_agent.py --qna
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Suppress RDKit C-level stderr warnings at the earliest possible point
import warnings
warnings.filterwarnings("ignore")

_backend_root = Path(__file__).resolve().parents[2]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
try:
    import dx_lab_env

    dx_lab_env.load_shared_dotenv()
except Exception:
    pass

from configs.tool_globals import LLM_MODEL as DEFAULT_LLM_MODEL

# Prevent local mcp.py from shadowing the mcp SDK
_script_dir = os.path.dirname(os.path.abspath(__file__))
_sys_path_backup = sys.path[:]
sys.path = [p for p in sys.path if os.path.abspath(p) != _script_dir]

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

sys.path = _sys_path_backup


# Default configuration (protein / disease must come from YAML or --protein / --disease)
DEFAULT_CONFIG = {
    "protein": None,
    "disease": None,
    "iterations": 2,
    "num_smiles": 2,
    "run_boltz": False,
    "boltz_top_k": 2,
    "boltz_extra_args_json": '["--use_msa_server","--accelerator","gpu","--num_workers","4"]',
    "model": DEFAULT_LLM_MODEL,
    "min_qed": 0.50,   # Minimum QED score for candidate selection
    "min_pkd": 5.0,    # Minimum pKd value for candidate selection
}


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file or use defaults."""
    config = DEFAULT_CONFIG.copy()

    if config_path:
        try:
            import yaml
            with open(config_path, "r") as f:
                user_config = yaml.safe_load(f)
            if user_config:
                config.update(user_config)
            print(f"Loaded config from: {config_path}")
        except ImportError:
            print("Warning: PyYAML not installed. Using default config.")
            print("Install with: pip install pyyaml")
        except FileNotFoundError:
            print(f"Warning: Config file not found: {config_path}")
            print("Using default config.")
        except Exception as e:
            print(f"Warning: Error loading config: {e}")
            print("Using default config.")

    return config


def _nonempty_str(value) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


def validate_pipeline_target(config: dict) -> None:
    """Pipeline mode requires a target protein and disease context."""
    if not _nonempty_str(config.get("protein")) or not _nonempty_str(config.get("disease")):
        print(
            "\nError: pipeline mode requires both `protein` and `disease`.\n"
            "  • Add them to your YAML config, or\n"
            "  • Pass:  --protein \"<target name>\"  --disease \"<indication or context>\"\n",
            file=sys.stderr,
        )
        sys.exit(2)


def find_latest_run_dir():
    """Find the most recent run directory."""
    runs_dir = os.path.join(os.path.dirname(__file__), "runs")
    if not os.path.exists(runs_dir):
        return None
    dirs = [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))]
    if not dirs:
        return None
    dirs.sort(reverse=True)
    return os.path.join(runs_dir, dirs[0])


async def monitor_progress_background(stop_event: asyncio.Event, interval: int = 5):
    """Monitor progress by reading status.json periodically in background."""
    last_step = None
    last_details = None
    run_dir = None

    while not stop_event.is_set():
        # Use wait_for with timeout to be responsive to stop_event
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break  # stop_event was set
        except asyncio.TimeoutError:
            pass  # Continue monitoring

        # Find run dir if not found yet
        if run_dir is None:
            run_dir = find_latest_run_dir()
            if run_dir:
                print(f"\n  [RUN DIR] {run_dir}")

        if run_dir is None:
            continue

        status_file = os.path.join(run_dir, "status.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, "r") as f:
                    status = json.load(f)
                current_step = status.get("current_step", "unknown")
                steps = status.get("steps", [])

                # Get latest step details
                details = ""
                if steps:
                    latest = steps[-1]
                    step_details = latest.get("details", {})
                    if step_details:
                        detail_parts = []
                        for k, v in step_details.items():
                            if k not in ("substep",) and v is not None:
                                detail_parts.append(f"{k}={v}")
                        if detail_parts:
                            details = " | " + ", ".join(detail_parts[:3])

                if current_step != last_step or details != last_details:
                    last_step = current_step
                    last_details = details
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"  [{timestamp}] {current_step}{details}", flush=True)

            except Exception:
                pass


def _mcp_server_env() -> dict:
    """Env for the MCP subprocess; respects parent ``DISCOVERY_AGENT_*`` overrides."""
    base = dict(os.environ)
    base.setdefault(
        "DISCOVERY_AGENT_FORCE_CONDA_RUN",
        os.environ.get("DISCOVERY_AGENT_FORCE_CONDA_RUN", "1"),
    )
    base.setdefault(
        "DISCOVERY_AGENT_CONDA_ENV",
        os.environ.get("DISCOVERY_AGENT_CONDA_ENV", "DiscoveryAgent"),
    )
    return base


async def run_qna_mode(config: dict):
    """Run interactive Q&A mode via MCP."""
    server_script = os.path.join(os.path.dirname(__file__), "mcp_agent.py")
    transport = StdioTransport(
        command=sys.executable,
        args=[server_script],
        cwd=os.path.dirname(server_script),
        env=_mcp_server_env(),
    )

    async with Client(transport) as client:
        print("=" * 70)
        print("DiscoveryAgent Q&A Mode (RAG-based Research Paper Q&A)")
        print("=" * 70)
        print("\nThis mode downloads relevant papers and answers questions using RAG.")
        print("Type 'quit' or 'exit' to leave.\n")

        default_protein = config.get("protein", "")
        default_disease = config.get("disease", "")
        default_model = config.get("model", DEFAULT_LLM_MODEL)

        print(f"Default protein: {default_protein or '(none)'}")
        print(f"Default disease: {default_disease or '(none)'}")
        print()

        protein_input = input(f"Enter protein name [{default_protein}]: ").strip()
        protein = protein_input if protein_input else default_protein or None

        disease_input = input(f"Enter disease name [{default_disease}]: ").strip()
        disease = disease_input if disease_input else default_disease or None

        qna_run_id = None

        # Download papers immediately if protein and disease are provided
        if protein and disease:
            print(f"\nDownloading papers for {protein} + {disease}...")
            start_time = time.time()

            # Call DiscoveryAgent_qna with a dummy question to trigger paper download
            result = await client.call_tool("DiscoveryAgent_qna", {
                "question": "_init_papers_",  # Special init command
                "protein": protein,
                "disease": disease,
                "model": default_model,
            })

            elapsed = time.time() - start_time

            if result and hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        try:
                            data = json.loads(content_item.text)
                            qna_run_id = data.get("run_id")
                            papers = data.get("papers_downloaded", [])
                            print(f"Downloaded {len(papers)} papers to runs/{qna_run_id}/papers/ ({elapsed:.1f}s)")
                        except json.JSONDecodeError:
                            pass

            print("\nReady for questions!")

        print("-" * 70)

        while True:
            try:
                question = input("\nYour question: ").strip()
                if question.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    if qna_run_id:
                        print(f"Q&A session saved to: runs/{qna_run_id}/")
                    break
                if not question:
                    continue

                print("\nQuerying DiscoveryAgent Q&A...")
                start_time = time.time()

                # Build params - always pass run_id to reuse same session
                params = {
                    "question": question,
                    "model": default_model,
                }

                # Pass run_id to reuse existing session (papers already downloaded)
                if qna_run_id:
                    params["run_id"] = qna_run_id

                result = await client.call_tool("DiscoveryAgent_qna", params)

                elapsed = time.time() - start_time

                print("\n" + "=" * 50)
                if result and hasattr(result, 'content'):
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            try:
                                data = json.loads(content_item.text)

                                # Capture run_id from first response if not set
                                if not qna_run_id and data.get("run_id"):
                                    qna_run_id = data["run_id"]
                                    print(f"[Session: {qna_run_id}]")

                                if data.get("ok"):
                                    print(f"Answer: {data.get('answer', 'No answer')}")
                                else:
                                    print(f"Error: {data.get('error', 'Unknown error')}")
                            except json.JSONDecodeError:
                                print(content_item.text)
                print(f"(Time: {elapsed:.1f}s)")
                print("=" * 50)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


async def run_pipeline_mode(config: dict):
    """Run full pipeline mode with given config."""
    server_script = os.path.join(os.path.dirname(__file__), "mcp_agent.py")
    transport = StdioTransport(
        command=sys.executable,
        args=[server_script],
        cwd=os.path.dirname(server_script),
        env=_mcp_server_env(),
    )

    async with Client(transport) as client:
        print("=" * 70)
        print("DiscoveryAgent Drug Discovery Pipeline")
        print("=" * 70)

        # List available tools
        tools = await client.list_tools()
        print(f"\nAvailable tools: {[t.name for t in tools]}\n")

        # Display configuration
        print("Configuration:")
        if config.get("run_id"):
            print(f"  Run ID: {config['run_id']}")
        print(f"  Protein: {config['protein']}")
        print(f"  Disease: {config['disease']}")
        print(f"  (Drug will be discovered via LLM extraction)")
        print(f"  Iterations: {config['iterations']}")
        print(f"  Num SMILES: {config['num_smiles']} per model")
        print(f"  Run Boltz: {config['run_boltz']}")
        print(f"  Boltz Top K: {config['boltz_top_k']}")
        print(f"  Min QED: {config.get('min_qed', 0.50)}")
        print(f"  Min pKd: {config.get('min_pkd', 5.0)}")
        print(f"  Model: {config['model']}")
        print("-" * 70)
        print("\nProgress updates will appear below:")

        start_time = time.time()

        # Start background progress monitor
        stop_monitor = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_progress_background(stop_monitor))

        # Build pipeline parameters
        pipeline_params = {
            "protein": config["protein"],
            "disease": config["disease"],
            "iterations": config["iterations"],
            "num_smiles": config["num_smiles"],
            "run_boltz": config["run_boltz"],
            "boltz_top_k": config["boltz_top_k"],
            "boltz_extra_args_json": config["boltz_extra_args_json"],
            "model": config["model"],
            "min_qed": config.get("min_qed", 0.50),
            "min_pkd": config.get("min_pkd", 5.0),
        }

        # Add run_id if specified in config
        if config.get("run_id"):
            pipeline_params["run_id"] = config["run_id"]

        result = await client.call_tool("DiscoveryAgent_run_pipeline", pipeline_params)

        # Stop the progress monitor
        stop_monitor.set()
        await monitor_task

        elapsed = time.time() - start_time

        # Ensure stdout is not suppressed
        sys.stdout.flush()

        print("\n" + "=" * 70, flush=True)
        print(f"Pipeline Result (elapsed: {elapsed:.1f}s / {elapsed/60:.1f}min):", flush=True)
        print("=" * 70, flush=True)

        # Parse and pretty-print the result
        if result and hasattr(result, 'content'):
            for content_item in result.content:
                if hasattr(content_item, 'text'):
                    try:
                        data = json.loads(content_item.text)
                        print(json.dumps(data, indent=2), flush=True)

                        # Print summary
                        if isinstance(data, dict):
                            print("\n" + "-" * 70, flush=True)
                            print("SUMMARY:", flush=True)
                            print(f"  Run ID: {data.get('run_id', 'N/A')}", flush=True)
                            print(f"  Run Dir: {data.get('run_dir', 'N/A')}", flush=True)
                            print(f"  OK: {data.get('ok', 'N/A')}", flush=True)
                            if 'error' in data:
                                print(f"  ERROR: {data['error']}", flush=True)
                            if 'iterations' in data:
                                print(f"  Iterations completed: {len(data['iterations'])}", flush=True)
                                for it in data['iterations']:
                                    is_last = it.get('is_last', False)
                                    if is_last:
                                        print(f"    - iter_{it['iter']:02d}: ok={it.get('ok')}, is_last=True", flush=True)
                                        print(f"      Property files: affinity_before, admet_before, affinity_after, admet_after", flush=True)
                                    else:
                                        print(f"    - iter_{it['iter']:02d}: ok={it.get('ok')}", flush=True)
                            if 'boltz' in data:
                                print(f"  Boltz structures generated: {len(data['boltz'].get('yamls', []))}", flush=True)
                                print(f"  Boltz jobs: {len(data['boltz'].get('jobs', []))}", flush=True)
                    except json.JSONDecodeError:
                        print(content_item.text, flush=True)
        else:
            print(result, flush=True)

        print("\n" + "=" * 70, flush=True)
        print("PIPELINE COMPLETED SUCCESSFULLY!", flush=True)
        print("=" * 70, flush=True)
        print("\nCheck status.json for detailed pipeline status.", flush=True)
        print(flush=True)

        # Suppress stderr to prevent RDKit warnings from appearing after completion
        sys.stderr = open(os.devnull, 'w')




async def main():
    parser = argparse.ArgumentParser(
        description="DiscoveryAgent Drug Discovery Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline (protein + disease in YAML or on the CLI)
  python run_discovery_agent.py --config pipeline_config.yaml

  python run_discovery_agent.py -c pipeline_config.yaml --protein "KRAS" --disease "pancreatic ductal adenocarcinoma"

  # Q&A mode
  python run_discovery_agent.py --qna --config pipeline_config.yaml
        """
    )
    parser.add_argument("--config", "-c", type=str, help="Path to YAML configuration file")
    parser.add_argument("--qna", action="store_true", help="Run in Q&A mode (RAG-based)")
    parser.add_argument(
        "--protein",
        type=str,
        default=None,
        help="Target protein name (overrides YAML; any UniProt-searchable name)",
    )
    parser.add_argument(
        "--disease",
        type=str,
        default=None,
        help="Disease or therapeutic context (overrides YAML)",
    )
    args = parser.parse_args()

    # Load config (used by both pipeline and Q&A modes)
    config = load_config(args.config)
    if args.protein is not None:
        config["protein"] = args.protein.strip() or None
    if args.disease is not None:
        config["disease"] = args.disease.strip() or None

    if args.qna:
        await run_qna_mode(config)
    else:
        validate_pipeline_target(config)
        await run_pipeline_mode(config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        sys.stderr = open(os.devnull, 'w')
        os._exit(0)
