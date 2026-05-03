"""
Métriques de performance globales du système multi-agent.
Suivi du throughput, latence, fiabilité, ressources, et communication.
"""

import json
import logging
import os
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from settings.config import OUTPUT_DIR, get_agent_output_dir

logger = logging.getLogger(__name__)


class SystemMetricsCollector:
    """Collecteur de métriques de performance du système global."""

    def __init__(self):
        self.session_start = time.time()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._agent_metrics: dict[str, list[dict]] = {}
        self._system_events: list[dict] = []
        self._acp_stats = {
            "total_messages": 0,
            "total_bytes_sent": 0,
            "total_bytes_received": 0,
            "message_sizes": [],
        }

    def record_agent_metrics(self, agent_name: str, metrics: dict[str, Any]) -> None:
        """Enregistre les métriques d'un agent spécifique."""
        if agent_name not in self._agent_metrics:
            self._agent_metrics[agent_name] = []

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            **metrics,
        }
        self._agent_metrics[agent_name].append(snapshot)

    def record_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Enregistre un événement système."""
        self._system_events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details,
        })

    def record_acp_message(self, size_bytes: int, direction: str = "sent") -> None:
        """Enregistre un message ACP pour les statistiques."""
        self._acp_stats["total_messages"] += 1
        self._acp_stats["message_sizes"].append(size_bytes)
        if direction == "sent":
            self._acp_stats["total_bytes_sent"] += size_bytes
        else:
            self._acp_stats["total_bytes_received"] += size_bytes

    def get_system_resources(self) -> dict[str, Any]:
        """Collecte les métriques de ressources système actuelles."""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "cpu_percent_process": process.cpu_percent(interval=0.1),
                "cpu_percent_system": psutil.cpu_percent(interval=0.1),
                "memory_rss_mb": memory_info.rss / (1024 * 1024),
                "memory_vms_mb": memory_info.vms / (1024 * 1024),
                "memory_percent": process.memory_percent(),
                "system_memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "system_memory_available_gb": psutil.virtual_memory().available / (1024**3),
                "system_memory_percent": psutil.virtual_memory().percent,
                "num_threads": process.num_threads(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
            }
        except Exception as e:
            logger.warning(f"Erreur collecte ressources système: {e}")
            return {"error": str(e)}

    def compute_system_summary(self) -> dict[str, Any]:
        """Calcule un résumé global des performances du système."""
        session_duration = time.time() - self.session_start

        # Métriques par agent
        agent_summaries = {}
        for agent_name, snapshots in self._agent_metrics.items():
            if snapshots:
                latest = snapshots[-1]
                total_req = latest.get("total_requests", 0)
                success_req = latest.get("successful_requests", 0)

                agent_summaries[agent_name] = {
                    "total_requests": total_req,
                    "success_rate": (success_req / total_req * 100) if total_req > 0 else 0,
                    "avg_processing_time": latest.get("avg_processing_time", 0.0),
                    "total_llm_calls": latest.get("total_llm_calls", 0),
                    "total_snapshots": len(snapshots),
                }

        # Throughput global
        total_all_requests = sum(
            s.get("total_requests", 0)
            for snaps in self._agent_metrics.values()
            for s in snaps[-1:]
        )

        # Latences per agent
        latencies = {}
        for agent_name, snapshots in self._agent_metrics.items():
            if snapshots:
                processing_times = [
                    s.get("avg_processing_time", 0) for s in snapshots if s.get("avg_processing_time")
                ]
                if processing_times:
                    sorted_times = sorted(processing_times)
                    latencies[agent_name] = {
                        "avg": sum(sorted_times) / len(sorted_times),
                        "median": sorted_times[len(sorted_times) // 2],
                        "p95": sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) >= 20 else sorted_times[-1],
                        "min": sorted_times[0],
                        "max": sorted_times[-1],
                    }

        # Communication ACP
        avg_msg_size = (
            sum(self._acp_stats["message_sizes"]) / len(self._acp_stats["message_sizes"])
            if self._acp_stats["message_sizes"]
            else 0
        )

        summary = {
            "session_id": self.session_id,
            "session_duration_seconds": session_duration,
            "system_info": self.get_system_resources(),

            # Throughput
            "total_requests_all_agents": total_all_requests,
            "requests_per_second": total_all_requests / session_duration if session_duration > 0 else 0,
            "active_agents": len(self._agent_metrics),

            # Latences
            "latencies_per_agent": latencies,

            # Fiabilité
            "total_system_events": len(self._system_events),
            "error_events": len([e for e in self._system_events if e["type"] == "error"]),

            # Communication ACP
            "acp_total_messages": self._acp_stats["total_messages"],
            "acp_total_bytes_sent": self._acp_stats["total_bytes_sent"],
            "acp_total_bytes_received": self._acp_stats["total_bytes_received"],
            "acp_avg_message_size_bytes": avg_msg_size,

            # Par agent
            "agent_summaries": agent_summaries,
        }

        return summary

    def save_metrics(self) -> Path:
        """Sauvegarde les métriques système dans output/system/metrics/."""
        output_dir = OUTPUT_DIR / "system" / "metrics"
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"system_metrics_{self.session_id}.json"
        filepath = output_dir / filename

        data = {
            "summary": self.compute_system_summary(),
            "agent_metrics": self._agent_metrics,
            "system_events": self._system_events,
            "acp_stats": {
                k: v for k, v in self._acp_stats.items() if k != "message_sizes"
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Métriques système sauvegardées: {filepath}")
        return filepath

    def save_agent_metrics(self, agent_name: str, agent_metrics: dict[str, Any]) -> Path:
        """Sauvegarde les métriques d'un agent dans output/<agent>/metrics/."""
        output_dir = get_agent_output_dir(agent_name)
        metrics_dir = output_dir / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{agent_name}_metrics_{self.session_id}.json"
        filepath = metrics_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(agent_metrics, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Métriques agent '{agent_name}' sauvegardées: {filepath}")
        return filepath
