"""
Point d'entrée principal du système multi-agent ACP.
Charge la configuration, initialise les agents, et démarre le serveur ACP.

AJOUTS (persistance) :
- Sauvegarde du log de session (output/system/metrics/session_log_*.json)
  et des métriques système globales à l'arrêt du serveur via atexit.
"""

import atexit
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from settings.config import (
    ACP_SERVER_HOST,
    ACP_SERVER_PORT,
    LOG_FORMAT,
    LOG_LEVEL,
    ensure_output_dirs,
)


def setup_logging():
    """Configure le logging global."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def register_agents():
    """Enregistre tous les agents dans le registre."""
    from serveurs.agent_registry import registry
    from agents.executor_agent import get_agent_config as get_executor_config
    from agents.planner_agent import get_agent_config as get_planner_config

    registry.register(get_executor_config())
    registry.register(get_planner_config())

    logging.getLogger(__name__).info(
        f"Agents enregistrés: {registry.list_agent_names()}"
    )


def register_shutdown_hooks():
    """
    Enregistre les hooks d'arrêt pour sauvegarder les métriques système
    et le log de session dans output/system/metrics/ avant l'arrêt du process.
    """
    logger = logging.getLogger(__name__)

    def _save_on_exit():
        logger.info("Arrêt du serveur — Sauvegarde des métriques système...")
        try:
            # ── Log de session centralisé ──────────────────────────────────
            from metrics.metrics_logger import metrics_logger
            session_path = metrics_logger.save_session_log()
            logger.info(f"Log de session sauvegardé → {session_path}")

            # ── Rapport de synthèse de la session ─────────────────────────
            report = metrics_logger.generate_report()
            logger.info(f"Rapport session : {report}")

        except Exception as e:
            logger.error(f"Échec sauvegarde log de session: {e}")

        try:
            # ── Métriques système globales (toutes agents confondus) ───────
            # On réutilise le collecteur système déjà peuplé par les agents.
            # Import des instances de module pour récupérer les données accumulées.
            from agents.executor_agent import _system_collector as exec_sys
            sys_path = exec_sys.save_metrics()
            logger.info(f"Métriques système (executor) sauvegardées → {sys_path}")
        except Exception as e:
            logger.error(f"Échec sauvegarde métriques système (executor): {e}")

        try:
            from agents.planner_agent import _system_collector as plan_sys
            sys_path = plan_sys.save_metrics()
            logger.info(f"Métriques système (planner) sauvegardées → {sys_path}")
        except Exception as e:
            logger.error(f"Échec sauvegarde métriques système (planner): {e}")

        logger.info("Sauvegarde des métriques système terminée.")

    atexit.register(_save_on_exit)
    logging.getLogger(__name__).info("Hooks d'arrêt enregistrés (sauvegarde métriques à l'arrêt)")


def main():
    """Point d'entrée principal."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("  Système Multi-Agent ACP — Démarrage")
    logger.info("=" * 60)

    # 1. Créer la structure output
    ensure_output_dirs()
    logger.info("Structure output créée")

    # 2. Enregistrer les agents
    register_agents()

    # 3. Enregistrer les hooks d'arrêt (persistance métriques système)
    register_shutdown_hooks()

    # 4. Créer et démarrer le serveur ACP
    from serveurs.acp_server import create_acp_server, start_server

    server = create_acp_server()

    logger.info(f"Serveur ACP prêt sur http://{ACP_SERVER_HOST}:{ACP_SERVER_PORT}")
    logger.info("Endpoints disponibles:")
    logger.info(f"  GET  http://{ACP_SERVER_HOST}:{ACP_SERVER_PORT}/agents")
    logger.info(f"  POST http://{ACP_SERVER_HOST}:{ACP_SERVER_PORT}/runs")
    logger.info("=" * 60)

    start_server(server)


if __name__ == "__main__":
    main()