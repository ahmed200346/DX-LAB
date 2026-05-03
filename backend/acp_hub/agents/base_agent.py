"""
Classe de base abstraite pour tous les agents du système.
Fournit l'interface commune, l'accès au LLM, au client ACP,
et la collecte de métriques.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from acp_sdk.client import Client as ACPClient
from acp_sdk.models import Message, MessagePart

from acp_hub.settings.config import ACP_SERVER_URL
from acp_hub.settings.llm_client import LLMClient, llm_client

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Classe de base pour tous les agents.
    Chaque agent hérite de cette classe et implémente la méthode `run()`.
    """

    def __init__(
        self,
        name: str,
        description: str,
        capabilities: list[str] = None,
        custom_llm_client: Optional[LLMClient] = None,
    ):
        self.name = name
        self.description = description
        self.capabilities = capabilities or []
        self.llm = custom_llm_client or llm_client
        self.logger = logging.getLogger(f"agent.{self.name}")
        self._metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_llm_calls": 0,
            "total_tokens_used": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
            "errors": [],
        }

    @abstractmethod
    async def run(self, input_text: str, context: Any = None) -> Any:
        """
        Méthode principale de l'agent. Doit être implémentée par chaque agent.

        Args:
            input_text: Texte d'entrée provenant d'un autre agent ou de l'utilisateur
            context: Contexte ACP (optionnel)

        Returns:
            Résultat de l'agent (str, dict, ou Message ACP)
        """
        pass

    async def call_llm(
        self,
        messages: list[dict],
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Appel au LLM avec tracking des métriques."""
        start_time = time.time()
        self._metrics["total_llm_calls"] += 1

        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            result = await self.llm.achat(messages, **kwargs)
            elapsed = time.time() - start_time
            self.logger.debug(
                f"LLM call completed in {elapsed:.2f}s"
            )
            return result
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            raise

    async def send_to_agent(
        self,
        target_agent: str,
        message: str,
        acp_server_url: str = ACP_SERVER_URL,
    ) -> str:
        """
        Envoie un message à un autre agent via le protocole ACP.

        Args:
            target_agent: Nom de l'agent cible
            message: Message à envoyer
            acp_server_url: URL du serveur ACP

        Returns:
            Réponse de l'agent cible
        """
        self.logger.info(f"Envoi de requête vers agent '{target_agent}'")
        start_time = time.time()

        try:
            async with ACPClient(base_url=acp_server_url) as client:
                run = await client.run_sync(
                    agent=target_agent,
                    input=[
                        Message(
                            parts=[
                                MessagePart(
                                    content=message,
                                    content_type="text/plain",
                                )
                            ]
                        )
                    ],
                )

                # Extraire le résultat
                result_text = ""
                if run.output:
                    for msg in run.output:
                        for part in msg.parts:
                            if hasattr(part, "content"):
                                result_text += str(part.content)

                elapsed = time.time() - start_time
                self.logger.info(
                    f"Réponse reçue de '{target_agent}' en {elapsed:.2f}s"
                )
                return result_text

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(
                f"Erreur communication avec '{target_agent}': {e} ({elapsed:.2f}s)"
            )
            raise

    def update_metrics(self, success: bool, processing_time: float, **kwargs) -> None:
        """Met à jour les métriques de l'agent."""
        self._metrics["total_requests"] += 1
        self._metrics["total_processing_time"] += processing_time

        if success:
            self._metrics["successful_requests"] += 1
        else:
            self._metrics["failed_requests"] += 1

        # Recalculer la moyenne
        if self._metrics["total_requests"] > 0:
            self._metrics["avg_processing_time"] = (
                self._metrics["total_processing_time"]
                / self._metrics["total_requests"]
            )

        # Métriques additionnelles
        for key, value in kwargs.items():
            self._metrics[key] = value

    def get_metrics(self) -> dict[str, Any]:
        """Retourne les métriques actuelles de l'agent."""
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        """Réinitialise les métriques de l'agent."""
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_llm_calls": 0,
            "total_tokens_used": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
            "errors": [],
        }
