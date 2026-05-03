from __future__ import annotations
import argparse
import datetime as _dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_backend_root = Path(__file__).resolve().parents[2]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
try:
    import dx_lab_env

    dx_lab_env.load_shared_dotenv()
except Exception:
    pass

from configs.tool_globals import LLM_MODEL as DEFAULT_LLM_MODEL


DISCOVERY_AGENT_ROOT = Path(__file__).resolve().parent

# Heavy retrieval tools that download papers / run full RAG — excluded from pipeline
# extraction so the agent finishes quickly and never blocks on PDF pipelines.
_PIPELINE_EXTRACTION_EXCLUDED_TOOLS = frozenset({"download_relevant_papers", "question_answering"})


def _ensure_discovery_agent_importable() -> None:
    """Ensure `import DiscoveryAgent` works without breaking fastmcp's `import mcp.*`."""
    if str(DISCOVERY_AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(DISCOVERY_AGENT_ROOT))


def _should_force_conda_run() -> bool:
    """
    If set, subprocess jobs run via `conda run -n <env> ...` even if the MCP
    server itself isn't started from that conda env.
    """
    raw = os.getenv("DISCOVERY_AGENT_FORCE_CONDA_RUN")
    if raw is None:
        raw = os.getenv("AGENTD_FORCE_CONDA_RUN", "0")
    return raw.strip() in {"1", "true", "TRUE", "yes", "YES"}


def _conda_env_name() -> str:
    name = os.getenv("DISCOVERY_AGENT_CONDA_ENV") or os.getenv("AGENTD_CONDA_ENV") or "DiscoveryAgent"
    return name.strip() or "DiscoveryAgent"


def _python_worker_prefix() -> List[str]:
    """
    Prefix for launching python workers.
    - If MCP server is launched inside the desired env, sys.executable is enough.
    - If not, DISCOVERY_AGENT_FORCE_CONDA_RUN=1 will force `conda run -n DiscoveryAgent python ...`.
    """
    if _should_force_conda_run():
        return ["conda", "run", "-n", _conda_env_name(), "python"]
    return [sys.executable]


def _command_in_env(cmd: List[str]) -> List[str]:
    """
    Wrap a non-python command to run inside the conda env if requested.
    """
    if _should_force_conda_run():
        return ["conda", "run", "-n", _conda_env_name()] + cmd
    return cmd


def _now_utc_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _safe_json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _safe_json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class ProgressTracker:
    """
    Tracks pipeline progress to a status.json file that can be monitored externally.
    """

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.status_file = run_dir / "status.json"
        self.steps: List[Dict[str, Any]] = []
        self.current_step = ""
        self.started_at = _now_utc_iso()

    def update(self, step: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Update the current step and write to status file."""
        self.current_step = step
        step_entry = {
            "step": step,
            "timestamp": _now_utc_iso(),
            "details": details or {},
        }
        self.steps.append(step_entry)
        self._write()

    def _write(self) -> None:
        status = {
            "run_dir": str(self.run_dir),
            "started_at": self.started_at,
            "current_step": self.current_step,
            "last_updated": _now_utc_iso(),
            "steps": self.steps,
        }
        # Atomic replace avoids Windows blocking when status.json is open in an editor.
        tmp = self.status_file.with_suffix(".json.tmp")
        _safe_json_dump(tmp, status)
        os.replace(tmp, self.status_file)


def _parse_fasta_to_sequence(fasta_text: str) -> str:
    """
    Convert UniProt FASTA (with header + newlines) into a single sequence string.
    """
    if not fasta_text:
        return ""
    lines = [ln.strip() for ln in fasta_text.splitlines() if ln.strip()]
    if not lines:
        return ""
    if lines[0].startswith(">"):
        lines = lines[1:]
    seq = "".join(lines)
    # Ensure no whitespace
    return "".join(seq.split())


def _extract_pipeline_context_fast(
    *,
    protein: str,
    disease: str,
    progress: ProgressTracker,
) -> Dict[str, Any]:
    """Resolve target protein + seed ligand without a multi-step LLM agent.

    The legacy ReAct extraction step often appeared \"stuck\" because Kimi/NIM calls
    can block for minutes per iteration and ``max_execution_time`` can reach 7+ minutes
    before ``status.json`` advances. This path uses only retrieval tools (network)
    and typically finishes in seconds.
    """
    import re
    from DiscoveryAgent.tools import retrieval as R

    progress.update("extraction", {"substep": "uniprot_lookup"})
    ids = R.get_uniprot_ids.invoke({"protein_name": protein.strip()})
    if isinstance(ids, str) or not ids:
        raise RuntimeError(f"UniProt lookup failed: {ids}")

    uniprot_id = ids[0][0]

    progress.update("extraction", {"substep": "fetch_fasta"})
    fasta_raw = R.fetch_uniprot_fasta.invoke({"uniprot_id": uniprot_id})
    if not fasta_raw:
        raise RuntimeError(f"No FASTA returned for {uniprot_id}")
    seq = _parse_fasta_to_sequence(str(fasta_raw))

    # Ordered drug-name candidates: curated seeds + regex hits from Serper (if any).
    drug_candidates: List[str] = []
    pnorm = protein.upper().replace(" ", "").replace("-", "")
    seeds_by_target: Dict[str, List[str]] = {
        "KRAS": ["Sotorasib", "Adagrasib", "Pembrolizumab"],
        "EGFR": ["Osimertinib", "Erlotinib", "Gefitinib"],
        "BCL2": ["Venetoclax"],
        "PDL1": ["Atezolizumab", "Pembrolizumab"],
        "PDCD1LG1": ["Atezolizumab"],
    }
    for key, names in seeds_by_target.items():
        if not names:
            continue
        k = key.replace("-", "")
        if k in pnorm or pnorm in k:
            drug_candidates.extend(names)
            break

    progress.update("extraction", {"substep": "serper_seed_drugs"})
    try:
        blob = R.search.invoke(
            {"query": f"FDA approved drug targeting {protein} {disease}"}
        )
        if isinstance(blob, str):
            pat = re.compile(
                r"\b([A-Z][a-z]+(?:inib|mab|nib|zole|tide|stat|clax|lib|zumab))\b"
            )
            for m in pat.finditer(blob):
                name = m.group(1)
                if name not in drug_candidates:
                    drug_candidates.append(name)
    except Exception:
        pass

    seen: set[str] = set()
    ordered: List[str] = []
    for n in drug_candidates:
        if n not in seen:
            seen.add(n)
            ordered.append(n)

    progress.update("extraction", {"substep": "chembl_smiles"})
    drug_name: Optional[str] = None
    smiles: Optional[str] = None
    for name in ordered:
        smi = R.get_drug_smiles.invoke({"drug_name": name})
        if smi and len(str(smi).strip()) > 5:
            drug_name = name
            smiles = str(smi).strip()
            break

    if not drug_name or not smiles:
        raise RuntimeError(
            "Could not resolve seed SMILES from ChEMBL for candidates tried: "
            + (", ".join(ordered[:12]) if ordered else "(none)")
        )

    return {
        "protein": protein,
        "disease": disease,
        "uniprot_id": uniprot_id,
        "fasta": seq,
        "drug_name": drug_name,
        "SMILES": smiles,
    }


def _load_api_keys_fallback() -> None:
    """
    Prefer env vars; if missing, optionally fall back to configs/secret_keys.py.
    Never prints secrets.
    """
    try:
        from configs import secret_keys
        from configs.tool_globals import NVIDIA_API_BASE

        if not os.getenv("SERPER_API_KEY") and getattr(secret_keys, "serper_api_key", None):
            os.environ["SERPER_API_KEY"] = secret_keys.serper_api_key
        key = getattr(secret_keys, "llm_api_key", None)
        if key and not (os.getenv("LLM_API_KEY") or os.getenv("NVIDIA_API_KEY")):
            k = str(key).strip()
            os.environ.setdefault("LLM_API_KEY", k)
            os.environ.setdefault("NVIDIA_API_KEY", k)
            os.environ.setdefault("OPENAI_API_KEY", k)
        os.environ.setdefault("OPENAI_API_BASE", NVIDIA_API_BASE)
    except Exception:
        return


# -----------------------------
# Job management (subprocesses)
# -----------------------------


@dataclass(frozen=True)
class JobInfo:
    job_id: str
    pid: int
    command: List[str]
    cwd: str
    log_path: str
    started_at: str


class JobManager:
    """
    Minimal job manager: start subprocesses with stdout/stderr to log file,
    persist metadata to runs/<run_id>/jobs/<job_id>.json, and provide status/logs.
    """

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.jobs_dir = run_dir / "jobs"
        self.logs_dir = run_dir / "logs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _job_meta_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def start(
        self,
        *,
        name: str,
        command: List[str],
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> JobInfo:
        job_id = f"{name}_{uuid.uuid4().hex[:12]}"
        log_path = self.logs_dir / f"{job_id}.log"
        log_f = open(log_path, "wb")

        # Ensure cwd exists
        cwd.mkdir(parents=True, exist_ok=True)

        # Merge env
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        # Start process
        p = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=proc_env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )

        info = JobInfo(
            job_id=job_id,
            pid=int(p.pid),
            command=command,
            cwd=str(cwd),
            log_path=str(log_path),
            started_at=_now_utc_iso(),
        )
        _safe_json_dump(self._job_meta_path(job_id), {"status": "running", **info.__dict__})
        return info

    def _pid_is_alive(self, pid: int) -> bool:
        """
        Check if a process is alive, handling zombie processes on Linux.
        A zombie process (defunct) still has a PID but is not truly running.
        """
        try:
            os.kill(pid, 0)
        except OSError:
            return False

        # On Linux, check /proc/<pid>/status for zombie state
        proc_status = Path(f"/proc/{pid}/status")
        if proc_status.exists():
            try:
                content = proc_status.read_text()
                for line in content.splitlines():
                    if line.startswith("State:"):
                        # State: Z (zombie) or State: R (running), etc.
                        if "Z" in line or "zombie" in line.lower():
                            return False
                        break
            except Exception:
                pass

        return True

    def status(self, job_id: str) -> Dict[str, Any]:
        meta_path = self._job_meta_path(job_id)
        if not meta_path.exists():
            return {"job_id": job_id, "status": "unknown", "error": "job id not found"}

        meta = _safe_json_load(meta_path)
        pid = int(meta.get("pid", -1))
        alive = pid > 0 and self._pid_is_alive(pid)

        if meta.get("status") == "running" and not alive:
            # We don't have exit code portably without psutil; infer from log footer if worker writes it.
            meta["status"] = "finished"
            meta["finished_at"] = _now_utc_iso()
            _safe_json_dump(meta_path, meta)

        return meta

    def tail_logs(self, job_id: str, max_bytes: int = 100_000) -> Dict[str, Any]:
        meta = self.status(job_id)
        log_path = meta.get("log_path")
        if not log_path:
            return {"job_id": job_id, "error": "no log_path"}
        lp = Path(log_path)
        if not lp.exists():
            return {"job_id": job_id, "error": "log file not found", "log_path": log_path}
        data = lp.read_bytes()
        if len(data) > max_bytes:
            data = data[-max_bytes:]
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = repr(data)
        return {"job_id": job_id, "log_path": log_path, "tail": text}

    def cancel(self, job_id: str) -> Dict[str, Any]:
        meta = self.status(job_id)
        pid = int(meta.get("pid", -1))
        if pid <= 0:
            return {"job_id": job_id, "status": meta.get("status", "unknown"), "error": "no pid"}
        if not self._pid_is_alive(pid):
            return {"job_id": job_id, "status": "finished"}
        try:
            os.kill(pid, signal.SIGTERM)
            meta["status"] = "cancelled"
            meta["cancelled_at"] = _now_utc_iso()
            _safe_json_dump(self._job_meta_path(job_id), meta)
            return meta
        except Exception as e:
            return {"job_id": job_id, "error": str(e)}


# -----------------------------
# Worker implementations
# -----------------------------


def _worker_predict_affinity(*, sequence: str, smiles_csv: str, out_dir: str) -> int:
    """
    Runs BAPULM affinity prediction in a separate process to release GPU memory after exit.
    """
    # Suppress warnings to keep output clean
    import warnings
    warnings.filterwarnings("ignore")
    
    # Redirect stderr to suppress RDKit warnings
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    
    try:
        _load_api_keys_fallback()
        os.makedirs(out_dir, exist_ok=True)
        os.chdir(out_dir)

        _ensure_discovery_agent_importable()
        from DiscoveryAgent.tools.prediction import predict_affinity_batch  # type: ignore

        payload = json.dumps({"sequence": sequence, "smiles_path": smiles_csv})
        result = predict_affinity_batch(payload)
        return 0
    finally:
        sys.stderr = old_stderr


def _worker_boltz_predict(*, yaml_path: str, out_dir: str, extra_args: List[str]) -> int:
    """
    Runs `boltz predict` as a subprocess worker.
    """
    os.makedirs(out_dir, exist_ok=True)
    os.chdir(out_dir)

    cmd = ["boltz", "predict", yaml_path] + extra_args
    # Run with suppressed output (logs go to boltz's own output files)
    completed = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return int(completed.returncode)


def _worker_predict_admet(*, smiles_csv: str, out_dir: str) -> int:
    """
    Runs ADMET prediction in a separate process.
    This is necessary because the DeepPK API can take several minutes and would
    otherwise cause MCP client timeouts.
    """
    # Suppress warnings to keep output clean
    import warnings
    warnings.filterwarnings("ignore")
    
    # Redirect stderr to suppress RDKit warnings
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    
    try:
        _load_api_keys_fallback()
        os.makedirs(out_dir, exist_ok=True)
        os.chdir(out_dir)

        _ensure_discovery_agent_importable()
        from DiscoveryAgent.tools.prediction import get_admet_predictions  # type: ignore

        result = get_admet_predictions(smiles_csv)
        return 0
    finally:
        sys.stderr = old_stderr


def _run_worker_from_argv(argv: List[str]) -> int:
    # Suppress ALL stderr output at the earliest possible point
    # This prevents RDKit C++ warnings from appearing in terminal
    import io
    import os
    import warnings
    warnings.filterwarnings("ignore")
    
    # Redirect stderr to /dev/null at OS level to catch C-level output
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)  # 2 = stderr file descriptor
    os.close(devnull_fd)
    sys.stderr = io.StringIO()
    
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("_worker", nargs="?")
    parser.add_argument("--kind", required=True, choices=["affinity", "boltz", "admet"])
    parser.add_argument("--sequence", default="")
    parser.add_argument("--smiles_csv", default="")
    parser.add_argument("--yaml_path", default="")
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--extra_args_json", default="[]")
    args = parser.parse_args(argv)

    if args.kind == "affinity":
        return _worker_predict_affinity(
            sequence=args.sequence, smiles_csv=args.smiles_csv, out_dir=args.out_dir
        )
    if args.kind == "admet":
        return _worker_predict_admet(
            smiles_csv=args.smiles_csv, out_dir=args.out_dir
        )
    if args.kind == "boltz":
        extra_args = json.loads(args.extra_args_json)
        return _worker_boltz_predict(
            yaml_path=args.yaml_path, out_dir=args.out_dir, extra_args=list(extra_args)
        )
    raise ValueError(f"Unknown worker kind: {args.kind}")


# -----------------------------
# Pipeline helpers (in-process)
# -----------------------------


def _ensure_run_dir(run_root: Path, run_id: Optional[str] = None) -> Tuple[str, Path]:
    run_id = run_id or _dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def _copy_into_run_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def _merge_affinity_admet(affinity_csv: Path, admet_csv: Path, out_csv: Path) -> Path:
    """Merge affinity and ADMET CSVs on **canonical SMILES** (inner join).

    Row-index merging is unsafe because the ADMET API may re-order, drop, or
    re-canonicalize inputs. We standardize both sides with RDKit and merge on
    the resulting canonical SMILES, then emit a ``merge_mismatch.json`` sidecar
    whenever any input rows are dropped so users can inspect losses.
    """
    import pandas as pd

    from DiscoveryAgent.chem import standardize  # type: ignore

    df_aff = pd.read_csv(affinity_csv)
    df_admet = pd.read_csv(admet_csv)

    if "SMILES" not in df_aff.columns:
        raise ValueError("Affinity CSV must include a 'SMILES' column")
    if "SMILES" not in df_admet.columns:
        raise ValueError("ADMET CSV must include a 'SMILES' column")

    df_aff = df_aff.copy()
    df_admet = df_admet.copy()
    df_aff["_canon"] = df_aff["SMILES"].astype(str).map(standardize)
    df_admet["_canon"] = df_admet["SMILES"].astype(str).map(standardize)

    aff_valid = df_aff.dropna(subset=["_canon"]).drop_duplicates(subset=["_canon"], keep="first")
    admet_valid = df_admet.dropna(subset=["_canon"]).drop_duplicates(subset=["_canon"], keep="first")

    admet_for_join = admet_valid.drop(columns=["SMILES"], errors="ignore")

    merged = pd.merge(aff_valid, admet_for_join, on="_canon", how="inner")
    merged["SMILES"] = merged["_canon"]
    merged = merged.drop(columns=["_canon"])

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_csv, index=False)

    aff_canon = set(aff_valid["_canon"])
    admet_canon = set(admet_valid["_canon"])
    only_aff = sorted(aff_canon - admet_canon)
    only_admet = sorted(admet_canon - aff_canon)
    if (
        len(aff_valid) != len(df_aff)
        or len(admet_valid) != len(df_admet)
        or only_aff
        or only_admet
    ):
        sidecar = out_csv.parent / "errors" / "merge_mismatch.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        _safe_json_dump(sidecar, {
            "affinity_input_rows": int(len(df_aff)),
            "admet_input_rows": int(len(df_admet)),
            "affinity_valid_rows": int(len(aff_valid)),
            "admet_valid_rows": int(len(admet_valid)),
            "merged_rows": int(len(merged)),
            "only_in_affinity_sample": only_aff[:20],
            "only_in_admet_sample": only_admet[:20],
        })

    return out_csv


def _score_candidates(property_csv: Path, out_csv: Path) -> Path:
    """Add rule-based booleans and QED + ``num_passed_rules`` to a property CSV.

    Columns consumed from the input CSV: ``SMILES`` (required) plus the
    per-molecule ADMET/FDA fields that ``DrugLikenessAnalyzer`` reads. RDKit-
    derived descriptors (MW, LogP, QED, rule flags) are recomputed here from a
    canonical SMILES so scoring is consistent regardless of which upstream
    stage produced the CSV.
    """
    import io
    import warnings
    import pandas as pd

    from DiscoveryAgent.chem import standardize  # type: ignore

    warnings.filterwarnings("ignore")

    old_stderr_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    try:
        from DiscoveryAgent.analysis.drug_likeness_analyzer import DrugLikenessAnalyzer  # type: ignore

        df = pd.read_csv(property_csv)
        if "SMILES" not in df.columns:
            raise ValueError(
                f"_score_candidates: input CSV {property_csv} is missing required 'SMILES' column; "
                f"got columns={list(df.columns)}"
            )

        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            d = r.to_dict()
            raw_smiles = d.get("SMILES")
            canon = standardize(str(raw_smiles)) if raw_smiles is not None else None
            smiles = canon or raw_smiles
            d["SMILES"] = smiles
            analyzer = DrugLikenessAnalyzer(data=d, smiles=smiles)
            report = analyzer.get_summary_report()

            # Normalize into flat columns
            lip = bool(report.get("lipinski_rule_of_5"))
            veb = bool(report.get("veber_rule"))
            gho = bool(report.get("ghose_filter"))
            ro3 = bool(report.get("rule_of_3"))
            opr = bool(report.get("oprea_lead_like"))
            num_passed = int(sum([lip, veb, gho, ro3, opr]))
            qed = analyzer.calculated_properties.get("qed")

            out_row = dict(d)
            out_row.update(
                {
                    "lipinski_rule_of_5": lip,
                    "veber_rule": veb,
                    "ghose_filter": gho,
                    "rule_of_3": ro3,
                    "oprea_lead_like": opr,
                    "num_passed_rules": num_passed,
                    "QED": qed,
                }
            )
            rows.append(out_row)
        scored = pd.DataFrame(rows)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        scored.to_csv(out_csv, index=False)
        return out_csv
    finally:
        sys.stderr = old_stderr
        # Restore OS-level stderr
        os.dup2(old_stderr_fd, 2)
        os.close(old_stderr_fd)


def _select_final_candidates(
    scored_csv: Path,
    out_csv: Path,
    *,
    top_k: int = 10,
    min_pkd: float = 6.0,
    min_qed: float = 0.55,
) -> Path:
    """Select final candidates for Boltz based on drug-likeness criteria.

    Filters applied (in order):
    - (i)  satisfy Oprea's lead-likeness filter (*soft*: if this empties the
           pool we retry once without it and mark ``relaxed_oprea: true`` in
           the sidecar metadata).
    - (ii) pass at least 2 of 3 drug-likeness rules (Lipinski, Veber, Ghose).
    - (iii) predicted ``pKd >= min_pkd`` (matches the documented behavior).
    - (iv)  ``QED >= min_qed``.

    Remaining rows are sorted by pKd descending; top_k are kept. All SMILES in
    the output CSV are canonicalized via the shared RDKit helpers.
    """
    import pandas as pd

    from DiscoveryAgent.chem import standardize  # type: ignore

    df = pd.read_csv(scored_csv).copy()
    original_count = len(df)

    rule_cols = ["lipinski_rule_of_5", "veber_rule", "ghose_filter"]
    existing_rules = [c for c in rule_cols if c in df.columns]

    def _apply_core_filters(frame: "pd.DataFrame") -> "pd.DataFrame":
        out = frame.copy()
        if existing_rules:
            out["drug_rules_passed"] = out[existing_rules].sum(axis=1)
            out = out[out["drug_rules_passed"] >= 2].copy()
        if "Affinity [pKd]" in out.columns:
            out = out[out["Affinity [pKd]"] >= min_pkd].copy()
        if "QED" in out.columns:
            out = out[out["QED"] >= min_qed].copy()
        return out

    relaxed_oprea = False
    if "oprea_lead_like" in df.columns:
        strict = df[df["oprea_lead_like"] == True].copy()
        strict_filtered = _apply_core_filters(strict)
        if len(strict_filtered) == 0:
            relaxed_oprea = True
            filtered = _apply_core_filters(df)
        else:
            filtered = strict_filtered
    else:
        filtered = _apply_core_filters(df)

    if "Affinity [pKd]" in filtered.columns:
        filtered = filtered.sort_values(by="Affinity [pKd]", ascending=False).copy()

    selected = filtered.head(top_k).copy()

    if "SMILES" in selected.columns and len(selected):
        selected["SMILES"] = selected["SMILES"].astype(str).map(
            lambda s: standardize(s) or s
        )

    keep_cols = [
        "SMILES",
        "Affinity [pKd]",
        "QED",
        "lipinski_rule_of_5",
        "veber_rule",
        "ghose_filter",
        "oprea_lead_like",
    ]
    final_cols = [c for c in keep_cols if c in selected.columns]
    selected = selected[final_cols]

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(out_csv, index=False)

    sidecar = out_csv.parent / (out_csv.stem + ".selection.json")
    _safe_json_dump(sidecar, {
        "scored_rows": int(original_count),
        "selected_rows": int(len(selected)),
        "min_pkd": float(min_pkd),
        "min_qed": float(min_qed),
        "top_k": int(top_k),
        "relaxed_oprea": bool(relaxed_oprea),
    })

    return out_csv


def _refine_smiles(
    in_csv: Path,
    out_csv: Path,
    *,
    protein: str,
    model: str = DEFAULT_LLM_MODEL,
) -> Path:
    """
    Run the LLM-driven SMILES refinement. This is the step that was manual in notebooks.
    We automate it and save a deterministic mapping file with Updated_SMILES + rationale.
    Output format: SMILES, Updated_SMILES, Property, Rationale
    """
    import io
    import warnings
    
    warnings.filterwarnings("ignore")
    
    old_stderr_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    
    try:
        _load_api_keys_fallback()
        from DiscoveryAgent.agents import DiscoveryAgent as DiscoveryAgentClass  # type: ignore
        from DiscoveryAgent.tools.prediction import check_smiles_validity  # type: ignore
        from DiscoveryAgent.prompts.molecular_refinement import PREFIX, SUFFIX, FORMAT_INSTRUCTIONS  # type: ignore
        from DiscoveryAgent.utils import process_dataset_with_agent  # type: ignore

        tools = [check_smiles_validity]
        refinement_agent = DiscoveryAgentClass(
            tools,
            model=model,
            prefix=PREFIX,
            suffix=SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
        ).agent

        df_out = process_dataset_with_agent(str(in_csv), protein, tools, refinement_agent)

        keep_cols = ["SMILES", "Updated_SMILES", "Property", "Rationale"]
        available_cols = [c for c in keep_cols if c in df_out.columns]
        df_out = df_out[available_cols]

        out_csv.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out_csv, index=False)
        return out_csv
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        os.dup2(old_stderr_fd, 2)
        os.close(old_stderr_fd)


def _extract_updated_smiles(refinement_csv: Path, out_smiles_csv: Path) -> Path:
    """Extract Updated_SMILES from refinement.csv and rename to SMILES for next iteration."""
    import pandas as pd

    df = pd.read_csv(refinement_csv)
    if "Updated_SMILES" not in df.columns:
        raise ValueError("Refinement CSV missing Updated_SMILES column")
    updated = df[["Updated_SMILES"]].dropna()
    updated = updated.rename(columns={"Updated_SMILES": "SMILES"})
    updated = updated[updated["SMILES"].astype(str).str.strip() != ""]
    out_smiles_csv.parent.mkdir(parents=True, exist_ok=True)
    updated.to_csv(out_smiles_csv, index=False)
    return out_smiles_csv


def _cleanup_intermediate_files(prop_dir: Path, keep_files: List[str]) -> None:
    """Remove intermediate prediction CSVs, preserving ``keep_files``.

    Failures are recorded in ``<prop_dir>/../errors/cleanup.json`` (appended)
    instead of being silently swallowed, so that incomplete cleanup is visible
    in the run artifacts.
    """
    if not prop_dir.exists():
        return

    errors: List[Dict[str, Any]] = []
    for f in prop_dir.iterdir():
        if f.is_file() and f.suffix == ".csv" and f.name not in keep_files:
            try:
                f.unlink()
            except Exception as e:
                errors.append({"path": str(f), "error": str(e)})

    if errors:
        err_dir = prop_dir.parent / "errors"
        err_dir.mkdir(parents=True, exist_ok=True)
        log_path = err_dir / "cleanup.json"
        existing: List[Dict[str, Any]] = []
        if log_path.exists():
            try:
                loaded = _safe_json_load(log_path)
                if isinstance(loaded, list):
                    existing = loaded
            except Exception:
                existing = []
        existing.extend(errors)
        _safe_json_dump(log_path, existing)


def _validate_smiles_csv(in_csv: Path, out_csv: Path) -> Dict[str, Any]:
    """Standardize a SMILES CSV and drop invalid rows.

    - Reads ``in_csv`` (must have a ``SMILES`` column).
    - Writes canonical SMILES to ``out_csv``.
    - Writes a ``dropped.json`` sidecar next to ``out_csv`` listing indices and
      original strings of dropped rows.
    - Returns a small summary dict for the caller to surface via ``progress``.
    """
    import pandas as pd

    from DiscoveryAgent.chem import standardize  # type: ignore

    out_csv.parent.mkdir(parents=True, exist_ok=True)

    if not in_csv.exists():
        raise FileNotFoundError(f"SMILES CSV not found: {in_csv}")

    df = pd.read_csv(in_csv)
    if "SMILES" not in df.columns:
        raise ValueError(f"{in_csv} is missing required 'SMILES' column")

    dropped: List[Dict[str, Any]] = []
    canon_rows: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        raw = row.get("SMILES")
        canon = standardize(str(raw)) if raw is not None else None
        if not canon:
            dropped.append({"index": int(idx), "original": None if raw is None else str(raw)})
            continue
        new_row = row.to_dict()
        new_row["SMILES"] = canon
        canon_rows.append(new_row)

    cleaned = pd.DataFrame(canon_rows, columns=df.columns)
    cleaned.to_csv(out_csv, index=False)

    sidecar = out_csv.parent / (out_csv.stem + ".dropped.json")
    _safe_json_dump(sidecar, {
        "input_csv": str(in_csv),
        "output_csv": str(out_csv),
        "input_rows": int(len(df)),
        "kept_rows": int(len(cleaned)),
        "dropped_rows": int(len(dropped)),
        "dropped_sample": dropped[:25],
    })

    return {
        "input_rows": int(len(df)),
        "kept_rows": int(len(cleaned)),
        "dropped_rows": int(len(dropped)),
    }


def _write_molecule_viz_csv(
    csv_path: Path,
    out_png: Path,
    *,
    legend_cols: Optional[List[str]] = None,
) -> None:
    """Draw a 2D RDKit structure grid from a SMILES CSV; never raises."""
    try:
        from DiscoveryAgent.chem.molecule_viz import write_smiles_csv_to_png

        write_smiles_csv_to_png(
            Path(csv_path),
            Path(out_png),
            legend_cols=legend_cols,
        )
    except Exception:
        return


def _write_smiles_csv(smiles: str, out_csv: Path) -> Path:
    """Write a single seed SMILES, canonicalized when possible."""
    import pandas as pd

    from DiscoveryAgent.chem import standardize  # type: ignore

    canon = standardize(smiles) or smiles
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"SMILES": canon}]).to_csv(out_csv, index=False)
    return out_csv


def _combine_pool_csvs(pool_dir: Path, out_csv: Path) -> Path:
    """Combine SMILES from Reinvent/Mol2Mol sampling into one **canonical** CSV.

    Every SMILES is standardized (salt-stripped + canonicalized) and duplicates
    are removed by canonical form rather than raw string equality. This avoids
    wasted affinity/ADMET compute on tautomer- or kekulization-equivalent
    molecules.
    """
    import pandas as pd

    from DiscoveryAgent.chem import dedup_canonical  # type: ignore

    reinvent_csv = pool_dir / "Reinvent_sampling.csv"
    mol2mol_csv = pool_dir / "Mol2Mol_sampling.csv"

    raw: List[str] = []
    for csv_path in [reinvent_csv, mol2mol_csv]:
        if not csv_path.exists():
            continue
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if "SMILES" not in df.columns:
            continue
        raw.extend(df["SMILES"].dropna().astype(str).tolist())

    canonical = dedup_canonical(raw)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"SMILES": canonical}).to_csv(out_csv, index=False)
    return out_csv


def _run_reinvent_pooling(
    *,
    run_dir: Path,
    initial_smiles: str,
    model: str = DEFAULT_LLM_MODEL,
    num_smiles: int = 20,  # Number of SMILES to sample (reduced for faster testing)
) -> Dict[str, Any]:
    """
    Pooling wrapper. Uses existing tool functions in generation.py.

    Uses REINVENT_PATH from configs/tool_globals.py.
    """
    _load_api_keys_fallback()
    os.chdir(run_dir)

    _ensure_discovery_agent_importable()
    import DiscoveryAgent.tools.generation as gen  
    from configs.tool_globals import REINVENT_PATH  

    # Validate that generation.py can find expected file
    expected_sampling = Path(REINVENT_PATH) / "configs" / "toml" / "sampling.toml"
    if not expected_sampling.exists():
        return {
            "ok": False,
            "error": "REINVENT sampling.toml not found",
            "hint": "Update REINVENT_PATH in configs/tool_globals.py",
            "expected": str(expected_sampling),
        }

    # Mol2Mol
    gen.save_smi_for_mol2mol(initial_smiles)
    mol2mol_toml = gen.update_reinvent_config("Mol2Mol")
    reinvent_toml = gen.update_reinvent_config("Reinvent")

    # Override num_smiles in generated TOML files for faster testing
    def _patch_num_smiles(toml_path: str, count: int):
        """Patch num_smiles in TOML file without modifying original configs."""
        import re
        with open(toml_path, "r") as f:
            content = f.read()

        content = re.sub(r"num_smiles\s*=\s*\d+", f"num_smiles = {count}", content)
        with open(toml_path, "w") as f:
            f.write(content)

    _patch_num_smiles(mol2mol_toml, num_smiles)
    _patch_num_smiles(reinvent_toml, num_smiles)

    # Execute REINVENT. 
    def _run_reinvent_cfg(cfg: str) -> str:
        log_file = cfg.replace(".toml", ".log")
        cmd = _command_in_env(["reinvent", "-l", log_file, cfg])
        try:
            subprocess.run(cmd, check=True, cwd=str(run_dir))
            return "REINVENT execution completed successfully."
        except subprocess.CalledProcessError as e:
            return f"Error occurred while running REINVENT: {e}"
        except FileNotFoundError:
            return "Error: 'reinvent' command not found. Ensure REINVENT is installed in the active environment."

    mol2mol_result = _run_reinvent_cfg(mol2mol_toml)
    reinvent_result = _run_reinvent_cfg(reinvent_toml)
    return {
        "ok": True,
        "configs": {"Mol2Mol": mol2mol_toml, "Reinvent": reinvent_toml},
        "results": {"Mol2Mol": mol2mol_result, "Reinvent": reinvent_result},
        "pool_dir": str(run_dir / "pool"),
    }


def _generate_boltz_yamls(
    *,
    run_dir: Path,
    protein_sequence: str,
    smiles_list: List[str],
) -> List[str]:
    os.chdir(run_dir)
    _ensure_discovery_agent_importable()
    from DiscoveryAgent.tools.generation import generate_complex_structure  # type: ignore

    yaml_paths: List[str] = []
    for smi in smiles_list:
        payload = json.dumps({"sequence": protein_sequence, "smiles": smi})
        _ = generate_complex_structure(payload)
        cfg_dir = run_dir / "configs"
        if not cfg_dir.exists():
            continue
        yamls = sorted(cfg_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
        if yamls:
            yaml_paths.append(str(yamls[0].resolve()))
    return yaml_paths


def _wait_for_jobs(
    jm: JobManager,
    job_ids: List[str],
    progress: ProgressTracker,
    progress_key: str,
    poll_interval: int = 5,
) -> Dict[str, Dict[str, Any]]:
    """
    Wait for multiple jobs to complete, updating progress periodically.
    Returns dict of job_id -> final status.
    """
    wait_count = 0
    while True:
        statuses = {jid: jm.status(jid) for jid in job_ids}
        running = [jid for jid, s in statuses.items() if s.get("status") == "running"]
        if not running:
            break
        time.sleep(poll_interval)
        wait_count += 1
        # Update progress every 30 seconds
        if wait_count % 6 == 0:
            progress.update(progress_key, {
                "substep": "waiting",
                "wait_seconds": wait_count * poll_interval,
                "statuses": {jid: s.get("status") for jid, s in statuses.items()},
            })
    return {jid: jm.status(jid) for jid in job_ids}


def _run_prediction_jobs(
    *,
    jm: JobManager,
    iter_dir: Path,
    smiles_csv: Path,
    seq: str,
    iteration: int,
    suffix: str = "",
) -> Tuple[JobInfo, JobInfo]:
    """
    Launch affinity and ADMET prediction jobs for given SMILES CSV.
    Returns (affinity_job, admet_job).
    """
    job_name_suffix = f"_i{iteration:02d}{suffix}"

    job_aff = jm.start(
        name=f"affinity{job_name_suffix}",
        command=[
            *_python_worker_prefix(),
            str(DISCOVERY_AGENT_ROOT / "mcp_agent.py"),
            "_worker",
            "--kind",
            "affinity",
            "--sequence",
            seq,
            "--smiles_csv",
            str(smiles_csv),
            "--out_dir",
            str(iter_dir),
        ],
        cwd=iter_dir,
        env={"PYTHONPATH": str(DISCOVERY_AGENT_ROOT)},
    )

    job_admet = jm.start(
        name=f"admet{job_name_suffix}",
        command=[
            *_python_worker_prefix(),
            str(DISCOVERY_AGENT_ROOT / "mcp_agent.py"),
            "_worker",
            "--kind",
            "admet",
            "--smiles_csv",
            str(smiles_csv),
            "--out_dir",
            str(iter_dir),
        ],
        cwd=iter_dir,
        env={"PYTHONPATH": str(DISCOVERY_AGENT_ROOT)},
    )

    return job_aff, job_admet


def _find_prediction_outputs(iter_dir: Path, smiles_csv_name: str) -> Tuple[Optional[Path], Optional[Path]]:
    """Find affinity and ADMET output files for a given iteration."""
    prop_dir = iter_dir / "property"

    affinity_out = prop_dir / f"affinity_{smiles_csv_name}"
    if not affinity_out.exists():
        candidates = list(prop_dir.glob("affinity_*.csv"))
        affinity_out = candidates[0] if candidates else None

    admet_out = prop_dir / f"admet_{smiles_csv_name}"
    if not admet_out.exists():
        candidates = list(prop_dir.glob("admet_*.csv"))
        admet_out = candidates[0] if candidates else None

    return affinity_out, admet_out


# -----------------------------
# MCP server
# -----------------------------


def _make_mcp():
    saved_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if p not in ("", str(DISCOVERY_AGENT_ROOT))]
        from fastmcp import FastMCP 
    finally:
        sys.path = saved_path

    mcp = FastMCP("DiscoveryAgent MCP")

    @mcp.tool(name="DiscoveryAgent_run_pipeline")
    def discovery_agent_run_pipeline(
        protein: str,
        disease: str,
        iterations: int = 2,
        num_smiles: int = 20,
        run_boltz: bool = False,
        boltz_top_k: int = 10,
        boltz_extra_args_json: str = "[\"--use_msa_server\",\"--accelerator\",\"gpu\",\"--num_workers\",\"20\"]",
        model: str = DEFAULT_LLM_MODEL,
        min_qed: float = 0.50,
        min_pkd: float = 5.0,
        run_id: Optional[str] = None,
        use_llm_for_extraction: bool = False,
    ) -> Dict[str, Any]:
        """
        End-to-end drug discovery pipeline automation.

        Parameters:
        - protein: Target protein name (e.g., "BCL-2", "EGFR")
        - disease: Disease context (e.g., "chronic lymphocytic leukemia")
        - iterations: Number of refinement iterations (default 2)
        - num_smiles: Number of SMILES to sample per model in REINVENT (default 20)
        - run_boltz: Whether to run Boltz structure generation (default False)
        - boltz_top_k: Number of top candidates for Boltz (default 10)
        - boltz_extra_args_json: Extra args for Boltz as JSON string
        - model: LLM model on NVIDIA NIM (default from configs/tool_globals.LLM_MODEL)
        - min_qed: Minimum QED score for candidate selection (default 0.50)
        - min_pkd: Minimum pKd value for candidate selection (default 5.0)
        - run_id: Custom run ID (optional, auto-generated if not provided)

        Note: REINVENT_PATH is read from configs/tool_globals.py
        
        Pipeline steps:
        1. Extraction (LLM-based): Discovers drug name, UniProt ID, FASTA, SMILES
        2. Pooling: Generate candidate molecules via REINVENT
        3. Iterative refinement loop
        4. Boltz structure generation for top candidates
        """
        _load_api_keys_fallback()
        _ensure_discovery_agent_importable()

        run_root = DISCOVERY_AGENT_ROOT / "runs"
        run_id2, run_dir = _ensure_run_dir(run_root, run_id)
        jm = JobManager(run_dir)
        progress = ProgressTracker(run_dir)

        progress.update("initializing", {"protein": protein, "disease": disease})

        def _safe_pkg_version(pkg_name: str) -> Optional[str]:
            try:
                from importlib.metadata import PackageNotFoundError, version  # type: ignore

                return version(pkg_name)
            except PackageNotFoundError:
                return None
            except Exception:
                return None

        try:
            import rdkit  # type: ignore
            rdkit_version = getattr(rdkit, "__version__", None) or _safe_pkg_version("rdkit")
        except Exception:
            rdkit_version = _safe_pkg_version("rdkit")

        reinvent_version = _safe_pkg_version("reinvent") or _safe_pkg_version("reinvent4")

        _safe_json_dump(
            run_dir / "run_config.json",
            {
                "protein": protein,
                "disease": disease,
                "iterations": iterations,
                "num_smiles": num_smiles,
                "run_boltz": run_boltz,
                "boltz_top_k": boltz_top_k,
                "boltz_extra_args_json": boltz_extra_args_json,
                "model": model,
                "min_qed": min_qed,
                "min_pkd": min_pkd,
                "created_at": _now_utc_iso(),
                "versions": {
                    "rdkit": rdkit_version,
                    "reinvent": reinvent_version,
                    "python": sys.version.split()[0],
                },
            },
        )

        # --- Target / seed extraction (deterministic fast path by default) ---
        # Legacy LLM ReAct extraction is disabled here: Kimi/NIM rounds can stall for
        # many minutes without updating status.json. Opt in with DISCOVERY_AGENT_USE_LLM_EXTRACTION=1.
        progress.update("extraction", {"substep": "starting"})
        os.chdir(run_dir)

        use_llm_extraction = False
        skip_inner_extraction = False
        ext_flag = os.environ.get("DISCOVERY_USE_EXTERNAL_CONTEXT", "").strip().lower()
        if ext_flag in ("1", "true", "yes", "on"):
            path = os.environ.get("DISCOVERY_CONTEXT_JSON_PATH", "").strip()
            inline = os.environ.get("DISCOVERY_CONTEXT_JSON", "").strip()
            raw = ""
            if path and Path(path).is_file():
                raw = Path(path).read_text(encoding="utf-8")
            elif inline:
                raw = inline
            if not raw.strip():
                return {
                    "ok": False,
                    "run_id": run_id2,
                    "error": (
                        "DISCOVERY_USE_EXTERNAL_CONTEXT set but missing "
                        "DISCOVERY_CONTEXT_JSON_PATH or DISCOVERY_CONTEXT_JSON"
                    ),
                }
            try:
                bundle = json.loads(raw)
            except json.JSONDecodeError as je:
                return {"ok": False, "run_id": run_id2, "error": f"invalid external context JSON: {je}"}
            extraction = {
                "protein": bundle.get("protein", protein),
                "disease": bundle.get("disease", disease),
                "uniprot_id": str(bundle.get("uniprot_id") or ""),
                "fasta": str(bundle.get("fasta") or ""),
                "drug_name": str(bundle.get("drug_name") or "external_seed"),
                "SMILES": str(bundle.get("SMILES") or bundle.get("smiles") or ""),
            }
            if not extraction["SMILES"] or not extraction["fasta"]:
                return {
                    "ok": False,
                    "run_id": run_id2,
                    "error": "external context requires SMILES and fasta (sequence string)",
                }
            _safe_json_dump(
                run_dir / "extraction_response.json",
                {"mode": "external_context", "path": path or None},
            )
            skip_inner_extraction = True

        if not skip_inner_extraction:
            # FastMCP / JSON may pass booleans as strings. ``bool("false")`` is True in Python,
            # which incorrectly enabled the slow LLM ReAct extraction path.
            def _tool_bool(v: Any, default: bool = False) -> bool:
                if v is None:
                    return default
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    return v != 0
                if isinstance(v, str):
                    return v.strip().lower() in ("1", "true", "yes", "on")
                return default

            use_llm_extraction = _tool_bool(use_llm_for_extraction, False)

            if use_llm_extraction:
                progress.update("extraction", {"substep": "starting_llm_extraction"})
                from DiscoveryAgent.agents import DiscoveryAgent as DiscoveryAgentClass  # type: ignore
                from DiscoveryAgent.utils import get_tool_decorated_functions  # type: ignore
                from DiscoveryAgent.prompts.data_extraction import PREFIX, SUFFIX, FORMAT_INSTRUCTIONS  # type: ignore

                all_retrieval_tools = get_tool_decorated_functions(
                    str(DISCOVERY_AGENT_ROOT / "DiscoveryAgent" / "tools" / "retrieval.py")
                )
                tools = [
                    t for t in all_retrieval_tools
                    if getattr(t, "name", "") not in _PIPELINE_EXTRACTION_EXCLUDED_TOOLS
                ]
                extraction_agent = DiscoveryAgentClass(
                    tools,
                    model=model,
                    prefix=PREFIX,
                    suffix=SUFFIX,
                    format_instructions=FORMAT_INSTRUCTIONS,
                    max_iterations=24,
                    max_execution_time=420.0,
                ).agent
                human_prompt = (
                    f"Suggest the potential drug molecules for {disease} targeting the protein {protein}."
                )
                extraction_result = extraction_agent.invoke({"input": human_prompt})
                progress.update("extraction", {"substep": "llm_extraction_completed"})
                from DiscoveryAgent.utils import custom_serializer  # type: ignore

                with open(run_dir / "extraction_response.json", "w", encoding="utf-8") as f:
                    json.dump(extraction_result, f, indent=2, default=custom_serializer)

                import re as _re

                drug_name = None
                smiles = None
                uniprot_id = None
                fasta = None

                if "intermediate_steps" in extraction_result:
                    for step in extraction_result.get("intermediate_steps", []):
                        if len(step) >= 2:
                            action = step[0]
                            observation = step[1]
                            tool_name = None
                            tool_input = None
                            if hasattr(action, "tool"):
                                tool_name = action.tool
                                tool_input = action.tool_input
                            elif isinstance(action, str):
                                tm = _re.search(r"tool='([^']+)'", action)
                                im = _re.search(r"tool_input='([^']+)'", action)
                                if tm:
                                    tool_name = tm.group(1)
                                if im:
                                    tool_input = im.group(1)
                            if tool_name == "get_uniprot_ids" and observation:
                                if isinstance(observation, list) and len(observation) > 0:
                                    first = observation[0]
                                    if isinstance(first, (list, tuple)) and len(first) > 0:
                                        uniprot_id = first[0]
                                    elif isinstance(first, str):
                                        uniprot_id = first
                                elif isinstance(observation, str) and "P" in observation:
                                    mm = _re.search(r"['\"]([A-Z][0-9A-Z]{4,})['\"]", observation)
                                    if mm:
                                        uniprot_id = mm.group(1)
                            elif tool_name == "fetch_uniprot_fasta" and observation:
                                fasta = observation if isinstance(observation, str) else str(observation)
                            elif tool_name == "get_drug_smiles" and observation:
                                drug_name = tool_input
                                if isinstance(observation, str) and len(observation) > 10:
                                    smiles = observation

                from DiscoveryAgent.tools import retrieval as R

                if not uniprot_id:
                    ids = R.get_uniprot_ids.invoke({"protein_name": protein})
                    if isinstance(ids, str) or not ids:
                        return {"ok": False, "run_id": run_id2, "error": f"UniProt lookup failed: {ids}"}
                    uniprot_id = ids[0][0]

                if not fasta:
                    fasta = R.fetch_uniprot_fasta.invoke({"uniprot_id": uniprot_id}) or ""

                seq = _parse_fasta_to_sequence(fasta)

                if not drug_name or not smiles:
                    output_text = extraction_result.get("output", "")
                    patterns = [
                        r"([A-Z][a-z]+(?:inib|mab|nib|zole|tide|stat|clax|lib|zumab))\b",
                        r"drug[:\s]+([A-Z][a-z]+)",
                        r"found\s+([A-Z][a-z]+)",
                        r"identified\s+([A-Z][a-z]+)",
                    ]
                    for pattern in patterns:
                        match = _re.search(pattern, output_text)
                        if match:
                            potential_drug = match.group(1).strip()
                            test_smiles = R.get_drug_smiles.invoke({"drug_name": potential_drug})
                            if test_smiles and len(str(test_smiles)) > 10:
                                drug_name = potential_drug
                                smiles = str(test_smiles)
                                break

                if not drug_name or not smiles:
                    return {
                        "ok": False,
                        "run_id": run_id2,
                        "error": "Could not extract drug name from LLM response",
                        "extraction_output": extraction_result.get("output", "")[:500],
                    }

                extraction = {
                    "protein": protein,
                    "disease": disease,
                    "uniprot_id": uniprot_id,
                    "fasta": seq,
                    "drug_name": drug_name,
                    "SMILES": smiles,
                }
            else:
                try:
                    extraction = _extract_pipeline_context_fast(
                        protein=protein,
                        disease=disease,
                        progress=progress,
                    )
                except Exception as exc:
                    err_file = run_dir / "errors" / "extraction_failed.json"
                    _safe_json_dump(err_file, {"error": str(exc), "type": type(exc).__name__})
                    progress.update("extraction", {"substep": "failed", "error": str(exc)})
                    return {
                        "ok": False,
                        "run_id": run_id2,
                        "run_dir": str(run_dir),
                        "error": "extraction_failed",
                        "detail": str(exc),
                    }

                _safe_json_dump(
                    run_dir / "extraction_response.json",
                    {"mode": "deterministic_fast", "result": extraction},
                )

        _safe_json_dump(run_dir / "extraction.json", extraction)
        seq = extraction["fasta"]
        smiles = extraction["SMILES"]
        drug_name = extraction["drug_name"]
        uniprot_id = extraction["uniprot_id"]

        _extraction_mode = (
            "external_context"
            if skip_inner_extraction
            else ("llm" if use_llm_extraction else "deterministic_fast")
        )
        progress.update("extraction", {
            "substep": "completed",
            "mode": _extraction_mode,
            "uniprot_id": uniprot_id,
            "drug_name": drug_name,
            "smiles": smiles[:50] + "...",
        })

        # --- Pooling (REINVENT) ---
        progress.update("pooling", {"substep": "running_reinvent", "num_smiles": num_smiles})
        pool_result = _run_reinvent_pooling(
            run_dir=run_dir, initial_smiles=smiles, model=model, num_smiles=num_smiles
        )
        progress.update("pooling", {"substep": "completed", "ok": pool_result.get("ok", False)})
        _safe_json_dump(run_dir / "pooling_result.json", pool_result)

        pool_dir = run_dir / "pool"
        reinvent_csv = pool_dir / "Reinvent_sampling.csv"
        mol2mol_csv = pool_dir / "Mol2Mol_sampling.csv"

        if reinvent_csv.exists() or mol2mol_csv.exists():
            current_smiles_csv = pool_dir / "combined_candidates.csv"
            _combine_pool_csvs(pool_dir, current_smiles_csv)
        else:
            current_smiles_csv = pool_dir / "seed.csv"
            _write_smiles_csv(smiles, current_smiles_csv)

        try:
            import pandas as _pd
            _pool_count = len(_pd.read_csv(current_smiles_csv))
        except Exception:
            _pool_count = 0
        if _pool_count == 0:
            _safe_json_dump(run_dir / "errors" / "empty_pool.json", {
                "error": "Candidate pool is empty after REINVENT + canonicalization",
                "pool_dir": str(pool_dir),
                "reinvent_csv_exists": reinvent_csv.exists(),
                "mol2mol_csv_exists": mol2mol_csv.exists(),
            })
            progress.update("pooling", {"substep": "empty_pool_abort"})
            return {
                "ok": False,
                "run_id": run_id2,
                "run_dir": str(run_dir),
                "error": "empty_pool",
                "pool_dir": str(pool_dir),
            }

        _write_molecule_viz_csv(
            current_smiles_csv,
            run_dir / "viz" / "pool_candidates.png",
        )

        # --- Iterative loop ---
        artifacts: Dict[str, Any] = {
            "run_id": run_id2,
            "run_dir": str(run_dir),
            "extraction_json": str(run_dir / "extraction.json"),
            "iterations": [],
        }

        total_iterations = max(1, int(iterations))
        for i in range(total_iterations):
            is_last_iteration = (i == total_iterations - 1)
            progress.update(f"iteration_{i}", {
                "substep": "starting",
                "iteration": i,
                "total_iterations": total_iterations,
                "is_last": is_last_iteration,
            })

            iter_dir = run_dir / f"iter_{i:02d}"
            iter_dir.mkdir(parents=True, exist_ok=True)
            os.chdir(iter_dir)

            iter_pool_dir = iter_dir / "pool"
            iter_pool_dir.mkdir(parents=True, exist_ok=True)
            smiles_csv_raw = iter_pool_dir / "candidates_raw.csv"
            smiles_csv_iter = iter_pool_dir / "candidates.csv"
            _copy_into_run_dir(current_smiles_csv, smiles_csv_raw)

            validation = _validate_smiles_csv(smiles_csv_raw, smiles_csv_iter)
            num_candidates = validation["kept_rows"]

            if num_candidates == 0:
                _safe_json_dump(iter_dir / "errors" / "empty_candidates.json", {
                    "error": "No valid SMILES after standardization",
                    **validation,
                })
                artifacts["iterations"].append({
                    "iter": i,
                    "ok": False,
                    "error": "All candidate SMILES failed validation",
                    **validation,
                })
                progress.update(f"iteration_{i}_error", {
                    "substep": "empty_candidates",
                    **validation,
                })
                break

            progress.update(f"iteration_{i}_prediction", {
                "substep": "starting_affinity_and_admet",
                "num_candidates": num_candidates,
                "dropped_invalid": validation["dropped_rows"],
            })

            job_aff, job_admet = _run_prediction_jobs(
                jm=jm,
                iter_dir=iter_dir,
                smiles_csv=smiles_csv_iter,
                seq=seq,
                iteration=i,
                suffix="_before" if is_last_iteration else "",
            )

            job_statuses = _wait_for_jobs(
                jm=jm,
                job_ids=[job_aff.job_id, job_admet.job_id],
                progress=progress,
                progress_key=f"iteration_{i}_prediction",
            )

            progress.update(f"iteration_{i}_prediction", {
                "substep": "predictions_completed",
                "affinity_status": job_statuses[job_aff.job_id].get("status"),
                "admet_status": job_statuses[job_admet.job_id].get("status"),
            })

            affinity_out, admet_out = _find_prediction_outputs(iter_dir, smiles_csv_iter.name)

            if not admet_out or not admet_out.exists():
                progress.update(f"iteration_{i}_error", {
                    "substep": "missing_admet",
                    "error": "ADMET prediction required but output not found",
                })
                _safe_json_dump(iter_dir / "errors" / "missing_admet.json", {
                    "error": "ADMET is required but output file not found",
                    "admet_job": job_admet.__dict__,
                    "admet_status": job_statuses[job_admet.job_id],
                })
                artifacts["iterations"].append({
                    "iter": i,
                    "ok": False,
                    "error": "ADMET prediction required but failed. See errors/missing_admet.json",
                })
                break

            if not affinity_out or not affinity_out.exists():
                progress.update(f"iteration_{i}_error", {
                    "substep": "missing_affinity",
                    "error": "Affinity prediction output not found",
                })
                _safe_json_dump(iter_dir / "errors" / "missing_affinity.json", {
                    "error": "Affinity prediction output file not found",
                    "affinity_job": job_aff.__dict__,
                    "affinity_status": job_statuses[job_aff.job_id],
                })
                artifacts["iterations"].append({
                    "iter": i,
                    "ok": False,
                    "error": "Affinity prediction failed. See errors/missing_affinity.json",
                })
                break

            prop_dir = iter_dir / "property"
            if is_last_iteration:
                final_affinity = prop_dir / "affinity_before.csv"
                final_admet = prop_dir / "admet_before.csv"
            else:
                final_affinity = prop_dir / "affinity.csv"
                final_admet = prop_dir / "admet.csv"

            if affinity_out != final_affinity:
                shutil.copy(affinity_out, final_affinity)
            if admet_out != final_admet:
                shutil.copy(admet_out, final_admet)

            _write_molecule_viz_csv(
                final_affinity,
                iter_dir / "viz" / "candidates.png",
                legend_cols=["Affinity [pKd]"],
            )

            progress.update(f"iteration_{i}_scoring", {"substep": "completed"})

            progress.update(f"iteration_{i}_refinement", {"substep": "starting_llm_refinement"})
            refinement_dir = iter_dir / "refinement"
            refinement_dir.mkdir(parents=True, exist_ok=True)
            refinement_csv = refinement_dir / "refinement.csv"
            
            _refine_smiles(smiles_csv_iter, refinement_csv, protein=protein, model=model)
            progress.update(f"iteration_{i}_refinement", {"substep": "completed"})

            if is_last_iteration:
                updated_smiles_csv_raw = refinement_dir / "updated_smiles_raw.csv"
                updated_smiles_csv = refinement_dir / "updated_smiles_temp.csv"
                _extract_updated_smiles(refinement_csv, updated_smiles_csv_raw)
                after_validation = _validate_smiles_csv(updated_smiles_csv_raw, updated_smiles_csv)
                progress.update(f"iteration_{i}_after_prediction", {
                    "substep": "starting_after_predictions",
                    "num_candidates": after_validation["kept_rows"],
                    "dropped_invalid": after_validation["dropped_rows"],
                })

                if after_validation["kept_rows"] == 0:
                    _safe_json_dump(iter_dir / "errors" / "empty_after_candidates.json", {
                        "error": "All refined SMILES failed validation",
                        **after_validation,
                    })
                    progress.update(f"iteration_{i}_after_prediction", {
                        "substep": "skipped_empty_after",
                        **after_validation,
                    })
                    job_aff_after = None
                    job_admet_after = None
                else:
                    job_aff_after, job_admet_after = _run_prediction_jobs(
                        jm=jm,
                        iter_dir=iter_dir,
                        smiles_csv=updated_smiles_csv,
                        seq=seq,
                        iteration=i,
                        suffix="_after",
                    )

                if job_aff_after is not None and job_admet_after is not None:
                    _wait_for_jobs(
                        jm=jm,
                        job_ids=[job_aff_after.job_id, job_admet_after.job_id],
                        progress=progress,
                        progress_key=f"iteration_{i}_after_prediction",
                    )

                    affinity_after, admet_after = _find_prediction_outputs(iter_dir, updated_smiles_csv.name)

                    if affinity_after and affinity_after.exists():
                        shutil.copy(affinity_after, prop_dir / "affinity_after.csv")
                    if admet_after and admet_after.exists():
                        shutil.copy(admet_after, prop_dir / "admet_after.csv")

                    progress.update(f"iteration_{i}_after_prediction", {
                        "substep": "completed",
                        "affinity_after_exists": (prop_dir / "affinity_after.csv").exists(),
                        "admet_after_exists": (prop_dir / "admet_after.csv").exists(),
                    })

                    aff_after_viz = prop_dir / "affinity_after.csv"
                    if aff_after_viz.exists():
                        _write_molecule_viz_csv(
                            aff_after_viz,
                            iter_dir / "viz" / "candidates_after.png",
                            legend_cols=["Affinity [pKd]"],
                        )

            if is_last_iteration:
                _cleanup_intermediate_files(prop_dir, [
                    "affinity_before.csv", "admet_before.csv",
                    "affinity_after.csv", "admet_after.csv",
                ])
            else:
                _cleanup_intermediate_files(prop_dir, [
                    "affinity.csv", "admet.csv",
                ])
            
            _cleanup_intermediate_files(refinement_dir, ["refinement.csv"])

            iter_artifact = {
                "iter": i,
                "ok": True,
                "is_last": is_last_iteration,
                "input_smiles_csv": str(smiles_csv_iter),
                "affinity_job": job_aff.__dict__,
                "admet_job": job_admet.__dict__,
                "refinement_csv": str(refinement_csv),
            }

            if is_last_iteration:
                iter_artifact.update({
                    "affinity_before_csv": str(prop_dir / "affinity_before.csv"),
                    "admet_before_csv": str(prop_dir / "admet_before.csv"),
                    "affinity_after_csv": str(prop_dir / "affinity_after.csv"),
                    "admet_after_csv": str(prop_dir / "admet_after.csv"),
                })
            else:
                iter_artifact.update({
                    "affinity_csv": str(prop_dir / "affinity.csv"),
                    "admet_csv": str(prop_dir / "admet.csv"),
                })

            artifacts["iterations"].append(iter_artifact)

            # Next iteration input - extract updated SMILES from refinement.csv
            # This creates a temp file that will be copied to next iter's pool/candidates.csv
            if not is_last_iteration:
                next_iter_smiles = iter_dir / "next_iter_candidates.csv"
                _extract_updated_smiles(refinement_csv, next_iter_smiles)
                current_smiles_csv = next_iter_smiles

        # --- Boltz structure generation + execution ---
        # --- Boltz: Always generate configs, optionally run structure prediction ---
        # Selection criteria: Oprea filter + 2/3 drug rules + pKd > min_pkd + QED >= min_qed
        boltz_jobs: List[Dict[str, Any]] = []
        boltz_yamls: List[str] = []
        smiles_for_boltz: List[str] = []
        
        if artifacts["iterations"]:
            progress.update("boltz", {"substep": "selecting_candidates"})

            last_iter = artifacts["iterations"][-1]
            if not last_iter.get("ok"):
                progress.update("boltz", {"substep": "skipped_due_to_iteration_failure"})
            else:
                # Get affinity_after and admet_after from last iteration
                affinity_after_csv = last_iter.get("affinity_after_csv")
                admet_after_csv = last_iter.get("admet_after_csv")
                
                # Define intermediate files for cleanup
                merged_csv = run_dir / "boltz_merged.csv"
                scored_csv = run_dir / "boltz_scored.csv"
                final_candidates_csv = run_dir / "boltz_candidates.csv"
                
                if affinity_after_csv and admet_after_csv and \
                   Path(affinity_after_csv).exists() and Path(admet_after_csv).exists():
                    try:
                        import pandas as pd
                        
                        # Merge affinity + admet for scoring
                        _merge_affinity_admet(
                            Path(affinity_after_csv), 
                            Path(admet_after_csv), 
                            merged_csv
                        )
                        
                        # Check if merged has data (more than just header)
                        df_merged = pd.read_csv(merged_csv)
                        if len(df_merged) == 0:
                            progress.update("boltz", {
                                "substep": "no_data_after_merge",
                                "message": "No candidates found after merging affinity and ADMET"
                            })
                        else:
                            # Score candidates (adds drug-likeness columns: oprea, lipinski, veber, ghose, QED)
                            _score_candidates(merged_csv, scored_csv)
                            
                            # Select final candidates with filters from config:
                            # - Oprea lead-like = True
                            # - At least 2 of 3 drug rules (Lipinski, Veber, Ghose)
                            # - pKd > min_pkd (from config)
                            # - QED >= min_qed (from config)
                            _select_final_candidates(
                                scored_csv,
                                final_candidates_csv,
                                top_k=int(boltz_top_k),
                                min_pkd=float(min_pkd),
                                min_qed=float(min_qed),
                            )
                            
                            # Read selected candidates
                            df_selected = pd.read_csv(final_candidates_csv)
                            smiles_for_boltz = df_selected["SMILES"].dropna().astype(str).tolist()

                            _write_molecule_viz_csv(
                                final_candidates_csv,
                                run_dir / "viz" / "boltz_candidates.png",
                                legend_cols=["Affinity [pKd]", "QED"],
                            )
                            
                            progress.update("boltz", {
                                "substep": "candidates_selected",
                                "passed_filters": len(smiles_for_boltz),
                                "filter_min_qed": min_qed,
                                "filter_min_pkd": min_pkd,
                            })
                        
                    except Exception as e:
                        _safe_json_dump(run_dir / "errors" / "boltz_selection.json", {"error": str(e)})
                    finally:
                        # Always clean up intermediate files - only keep boltz_candidates.csv
                        if merged_csv.exists():
                            merged_csv.unlink()
                        if scored_csv.exists():
                            scored_csv.unlink()

                # Always generate YAML configs (even if run_boltz=False)
                progress.update("boltz", {
                    "substep": "generating_yamls",
                    "num_candidates": len(smiles_for_boltz),
                })

                if smiles_for_boltz:
                    boltz_yamls = _generate_boltz_yamls(
                        run_dir=run_dir,
                        protein_sequence=seq,
                        smiles_list=smiles_for_boltz
                    )
                    progress.update("boltz", {
                        "substep": "yamls_generated",
                        "num_yamls": len(boltz_yamls),
                        "run_boltz": run_boltz,
                    })

                    # Only run Boltz structure prediction if run_boltz=True
                    if run_boltz:
                        progress.update("boltz", {
                            "substep": "running_boltz_jobs",
                            "num_yamls": len(boltz_yamls),
                        })

                        extra_args = json.loads(boltz_extra_args_json)
                        for idx, yp in enumerate(boltz_yamls):
                            progress.update("boltz", {
                                "substep": f"running_boltz_{idx+1}_of_{len(boltz_yamls)}",
                                "yaml": yp,
                            })

                            job = jm.start(
                                name="boltz",
                                command=[
                                    *_python_worker_prefix(),
                                    str(DISCOVERY_AGENT_ROOT / "mcp_agent.py"),
                                    "_worker",
                                    "--kind",
                                    "boltz",
                                    "--yaml_path",
                                    yp,
                                    "--out_dir",
                                    str(run_dir),
                                    "--extra_args_json",
                                    json.dumps(extra_args),
                                ],
                                cwd=run_dir,
                                env={"PYTHONPATH": str(DISCOVERY_AGENT_ROOT)},
                            )

                            # Wait for each Boltz job
                            while jm.status(job.job_id).get("status") == "running":
                                time.sleep(5)
                            boltz_jobs.append(job.__dict__)

                        progress.update("boltz", {"substep": "completed", "num_jobs": len(boltz_jobs)})
                    else:
                        progress.update("boltz", {"substep": "configs_only_structure_skipped"})
                else:
                    progress.update("boltz", {"substep": "no_candidates_passed_filters"})

        artifacts["boltz"] = {"yamls": boltz_yamls, "jobs": boltz_jobs}
        progress.update("pipeline_complete", {"total_iterations": len(artifacts["iterations"])})
        _safe_json_dump(run_dir / "summary.json", {"ok": True, **artifacts})
        return {"ok": True, **artifacts}

    @mcp.tool(name="DiscoveryAgent_qna")
    def discovery_agent_qna(
        question: str,
        protein: Optional[str] = None,
        disease: Optional[str] = None,
        model: str = DEFAULT_LLM_MODEL,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Q&A mode: Ask questions about drug discovery, proteins, diseases, etc.
        Uses RAG (Retrieval-Augmented Generation) with downloaded research papers.

        Parameters:
        - question: The question to answer (use "_init_papers_" to just download papers)
        - protein: Target protein name (for paper search)
        - disease: Disease name (for paper search)
        - model: LLM model on NVIDIA NIM (default from configs/tool_globals.LLM_MODEL)
        - run_id: Run ID for storing papers (creates new if not provided)

        If protein and disease are provided, relevant papers will be downloaded
        to runs/<run_id>/papers/ directory.

        This is a standalone mode separate from the full pipeline.
        """
        _load_api_keys_fallback()
        _ensure_discovery_agent_importable()

        # Create or use existing run directory for Q&A session
        run_root = DISCOVERY_AGENT_ROOT / "runs"
        run_id2, run_dir = _ensure_run_dir(run_root, run_id)
        papers_dir = run_dir / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)

        # Save Q&A session config
        if not (run_dir / "qna_config.json").exists():
            _safe_json_dump(
                run_dir / "qna_config.json",
                {
                    "mode": "qna",
                    "protein": protein,
                    "disease": disease,
                    "model": model,
                    "created_at": _now_utc_iso(),
                },
            )

        from DiscoveryAgent.agents import DiscoveryAgent as DiscoveryAgentClass  # type: ignore
        from DiscoveryAgent.utils import get_tool_decorated_functions  # type: ignore
        from DiscoveryAgent.prompts.question_answering import PREFIX, SUFFIX, FORMAT_INSTRUCTIONS  # type: ignore
        import configs.tool_globals as tool_globals  # type: ignore

        # Override PAPER_DIR to use run-specific directory
        original_paper_dir = tool_globals.PAPER_DIR
        tool_globals.PAPER_DIR = str(papers_dir)

        # Change working directory to run_dir
        original_cwd = os.getcwd()
        os.chdir(run_dir)

        try:
            import importlib
            import DiscoveryAgent.tools.retrieval as retrieval_module
            
            # Reload retrieval module to pick up the new PAPER_DIR
            importlib.reload(retrieval_module)
            
            # Download papers if protein/disease specified and papers dir is empty
            papers_downloaded = []
            existing_papers = list(papers_dir.glob("*.pdf"))
            if protein and disease and not existing_papers:
                try:
                    query = f"{disease} {protein} treatment therapy year: \"2022-\""
                    papers_downloaded = retrieval_module.download_relevant_papers(query)
                except Exception as e:
                    _safe_json_dump(run_dir / "errors" / "paper_download.json", {"error": str(e)})

            # Reload again after download to ensure question_answering sees the papers
            importlib.reload(retrieval_module)
            
            # If this is just an init call to download papers, return early
            if question == "_init_papers_":
                return {
                    "ok": True,
                    "run_id": run_id2,
                    "run_dir": str(run_dir),
                    "papers_downloaded": papers_downloaded,
                    "answer": f"Papers downloaded: {len(papers_downloaded)}",
                }
            
            # Get retrieval tools (includes question_answering which does RAG)
            tools = get_tool_decorated_functions(str(DISCOVERY_AGENT_ROOT / "DiscoveryAgent" / "tools" / "retrieval.py"))
            tool_names = [tool.name for tool in tools]
            tool_desc = [tool.description for tool in tools]

            qna_agent = DiscoveryAgentClass(
                tools,
                model=model,
                prefix=PREFIX,
                suffix=SUFFIX,
                format_instructions=FORMAT_INSTRUCTIONS,
            ).agent

            input_data = {
                "input": question,
                "tools": tools,
                "tool_names": tool_names,
                "tool_desc": tool_desc,
            }

            result = qna_agent.invoke(input_data)
            
            # Log Q&A interaction
            qna_log = run_dir / "qna_log.jsonl"
            with open(qna_log, "a") as f:
                f.write(json.dumps({
                    "timestamp": _now_utc_iso(),
                    "question": question,
                    "answer": result.get("output", str(result)),
                    "papers_downloaded": len(papers_downloaded),
                }) + "\n")

            return {
                "ok": True,
                "run_id": run_id2,
                "run_dir": str(run_dir),
                "question": question,
                "answer": result.get("output", str(result)),
                "papers_downloaded": papers_downloaded,
            }
        except Exception as e:
            return {
                "ok": False,
                "run_id": run_id2,
                "run_dir": str(run_dir),
                "question": question,
                "error": str(e),
            }
        finally:
            # Restore original PAPER_DIR and working directory
            tool_globals.PAPER_DIR = original_paper_dir
            os.chdir(original_cwd)

    @mcp.tool(name="DiscoveryAgent_run_status")
    def discovery_agent_run_status(run_id: str) -> Dict[str, Any]:
        """Get the current status and progress of a pipeline run."""
        run_dir = DISCOVERY_AGENT_ROOT / "runs" / run_id
        status_file = run_dir / "status.json"

        if not status_file.exists():
            return {"ok": False, "run_id": run_id, "error": "Status file not found"}

        try:
            status = _safe_json_load(status_file)
            return {"ok": True, "run_id": run_id, **status}
        except Exception as e:
            return {"ok": False, "run_id": run_id, "error": str(e)}

    @mcp.tool(name="DiscoveryAgent_list_runs")
    def discovery_agent_list_runs() -> Dict[str, Any]:
        """List all pipeline runs with their status."""
        runs_dir = DISCOVERY_AGENT_ROOT / "runs"
        if not runs_dir.exists():
            return {"ok": True, "runs": []}

        runs = []
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue

            run_info = {"run_id": run_dir.name}

            # Try to get status
            status_file = run_dir / "status.json"
            if status_file.exists():
                try:
                    status = _safe_json_load(status_file)
                    run_info["current_step"] = status.get("current_step", "unknown")
                    run_info["started_at"] = status.get("started_at")
                    run_info["last_updated"] = status.get("last_updated")
                except Exception:
                    run_info["current_step"] = "error_reading_status"

            # Try to get config
            config_file = run_dir / "run_config.json"
            if config_file.exists():
                try:
                    config = _safe_json_load(config_file)
                    run_info["protein"] = config.get("protein")
                    run_info["drug_name"] = config.get("drug_name")
                except Exception:
                    pass

            runs.append(run_info)

        return {"ok": True, "runs": runs[:20]}  # Limit to 20 most recent

    @mcp.tool(name="DiscoveryAgent_job_status")
    def discovery_agent_job_status(run_id: str, job_id: str) -> Dict[str, Any]:
        """Get job status for a run."""
        run_dir = DISCOVERY_AGENT_ROOT / "runs" / run_id
        jm = JobManager(run_dir)
        return jm.status(job_id)

    @mcp.tool(name="DiscoveryAgent_job_logs")
    def discovery_agent_job_logs(run_id: str, job_id: str, max_bytes: int = 100_000) -> Dict[str, Any]:
        """Tail job logs for a run."""
        run_dir = DISCOVERY_AGENT_ROOT / "runs" / run_id
        jm = JobManager(run_dir)
        return jm.tail_logs(job_id, max_bytes=max_bytes)

    @mcp.tool(name="DiscoveryAgent_job_cancel")
    def discovery_agent_job_cancel(run_id: str, job_id: str) -> Dict[str, Any]:
        """Cancel a job for a run."""
        run_dir = DISCOVERY_AGENT_ROOT / "runs" / run_id
        jm = JobManager(run_dir)
        return jm.cancel(job_id)

    return mcp


def main() -> int:
    # Worker entrypoint: `python mcp_agent.py _worker --kind ...`
    # Suppress stderr at OS level BEFORE any imports for workers
    if len(sys.argv) > 1 and sys.argv[1] == "_worker":
        import os
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        # os.dup2(devnull_fd, 2)  # Redirect stderr to /dev/null at OS level
        os.close(devnull_fd)
        return _run_worker_from_argv(sys.argv[1:])

    # Check for Q&A mode from command line
    if len(sys.argv) > 1 and sys.argv[1] == "_qna":
        # Interactive Q&A mode
        _load_api_keys_fallback()
        _ensure_discovery_agent_importable()

        print("=" * 60)
        print("DiscoveryAgent Q&A Mode (RAG-based)")
        print("=" * 60)
        print("\nThis mode uses downloaded research papers to answer questions.")
        print("Type 'quit' or 'exit' to leave.\n")

        # Ask if user wants to download papers
        protein = input("Enter protein name (or press Enter to skip): ").strip() or None
        drug_name = input("Enter drug name (or press Enter to skip): ").strip() or None

        if protein and drug_name:
            print(f"\nDownloading papers for {drug_name} + {protein}...")
            try:
                from DiscoveryAgent.tools.retrieval import download_relevant_papers
                query = f"{drug_name} {protein} year: \"2022-\""
                papers = download_relevant_papers(query)
                print(f"Downloaded {len(papers)} papers.\n")
            except Exception as e:
                print(f"Paper download failed: {e}\n")

        # Setup Q&A agent
        from DiscoveryAgent.agents import DiscoveryAgent as DiscoveryAgentClass
        from DiscoveryAgent.utils import get_tool_decorated_functions
        from DiscoveryAgent.prompts.question_answering import PREFIX, SUFFIX, FORMAT_INSTRUCTIONS

        tools = get_tool_decorated_functions(str(DISCOVERY_AGENT_ROOT / "DiscoveryAgent" / "tools" / "retrieval.py"))
        tool_names = [tool.name for tool in tools]
        tool_desc = [tool.description for tool in tools]

        qna_agent = DiscoveryAgentClass(
            tools,
            model=DEFAULT_LLM_MODEL,
            prefix=PREFIX,
            suffix=SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
        ).agent

        while True:
            try:
                question = input("\nYour question: ").strip()
                if question.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break
                if not question:
                    continue

                input_data = {
                    "input": question,
                    "tools": tools,
                    "tool_names": tool_names,
                    "tool_desc": tool_desc,
                }

                print("\nThinking...")
                result = qna_agent.invoke(input_data)
                print("\n" + "=" * 40)
                print("Answer:", result.get("output", str(result)))
                print("=" * 40)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

        return 0

    # Server entrypoint (stdio)
    # Suppress stderr to prevent library warnings from breaking MCP JSON-RPC protocol
    import io
    import warnings
    warnings.filterwarnings("ignore")
    sys.stderr = io.StringIO()  # Redirect stderr to null
    
    _load_api_keys_fallback()
    mcp = _make_mcp()
    # show_banner=False is critical for stdio transport - banner output breaks JSON-RPC protocol
    mcp.run(show_banner=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
