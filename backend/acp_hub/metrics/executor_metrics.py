"""
Métriques spécifiques à l'agent Executor.
Calcul, collecte et export des métriques d'orchestration.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from acp_hub.settings.config import get_agent_output_dir

logger = logging.getLogger(__name__)


class ExecutorMetricsCollector:
    """Collecteur de métriques pour l'agent Executor."""

    def __init__(self):
        self.session_start = time.time()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._history: list[dict] = []

    def record_execution(self, executor_metrics: dict[str, Any]) -> None:
        """Enregistre un snapshot des métriques de l'Executor."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_since_session_start": time.time() - self.session_start,
            **executor_metrics,
        }
        self._history.append(snapshot)
        logger.debug(f"Executor metrics snapshot enregistré: #{len(self._history)}")

    def compute_summary(self) -> dict[str, Any]:
        """Calcule un résumé des métriques de la session."""
        if not self._history:
            return {"status": "no_data"}

        latest = self._history[-1]

        total_requests = latest.get("total_requests", 0)
        successful = latest.get("successful_requests", 0)
        failed = latest.get("failed_requests", 0)

        # Métriques d'orchestration
        plans_executed = latest.get("plans_executed", 0)
        steps_succeeded = latest.get("steps_succeeded", 0)
        steps_failed = latest.get("steps_failed", 0)
        total_steps = latest.get("total_steps_executed", 0)

        # Métriques de communication
        acp_sent = latest.get("total_acp_messages_sent", 0)
        acp_received = latest.get("total_acp_messages_received", 0)
        avg_acp_latency = latest.get("avg_acp_latency", 0.0)

        # Métriques de qualité
        needs_handled = latest.get("total_needs_handled", 0)
        needs_resolved = latest.get("needs_resolved", 0)
        needs_unresolved = latest.get("needs_unresolved", 0)

        summary = {
            "session_id": self.session_id,
            "session_duration": time.time() - self.session_start,
            "total_snapshots": len(self._history),

            # Métriques globales
            "total_requests": total_requests,
            "success_rate": (successful / total_requests * 100) if total_requests > 0 else 0,
            "failure_rate": (failed / total_requests * 100) if total_requests > 0 else 0,
            "avg_processing_time": latest.get("avg_processing_time", 0.0),

            # Orchestration
            "plans_executed": plans_executed,
            "total_steps_executed": total_steps,
            "step_success_rate": (steps_succeeded / total_steps * 100) if total_steps > 0 else 0,
            "step_failure_rate": (steps_failed / total_steps * 100) if total_steps > 0 else 0,
            "avg_step_time": latest.get("avg_step_time", 0.0),
            "plan_completion_rate": latest.get("plan_completion_rate", 0.0) * 100,

            # Routage
            "total_routing_decisions": latest.get("total_routing_decisions", 0),
            "routing_changes": latest.get("routing_changes", 0),

            # Communication ACP
            "acp_messages_sent": acp_sent,
            "acp_messages_received": acp_received,
            "acp_message_delivery_rate": (acp_received / acp_sent * 100) if acp_sent > 0 else 0,
            "avg_acp_latency_seconds": avg_acp_latency,

            # Besoins & Résolution
            "total_needs_handled": needs_handled,
            "need_resolution_rate": (needs_resolved / needs_handled * 100) if needs_handled > 0 else 0,
            "needs_unresolved": needs_unresolved,

            # Fiabilité
            "total_retries": latest.get("total_retries", 0),
            "error_count": latest.get("error_count", 0),
            "total_llm_calls": latest.get("total_llm_calls", 0),
        }

        return summary

    def save_metrics(self) -> Path:
        """Sauvegarde les métriques dans le dossier output/executor/metrics/."""
        output_dir = get_agent_output_dir("executor")
        metrics_dir = output_dir / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        filename = f"executor_metrics_{self.session_id}.json"
        filepath = metrics_dir / filename

        data = {
            "summary": self.compute_summary(),
            "history": self._history,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Métriques Executor sauvegardées: {filepath}")
        return filepath

    def get_history(self) -> list[dict]:
        """Retourne l'historique complet des snapshots."""
        return self._history.copy()
