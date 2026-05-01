"""
Serveur ACP principal.
Initialise le serveur acp_sdk, enregistre dynamiquement les agents
depuis le registre, et démarre le serveur HTTP.

CORRECTIONS :
- Suppression des paramètres non supportés (input_content_types, output_content_types)
  dans server.agent() selon la version de acp_sdk
- Utilisation de functools.wraps pour préserver les métadonnées de la fonction
- Le résultat du décorateur est maintenant stocké (bonne pratique)
- Meilleure gestion des erreurs à l'enregistrement
"""

import functools
import logging
from collections.abc import AsyncGenerator

from acp_sdk.models import Message, MessagePart
from acp_sdk.server import Context, RunYield, RunYieldResume, Server

from serveurs.agent_registry import AgentConfig, registry
from settings.config import ACP_SERVER_HOST, ACP_SERVER_PORT

logger = logging.getLogger(__name__)


def create_acp_server() -> Server:
    """
    Crée et configure le serveur ACP.
    Enregistre tous les agents du registre comme agents ACP.
    """
    server = Server()

    agents = registry.list_agents()
    if not agents:
        logger.warning("Aucun agent enregistré dans le registre.")
        return server

    for agent_config in agents:
        try:
            _register_agent_to_server(server, agent_config)
            logger.info(f"Agent ACP '{agent_config.name}' enregistré avec succès")
        except Exception as e:
            logger.error(
                f"Échec de l'enregistrement de l'agent '{agent_config.name}': {e}",
                exc_info=True,
            )

    registered = registry.list_agent_names()
    logger.info(f"Serveur ACP configuré — agents enregistrés : {registered}")
    return server


def _register_agent_to_server(server: Server, agent_config: AgentConfig) -> None:
    """
    Enregistre un agent dans le serveur ACP.

    CORRECTION principale : on crée la fonction handler AVANT d'appeler
    server.agent(), on lui assigne __name__ et __doc__ via functools.wraps,
    et on ne passe que les paramètres supportés par l'API ACP SDK (name, description).
    Les paramètres input/output_content_types ont été retirés car ils ne sont pas
    disponibles dans toutes les versions du SDK et provoquent un TypeError silencieux
    qui empêche l'enregistrement de l'agent.
    """
    handler = agent_config.handler

    # ── Créer le wrapper avant de le décorer ─────────────────────────────────
    # functools.wraps copie __name__, __doc__, __module__ etc. depuis handler,
    # puis on surcharge __name__ avec le nom ACP souhaité.
    @functools.wraps(handler)
    async def acp_agent_handler(
        input: list[Message], context: Context
    ) -> AsyncGenerator[RunYield, RunYieldResume]:
        """Wrapper ACP autour du handler de l'agent."""
        logger.info(f"Agent '{agent_config.name}' — requête reçue")

        try:
            # Extraire le texte de l'input ACP
            input_text = ""
            for msg in input:
                for part in msg.parts:
                    if hasattr(part, "content") and isinstance(part.content, str):
                        input_text += part.content + "\n"

            yield {"thought": f"Agent {agent_config.name} traite la requête…"}

            # Appeler le handler de l'agent
            result = await handler(input_text.strip(), context)

            # Convertir le résultat en message ACP
            if isinstance(result, str):
                yield Message(
                    parts=[MessagePart(content=result, content_type="text/plain")]
                )
            elif isinstance(result, dict):
                import json
                yield Message(
                    parts=[
                        MessagePart(
                            content=json.dumps(result, ensure_ascii=False, indent=2),
                            content_type="application/json",
                        )
                    ]
                )
            elif isinstance(result, Message):
                yield result
            else:
                yield Message(
                    parts=[MessagePart(content=str(result), content_type="text/plain")]
                )

            logger.info(f"Agent '{agent_config.name}' — requête traitée avec succès")

        except Exception as e:
            logger.error(f"Agent '{agent_config.name}' — erreur : {e}", exc_info=True)
            yield Message(
                parts=[
                    MessagePart(
                        content=f"Erreur dans l'agent {agent_config.name}: {str(e)}",
                        content_type="text/plain",
                    )
                ]
            )

    # ── Forcer le bon __name__ AVANT de passer au décorateur ─────────────────
    # Le serveur ACP utilise __name__ pour identifier la route de l'agent.
    acp_agent_handler.__name__ = agent_config.name
    acp_agent_handler.__doc__ = agent_config.description

    # ── Enregistrer via le décorateur server.agent() ──────────────────────────
    # On stocke le résultat du décorateur (bonne pratique).
    # CORRECTION : on n'utilise PAS input_content_types ni output_content_types
    # car ces paramètres ne sont pas supportés dans toutes les versions du SDK.
    registered_handler = server.agent(
        name=agent_config.name,
        description=agent_config.description,
    )(acp_agent_handler)

    logger.debug(f"Handler enregistré pour '{agent_config.name}': {registered_handler}")


def start_server(server: Server) -> None:
    """Démarre le serveur ACP sur l'host et le port configurés."""
    logger.info(f"Démarrage du serveur ACP sur {ACP_SERVER_HOST}:{ACP_SERVER_PORT}")
    server.run(
        host=ACP_SERVER_HOST,
        port=ACP_SERVER_PORT,
        configure_logger=True,
        configure_telemetry=False,
        self_registration=False,
    )