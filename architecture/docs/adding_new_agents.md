# Ajouter un nouvel agent à l'Architecture Multi-Agent ACP

Ce projet intègre un serveur avec le protocole de communication **ACP (Agent Communication Protocol)**. Cette architecture standardisée facilite l'intégration de nouveaux agents dans le système.

Voici les étapes détaillées pour créer et intégrer un nouvel agent.

## Étape 1 : Créer la classe de l'Agent

Tout nouvel agent doit hériter de la classe de base `BaseAgent` définie dans `agents/base_agent.py`.
Créez un nouveau fichier Python dans le dossier `agents/` (par exemple, `agents/researcher_agent.py`).

```python
import time
import json
from typing import Any
from agents.base_agent import BaseAgent
from metrics.metrics_logger import metrics_logger

class ResearcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="researcher", # Le nom de l'agent (utilisé dans les appels ACP)
            description="Agent spécialisé dans la recherche d'informations.",
            capabilities=["web_search", "data_extraction", "summarization"]
        )
        # Vous pouvez ajouter vos propres métriques ici
        self._custom_metrics = {
            "searches_performed": 0,
            "data_extracted_kb": 0.0
        }

    async def run(self, input_text: str, context: Any = None) -> Any:
        """EntryPoint pour le serveur ACP."""
        start_time = time.time()
        self.logger.info(f"Démarrage du chercheur sur : {input_text}")
        
        try:
            # 1. Votre logique métier (appels LLM, outils, base de données, etc.)
            result_data = await self._perform_research(input_text)
            
            # 2. Mettre à jour les métriques
            self._custom_metrics["searches_performed"] += 1
            processing_time = time.time() - start_time
            self.update_metrics(success=True, processing_time=processing_time)
            
            # 3. Formater et retourner la réponse
            response = {
                "status": "success",
                "data": result_data
            }
            return json.dumps(response, ensure_ascii=False, indent=2)

        except Exception as e:
            # Gestion des erreurs
            self.logger.error(f"Erreur : {e}")
            processing_time = time.time() - start_time
            self.update_metrics(success=False, processing_time=processing_time)
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
            
    async def _perform_research(self, query: str) -> dict:
        # Implémentation de votre logique métier
        ...
```

## Étape 2 : Configurer l'Agent pour le Registre ACP

À la fin de votre fichier d'agent (ex: `agents/researcher_agent.py`), ajoutez une factory method pour instancier l'agent et générer sa configuration `AgentConfig`. Le serveur s'appuie sur cette configuration pour s'enregistrer.

```python
from serveurs.agent_registry import AgentConfig

_researcher_instance = None

def get_agent_config() -> AgentConfig:
    """Retourne la configuration de l'agent pour le registre dynamique."""
    global _researcher_instance
    if _researcher_instance is None:
        _researcher_instance = ResearcherAgent()
        
    return AgentConfig(
        name=_researcher_instance.name,
        description=_researcher_instance.description,
        handler=_researcher_instance.run,
        capabilities=_researcher_instance.capabilities,
        input_content_types=["text/plain", "application/json"],
        output_content_types=["text/plain", "application/json"],
    )
```

## Étape 3 : Enregistrer l'Agent au Démarrage

Pour que le serveur expose ce nouvel agent, vous devez l'ajouter au registre dans le fichier principal `main.py`.

Modifiez la fonction `register_agents()` dans `main.py` :

```python
def register_agents():
    """Enregistre tous les agents dans le registre."""
    from serveurs.agent_registry import registry
    from agents.executor_agent import get_agent_config as get_executor_config
    from agents.planner_agent import get_agent_config as get_planner_config
    
    # 1. Importez la configuration de votre nouvel agent
    from agents.researcher_agent import get_agent_config as get_researcher_config

    # 2. Enregistrez-le dans le registre
    registry.register(get_executor_config())
    registry.register(get_planner_config())
    registry.register(get_researcher_config())

    logging.getLogger(__name__).info(
        f"Agents enregistrés: {registry.list_agent_names()}"
    )
```

## Étape 4 (Optionnel mais recommandé) : Intégrer les Métriques

Si vous souhaitez que votre agent expose ses métriques système dans le "Dashboard Métriques" (Interface Gradio ou Logs Serveur), assurez-vous de sauvegarder vos métriques via le `SystemMetricsCollector` partagé. Vous pouvez le faire à l'intérieur de la méthode `run()` avec :

```python
# Dans agents/researcher_agent.py (en-tête du fichier)
from metrics.system_metrics import SystemMetricsCollector
_system_collector = SystemMetricsCollector()

# Plus tard dans run()
combined_metrics = {**self.get_metrics(), **self._custom_metrics}
_system_collector.record_agent_metrics(self.name, combined_metrics)
_system_collector.save_agent_metrics(self.name, combined_metrics)
```

## Résumé du flux
1. L'application (Gradio ou client ACP) exécute une requête POST sur `/runs` avec `{ "agent": "researcher", ... }`.
2. Le serveur `acp_server.py` dirige la requête vers la fonction configurée dans `AgentConfig.handler`.
3. La fonction `ResearcherAgent.run()` est déclenchée, effectue la logique, et retourne le JSON.
4. L'utilisateur reçoit la sortie.
