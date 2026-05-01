"""
Logger centralisé des métriques.
Collecte les métriques de tous les agents et les persiste dans output/.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from settings.config import OUTPUT_DIR, get_agent_output_dir

logger = logging.getLogger(__name__)


class MetricsLogger:
    """Logger centralisé pour toutes les métriques du système."""

    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._logs: list[dict] = []

    def log_metric(
        self,
        agent_name: str,
        metric_name: str,
        value: Any,
        context: dict[str, Any] = None,
    ) -> None:
        """Enregistre une métrique individuelle."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "metric": metric_name,
            "value": value,
            "context": context or {},
        }
        self._logs.append(entry)
        logger.debug(f"Metric: {agent_name}.{metric_name} = {value}")

    def log_result(
        self,
        agent_name: str,
        result_data: Any,
        result_type: str = "execution",
    ) -> Path:
        """Sauvegarde un résultat d'agent dans output/<agent>/results/."""
        output_dir = get_agent_output_dir(agent_name)
        results_dir = output_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result_type}_{timestamp}.json"
        filepath = results_dir / filename

        data = {
            "agent": agent_name,
            "result_type": result_type,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "data": result_data,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Résultat '{result_type}' de '{agent_name}' sauvegardé: {filepath}")
        return filepath

    def save_session_log(self) -> Path:
        """Sauvegarde le log complet de la session."""
        log_dir = OUTPUT_DIR / "system" / "metrics"
        log_dir.mkdir(parents=True, exist_ok=True)

        filename = f"session_log_{self.session_id}.json"
        filepath = log_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._logs, f, ensure_ascii=False, indent=2)

        logger.info(f"Log de session sauvegardé: {filepath}")
        return filepath

    def generate_report(self) -> dict[str, Any]:
        """Génère un rapport de synthèse des métriques de la session."""
        if not self._logs:
            return {"status": "no_data"}

        # Grouper par agent
        by_agent: dict[str, list[dict]] = {}
        for entry in self._logs:
            agent = entry["agent"]
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(entry)

        # Grouper par métrique
        by_metric: dict[str, list] = {}
        for entry in self._logs:
            metric = f"{entry['agent']}.{entry['metric']}"
            if metric not in by_metric:
                by_metric[metric] = []
            by_metric[metric].append(entry["value"])

        report = {
            "session_id": self.session_id,
            "total_entries": len(self._logs),
            "agents_tracked": list(by_agent.keys()),
            "metrics_per_agent": {
                agent: len(entries) for agent, entries in by_agent.items()
            },
            "unique_metrics": list(by_metric.keys()),
        }

        return report


# Instance globale
metrics_logger = MetricsLogger()
