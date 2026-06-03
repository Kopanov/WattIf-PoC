"""Optional server-side Anthropic explainer backend (M4).

Used only on the hosted demo, with a rate limit and spend cap. The key is read from the
environment and must never be committed. The ``anthropic`` SDK is imported lazily.
"""
from __future__ import annotations

from typing import Optional

from whatif.adapters.base import LLMClient
from whatif.config import settings


class AnthropicClient(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: Optional[str] = None) -> None:
        self.model = model
        self.api_key = api_key or settings.anthropic_api_key

    def complete(self, system: str, prompt: str, schema: Optional[dict] = None) -> str:
        raise NotImplementedError("M4: Anthropic explainer not implemented yet.")
