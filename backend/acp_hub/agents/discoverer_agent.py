"""
ACP wrapper for Advanced-AI-Project DiscoveryAgent — subprocess to run_discovery_agent.py.
Optional external context (from Data Manager) via DISCOVERY_USE_EXTERNAL_CONTEXT + JSON file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from acp_hub.agents.base_agent import BaseAgent
from acp_hub.serveurs.agent_registry import AgentConfig
from acp_hub.settings.config import DISCOVERY_AGENT_ROOT, get_agent_output_dir

logger = logging.getLogger(__name__)

_instance: "DiscovererAgent | None" = None


def _lite_config() -> dict[str, Any]:
    return {
        "iterations": 1,
        "num_smiles": 2,
        "run_boltz": False,
        "boltz_top_k": 1,
    }


def _full_config() -> dict[str, Any]:
    return {
        "iterations": 2,
        "num_smiles": 2,
        "run_boltz": False,
        "boltz_top_k": 2,
    }


def _build_external_context_path(bundle: dict[str, Any], run_id: str) -> Path | None:
    """If bundle has enough fields, write JSON for DiscoveryAgent Phase-2 hook."""
    smiles = (bundle.get("SMILES") or bundle.get("smiles") or bundle.get("seed_smiles") or "").strip()
    fasta = (bundle.get("fasta") or bundle.get("fasta_sequence") or "").strip()
    uniprot = (bundle.get("uniprot_id") or bundle.get("uniprot") or "").strip()
    drug_name = (bundle.get("drug_name") or bundle.get("drug") or "seed").strip()
    protein = (bundle.get("protein") or "").strip()
    disease = (bundle.get("disease") or "").strip()
    if not smiles or not fasta:
        return None
    out = {
        "protein": protein,
        "disease": disease,
        "SMILES": smiles,
        "drug_name": drug_name,
        "uniprot_id": uniprot or None,
        "fasta": fasta,
    }
    p = get_agent_output_dir("discoverer") / "results" / f"context_{run_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


class DiscovererAgent(BaseAgent):
    """Runs DiscoveryAgent pipeline via subprocess (same host)."""

    def __init__(self):
        super().__init__(
            name="discoverer",
            description=(
                "Molecular discovery pipeline: extraction context, REINVENT pooling, "
                "affinity/ADMET, optional Boltz (Advanced-AI-Project)."
            ),
            capabilities=[
                "molecule_generation",
                "affinity_prediction",
                "admet",
                "structure_prediction",
            ],
        )

    async def run(self, input_text: str, context: Any = None) -> Any:
        start = time.time()
        root = DISCOVERY_AGENT_ROOT.strip()
        if not root or not Path(root).is_dir():
            self.update_metrics(False, time.time() - start)
            return json.dumps(
                {
                    "status": "error",
                    "error": "DISCOVERY_AGENT_ROOT is not set or not a directory",
                    "hint": "Set env DISCOVERY_AGENT_ROOT to Advanced-AI-Project repo root",
                },
                ensure_ascii=False,
                indent=2,
            )

        root_path = Path(root).resolve()
        runner = root_path / "run_discovery_agent.py"
        if not runner.is_file():
            self.update_metrics(False, time.time() - start)
            return json.dumps(
                {"status": "error", "error": f"run_discovery_agent.py not found under {root_path}"},
                ensure_ascii=False,
                indent=2,
            )

        try:
            payload = json.loads(input_text) if input_text.strip().startswith("{") else {}
        except json.JSONDecodeError:
            payload = {}

        protein = (payload.get("protein") or "").strip()
        disease = (payload.get("disease") or "").strip()
        tier = (payload.get("tier") or "lite").strip().lower()
        run_id = (payload.get("run_id") or f"acp_{int(time.time())}").strip()
        context_bundle = payload.get("context_bundle")

        if not protein or not disease:
            self.update_metrics(False, time.time() - start)
            return json.dumps(
                {
                    "status": "error",
                    "error": "discoverer requires JSON with 'protein' and 'disease'",
                },
                ensure_ascii=False,
                indent=2,
            )

        cfg: dict[str, Any] = {
            "run_id": run_id,
            "protein": protein,
            "disease": disease,
            "model": payload.get("model", "moonshotai/kimi-k2.6"),
        }
        cfg.update(_lite_config() if tier == "lite" else _full_config())
        cfg.update({k: v for k, v in payload.items() if k in cfg or k in (
            "min_qed", "min_pkd", "boltz_extra_args_json",
        )})

        cfg_path = get_agent_output_dir("discoverer") / "results" / f"{run_id}_pipeline.yaml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

        env = os.environ.copy()
        ext_path: Path | None = None
        if isinstance(context_bundle, dict):
            ext_path = _build_external_context_path(context_bundle, run_id)
            if ext_path is not None:
                env["DISCOVERY_USE_EXTERNAL_CONTEXT"] = "1"
                env["DISCOVERY_CONTEXT_JSON_PATH"] = str(ext_path)

        cmd = [sys.executable, str(runner), "-c", str(cfg_path), "--protein", protein, "--disease", disease]
        self.logger.info("discoverer — running: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(root_path),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode(errors="replace")[-8000:]
        stderr = stderr_b.decode(errors="replace")[-8000:]

        ok = proc.returncode == 0
        self.update_metrics(ok, time.time() - start)

        runs_dir = root_path / "runs"
        latest = None
        if runs_dir.is_dir():
            sub = sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
            latest = str(sub[0]) if sub else None

        return json.dumps(
            {
                "status": "success" if ok else "error",
                "returncode": proc.returncode,
                "run_id": run_id,
                "config_path": str(cfg_path),
                "latest_run_dir": latest,
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            },
            ensure_ascii=False,
            indent=2,
        )


def get_agent_config() -> AgentConfig:
    global _instance
    if _instance is None:
        _instance = DiscovererAgent()
    a = _instance
    return AgentConfig(
        name=a.name,
        description=a.description,
        handler=a.run,
        capabilities=a.capabilities,
    )
