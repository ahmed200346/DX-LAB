"""
ACP hub entrypoint — run from repo `backend/` directory:

    python -m acp_hub.main

Requires PYTHONPATH to include `backend` (the parent of `acp_hub`), which `python -m` does when cwd is `backend/`.
"""

from __future__ import annotations

import atexit
import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from acp_hub.settings.config import (
    ACP_SERVER_HOST,
    ACP_SERVER_PORT,
    LOG_FORMAT,
    LOG_LEVEL,
    ensure_output_dirs,
)


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def register_agents() -> None:
    from acp_hub.serveurs.agent_registry import registry
    from acp_hub.agents.data_manager_agent import get_agent_config as get_data_manager_config
    from acp_hub.agents.discoverer_agent import get_agent_config as get_discoverer_config
    from acp_hub.agents.executor_agent import get_agent_config as get_executor_config
    from acp_hub.agents.planner_agent import get_agent_config as get_planner_config
    from acp_hub.agents.printer_3d_agent import get_agent_config as get_printer_3d_config

    for get_cfg in (
        get_executor_config,
        get_planner_config,
        get_data_manager_config,
        get_discoverer_config,
        get_printer_3d_config,
    ):
        registry.register(get_cfg())

    logging.getLogger(__name__).info("Agents registered: %s", registry.list_agent_names())


def register_shutdown_hooks() -> None:
    logger = logging.getLogger(__name__)

    def _save_on_exit() -> None:
        logger.info("Shutdown — saving session metrics...")
        try:
            from acp_hub.metrics.metrics_logger import metrics_logger

            session_path = metrics_logger.save_session_log()
            logger.info("Session log saved → %s", session_path)
            report = metrics_logger.generate_report()
            logger.info("Session report: %s", report)
        except Exception as e:
            logger.error("Session log save failed: %s", e)

        try:
            from acp_hub.agents.executor_agent import _system_collector as exec_sys

            sys_path = exec_sys.save_metrics()
            logger.info("Executor system metrics → %s", sys_path)
        except Exception as e:
            logger.error("Executor metrics save failed: %s", e)

        try:
            from acp_hub.agents.planner_agent import _system_collector as plan_sys

            sys_path = plan_sys.save_metrics()
            logger.info("Planner system metrics → %s", sys_path)
        except Exception as e:
            logger.error("Planner metrics save failed: %s", e)

    atexit.register(_save_on_exit)
    logger.info("Shutdown hooks registered")


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("  DX-LAB ACP multi-agent hub")
    logger.info("=" * 60)

    ensure_output_dirs()
    register_agents()
    register_shutdown_hooks()

    from acp_hub.serveurs.acp_server import create_acp_server, start_server

    server = create_acp_server()
    logger.info("ACP server http://%s:%s", ACP_SERVER_HOST, ACP_SERVER_PORT)
    logger.info("  GET  http://%s:%s/agents", ACP_SERVER_HOST, ACP_SERVER_PORT)
    logger.info("  POST http://%s:%s/runs", ACP_SERVER_HOST, ACP_SERVER_PORT)
    logger.info("=" * 60)
    start_server(server)


if __name__ == "__main__":
    main()
