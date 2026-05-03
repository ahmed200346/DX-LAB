"""
ACP wrapper for Virtual Drug Discovery Lab (3D printer) — HTTP POST /api/submit.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from acp_hub.agents.base_agent import BaseAgent
from acp_hub.serveurs.agent_registry import AgentConfig
from acp_hub.settings.config import PRINTER_3D_URL

logger = logging.getLogger(__name__)

_instance: "Printer3DAgent | None" = None


class Printer3DAgent(BaseAgent):
    """Proxies to Flask 3D printer /api/submit."""

    def __init__(self):
        super().__init__(
            name="printer_3d",
            description=(
                "3D molecular structure generation and metrics (RDKit / ESMFold / DiffDock pipeline)."
            ),
            capabilities=["structure_generation", "molecular_visualization", "docking"],
        )

    async def run(self, input_text: str, context: Any = None) -> Any:
        start = time.time()
        self.logger.info("printer_3d — forwarding to Flask /api/submit")

        description = input_text.strip()
        try:
            obj = json.loads(input_text)
            if isinstance(obj, dict):
                description = (
                    obj.get("description")
                    or obj.get("query")
                    or obj.get("prompt")
                    or description
                )
        except json.JSONDecodeError:
            pass

        if not description:
            self.update_metrics(False, time.time() - start)
            return json.dumps({"success": False, "error": "empty_description"}, ensure_ascii=False)

        url = f"{PRINTER_3D_URL.rstrip('/')}/api/submit"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
                resp = await client.post(url, json={"description": description})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            self.logger.exception("printer_3d HTTP error: %s", e)
            self.update_metrics(False, time.time() - start)
            return json.dumps({"success": False, "error": str(e), "url": url}, ensure_ascii=False, indent=2)

        self.update_metrics(True, time.time() - start)
        return json.dumps(data, ensure_ascii=False, indent=2)


def get_agent_config() -> AgentConfig:
    global _instance
    if _instance is None:
        _instance = Printer3DAgent()
    a = _instance
    return AgentConfig(
        name=a.name,
        description=a.description,
        handler=a.run,
        capabilities=a.capabilities,
    )
