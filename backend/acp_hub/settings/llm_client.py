"""
Client LLM réutilisable pour tous les agents du système.
Basé sur le pattern OpenAI-compatible avec support asynchrone.
"""

import logging
from typing import Optional

import httpx
from openai import AsyncOpenAI, OpenAI

from acp_hub.settings.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_FREQUENCY_PENALTY,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PRESENCE_PENALTY,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    LLM_VERIFY_SSL,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """Client LLM encapsulant les appels synchrones et asynchrones."""

    def __init__(
        self,
        api_key: str = LLM_API_KEY,
        base_url: str = LLM_BASE_URL,
        model: str = LLM_MODEL,
        verify_ssl: bool = LLM_VERIFY_SSL,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

        # Client synchrone
        http_client = httpx.Client(verify=verify_ssl)
        self.sync_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )

        # Client asynchrone
        async_http_client = httpx.AsyncClient(verify=verify_ssl)
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=async_http_client,
        )

    def chat(
        self,
        messages: list[dict],
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_TOKENS,
        top_p: float = LLM_TOP_P,
        frequency_penalty: float = LLM_FREQUENCY_PENALTY,
        presence_penalty: float = LLM_PRESENCE_PENALTY,
        model: Optional[str] = None,
    ) -> str:
        """Appel synchrone au LLM. Retourne le contenu de la réponse."""
        try:
            target_model = model or self.model
            kwargs = {}
            if "kimi" in target_model:
                kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": True}}

            response = self.sync_client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                **kwargs
            )
            content = response.choices[0].message.content
            logger.debug(f"LLM response (sync): {content[:200]}...")
            return content
        except Exception as e:
            logger.error(f"Erreur appel LLM synchrone: {e}")
            raise

    async def achat(
        self,
        messages: list[dict],
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_TOKENS,
        top_p: float = LLM_TOP_P,
        frequency_penalty: float = LLM_FREQUENCY_PENALTY,
        presence_penalty: float = LLM_PRESENCE_PENALTY,
        model: Optional[str] = None,
    ) -> str:
        """Appel asynchrone au LLM. Retourne le contenu de la réponse."""
        try:
            target_model = model or self.model
            kwargs = {}
            if "kimi" in target_model:
                kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": True}}

            response = await self.async_client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                **kwargs
            )
            content = response.choices[0].message.content
            logger.debug(f"LLM response (async): {content[:200]}...")
            return content
        except Exception as e:
            logger.error(f"Erreur appel LLM asynchrone: {e}")
            raise


# Instance globale réutilisable
llm_client = LLMClient()
