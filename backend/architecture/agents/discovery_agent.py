import json
import time
import httpx
from typing import Any
from agents.base_agent import BaseAgent
from serveurs.agent_registry import AgentConfig
from metrics.system_metrics import SystemMetricsCollector

# Collecteur système pour intégrer les métriques dans le rapport global
_system_collector = SystemMetricsCollector()

class DiscoveryAgent(BaseAgent):
    """
    Agent proxy pour le système intelligent_target_discovery.
    Fait le pont entre l'architecture ACP et le serveur FastAPI de découverte.
    """

    def __init__(self):
        super().__init__(
            name="intelligent_target_discovery",
            description="Agent spécialisé dans la découverte de cibles moléculaires, l'extraction d'entités biomédicales et l'interrogation de bases de données (PubMed, etc).",
            capabilities=["target_discovery", "biomedical_search", "molecular_extraction"]
        )
        self._custom_metrics = {
            "api_requests_sent": 0,
            "api_errors": 0
        }

    async def run(self, input_text: str, context: Any = None) -> Any:
        start_time = time.time()
        self.logger.info(f"Démarrage discovery_agent sur: {input_text[:50]}...")
        self._custom_metrics["api_requests_sent"] += 1

        payload = {
            "prompt": input_text,
            "top_k": 5,
            "data_types": ["text", "pdf"],
            "intent": "refresh"
        }

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post("http://127.0.0.1:8000/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                
                # Vérification si le serveur API indique une erreur (même avec un code 200/500 interne encapsulé)
                if not data.get("success", True) and data.get("error"):
                    raise Exception(data.get("error"))

                processing_time = time.time() - start_time
                self.update_metrics(success=True, processing_time=processing_time)
                
                # Sauvegarde des métriques
                combined_metrics = {**self.get_metrics(), **self._custom_metrics}
                _system_collector.record_agent_metrics(self.name, combined_metrics)
                _system_collector.save_agent_metrics(self.name, combined_metrics)

                return json.dumps({
                    "status": "success",
                    "result": data.get("result", ""),
                    "targets": data.get("targets", []),
                    "sources": data.get("sources", [])
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"Erreur API discovery: {str(e)}")
            self._custom_metrics["api_errors"] += 1
            processing_time = time.time() - start_time
            self.update_metrics(success=False, processing_time=processing_time)
            
            # Sauvegarde des métriques même en cas d'erreur
            combined_metrics = {**self.get_metrics(), **self._custom_metrics}
            _system_collector.record_agent_metrics(self.name, combined_metrics)
            _system_collector.save_agent_metrics(self.name, combined_metrics)

            # Message demandé par l'utilisateur pour les erreurs de clé API / connexion
            error_msg = "La requête a été transférée pour ce système afin d'être traitée mais le problème de clé API a interrompu le processus."
            
            return json.dumps({
                "status": "error",
                "error": error_msg,
                "details": str(e)
            }, ensure_ascii=False, indent=2)

# Factory pour le registre ACP
_discovery_instance = None

def get_agent_config() -> AgentConfig:
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = DiscoveryAgent()
        
    return AgentConfig(
        name=_discovery_instance.name,
        description=_discovery_instance.description,
        handler=_discovery_instance.run,
        capabilities=_discovery_instance.capabilities,
        input_content_types=["text/plain", "application/json"],
        output_content_types=["text/plain", "application/json"],
    )
