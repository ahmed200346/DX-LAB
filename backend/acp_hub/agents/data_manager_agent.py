"""
ACP wrapper for Intelligent Target Discovery (Data Manager) — HTTP to ITD /generate.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from acp_hub.agents.base_agent import BaseAgent
from acp_hub.serveurs.agent_registry import AgentConfig
from acp_hub.settings.config import DATA_MANAGER_URL

logger = logging.getLogger(__name__)

_instance: "DataManagerAgent | None" = None


class DataManagerAgent(BaseAgent):
    """Proxies to ITD FastAPI POST /generate."""

    def __init__(self):
        super().__init__(
            name="data_manager",
            description=(
                "Data handler: biomedical literature retrieval, embeddings, vector store, "
                "and target/chemical context (Intelligent Target Discovery API)."
            ),
            capabilities=[
                "literature_retrieval",
                "vector_search",
                "target_resolution",
                "evidence_validation",
            ],
        )

    async def run(self, input_text: str, context: Any = None) -> Any:
        start = time.time()
        self.logger.info("data_manager — forwarding to ITD /generate")

        payload: dict[str, Any]
        try:
            payload = json.loads(input_text) if input_text.strip().startswith("{") else {}
        except json.JSONDecodeError:
            payload = {}

        if not payload.get("prompt"):
            payload["prompt"] = (
                payload.get("query")
                or payload.get("q")
                or input_text.strip()
            )

        body = {
            "prompt": str(payload.get("prompt", "")).strip(),
            "top_k": int(payload.get("top_k", 10)),
            "data_types": payload.get("data_types", ["text", "pdf"]),
            "intent": payload.get("intent", "refresh"),
        }
        if not body["prompt"]:
            err = json.dumps({"status": "error", "error": "empty_prompt"}, ensure_ascii=False)
            self.update_metrics(False, time.time() - start)
            return err

        url = f"{DATA_MANAGER_URL.rstrip('/')}/generate"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            self.logger.exception("data_manager HTTP error: %s", e)
            self.update_metrics(False, time.time() - start)
            return json.dumps(
                {"status": "error", "error": str(e), "url": url},
                ensure_ascii=False,
                indent=2,
            )

        self.update_metrics(True, time.time() - start)
        # Return structured subset for downstream discoverer / reporter
        out = {
            "status": "success" if data.get("success") else "error",
            "session_id": data.get("session_id", ""),
            "targets": data.get("targets", []),
            "sources": data.get("sources", []),
            "source_count": data.get("source_count", 0),
            "validation_score": data.get("validation_score", 0.0),
            "error": data.get("error"),
        }
        return json.dumps(out, ensure_ascii=False, indent=2)


def get_agent_config() -> AgentConfig:
    global _instance
    if _instance is None:
        _instance = DataManagerAgent()
    a = _instance
    return AgentConfig(
        name=a.name,
        description=a.description,
        handler=a.run,
        capabilities=a.capabilities,
    )
