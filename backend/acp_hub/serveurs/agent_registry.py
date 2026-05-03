"""
Registre dynamique des agents du système multi-agent.
Permet l'ajout, la suppression et la découverte des agents de manière extensible.
"""

import importlib
import importlib.util
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from acp_hub.settings.config import AGENTS_DIR

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration d'un agent enregistré dans le système."""

    name: str
    description: str
    handler: Callable  # Fonction async de l'agent compatible ACP
    capabilities: list[str] = field(default_factory=list)
    input_content_types: list[str] = field(
        default_factory=lambda: ["text/plain", "application/json"]
    )
    output_content_types: list[str] = field(
        default_factory=lambda: ["text/plain", "application/json"]
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """
    Registre centralisé des agents.
    Permet l'enregistrement dynamique et la découverte des agents.
    """

    def __init__(self):
        self._agents: dict[str, AgentConfig] = {}
        logger.info("AgentRegistry initialisé")

    def register(self, config: AgentConfig) -> None:
        """Enregistre un agent dans le registre."""
        if config.name in self._agents:
            logger.warning(
                f"Agent '{config.name}' déjà enregistré, remplacement en cours."
            )
        self._agents[config.name] = config
        logger.info(
            f"Agent '{config.name}' enregistré — {config.description}"
        )

    def unregister(self, name: str) -> bool:
        """Supprime un agent du registre. Retourne True si supprimé."""
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Agent '{name}' supprimé du registre")
            return True
        logger.warning(f"Agent '{name}' non trouvé dans le registre")
        return False

    def get(self, name: str) -> Optional[AgentConfig]:
        """Retourne la configuration d'un agent par son nom."""
        return self._agents.get(name)

    def list_agents(self) -> list[AgentConfig]:
        """Retourne la liste de tous les agents enregistrés."""
        return list(self._agents.values())

    def list_agent_names(self) -> list[str]:
        """Retourne la liste des noms d'agents enregistrés."""
        return list(self._agents.keys())

    def has_agent(self, name: str) -> bool:
        """Vérifie si un agent est enregistré."""
        return name in self._agents

    def get_agent_capabilities(self, name: str) -> list[str]:
        """Retourne les capacités d'un agent."""
        agent = self.get(name)
        return agent.capabilities if agent else []

    def find_agents_by_capability(self, capability: str) -> list[AgentConfig]:
        """Trouve tous les agents ayant une capacité donnée."""
        return [
            agent
            for agent in self._agents.values()
            if capability in agent.capabilities
        ]

    def auto_discover(self, agents_dir: Path = AGENTS_DIR) -> list[str]:
        """
        Découvre et charge automatiquement les agents depuis le dossier agents/.
        Chaque module agent doit exposer une fonction `get_agent_config()` 
        qui retourne un AgentConfig.
        """
        discovered = []
        if not agents_dir.exists():
            logger.warning(f"Dossier agents non trouvé: {agents_dir}")
            return discovered

        for file_path in agents_dir.glob("*_agent.py"):
            module_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(
                    f"agents.{module_name}", file_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, "get_agent_config"):
                        config = module.get_agent_config()
                        if isinstance(config, AgentConfig):
                            self.register(config)
                            discovered.append(config.name)
                        else:
                            logger.warning(
                                f"get_agent_config() dans {module_name} ne retourne pas un AgentConfig"
                            )
                    else:
                        logger.debug(
                            f"Module {module_name} n'a pas de get_agent_config()"
                        )
            except Exception as e:
                logger.error(
                    f"Erreur lors du chargement de l'agent {module_name}: {e}"
                )

        logger.info(f"Auto-découverte terminée: {len(discovered)} agents trouvés")
        return discovered

    def get_agents_summary(self) -> list[dict[str, Any]]:
        """Retourne un résumé de tous les agents pour l'affichage."""
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "capabilities": agent.capabilities,
                "input_content_types": agent.input_content_types,
                "output_content_types": agent.output_content_types,
            }
            for agent in self._agents.values()
        ]


# Instance globale du registre
registry = AgentRegistry()
