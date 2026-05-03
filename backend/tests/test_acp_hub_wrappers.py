"""
Smoke tests for ACP hub wrapper agents (mocked HTTP / subprocess).
Run from `backend/`:

    python -m pytest tests/test_acp_hub_wrappers.py -q
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.mark.asyncio
async def test_data_manager_forwards_to_generate():
    from acp_hub.agents.data_manager_agent import DataManagerAgent

    fake = {
        "success": True,
        "session_id": "abc",
        "targets": [{"gene": "EGFR"}],
        "sources": [],
        "source_count": 1,
        "validation_score": 0.9,
    }

    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=fake)
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("acp_hub.agents.data_manager_agent.httpx.AsyncClient", return_value=mock_client):
        agent = DataManagerAgent()
        out = await agent.run(json.dumps({"query": "test query", "top_k": 5}))

    data = json.loads(out)
    assert data["status"] == "success"
    assert data["session_id"] == "abc"
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "/generate" in args[0]
    assert kwargs["json"]["prompt"] == "test query"


@pytest.mark.asyncio
async def test_printer_3d_forwards_to_submit():
    from acp_hub.agents.printer_3d_agent import Printer3DAgent

    fake = {"success": True, "data": {"metrics": {}}}
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=fake)
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("acp_hub.agents.printer_3d_agent.httpx.AsyncClient", return_value=mock_client):
        agent = Printer3DAgent()
        out = await agent.run(json.dumps({"description": "aspirin"}))

    data = json.loads(out)
    assert data["success"] is True
    body = mock_client.post.call_args.kwargs["json"]
    assert body["description"] == "aspirin"


@pytest.mark.asyncio
async def test_discoverer_requires_root():
    from acp_hub.agents import discoverer_agent

    with patch.object(discoverer_agent, "DISCOVERY_AGENT_ROOT", ""):
        agent = discoverer_agent.DiscovererAgent()
        out = await agent.run(
            json.dumps({"protein": "EGFR", "disease": "cancer", "tier": "lite"})
        )
    data = json.loads(out)
    assert data["status"] == "error"
