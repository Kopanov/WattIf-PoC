"""Local LLM client via Ollama (optional explainer backend, no API key).

Used only when the user opts in. It rephrases the ALREADY-grounded facts into more natural
prose; the service re-checks the output with the guardrail and falls back to the deterministic
template if the model is unavailable or the draft trips the guardrail. ``requests`` is imported
lazily so importing this module never requires it.
"""
from __future__ import annotations

from typing import Optional

from whatif.adapters.base import LLMClient
from whatif.config import settings


class OllamaClient(LLMClient):
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None) -> None:
        self.model = model or settings.ollama_model
        self.host = (host or settings.ollama_host).rstrip("/")

    def complete(self, system: str, prompt: str, schema: Optional[dict] = None) -> str:
        import requests

        resp = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def list_models(host: Optional[str] = None) -> list:
    """Names of locally available Ollama models (empty list if the server is unreachable)."""
    import requests

    base = (host or settings.ollama_host).rstrip("/")
    try:
        resp = requests.get(f"{base}/api/tags", timeout=3)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []
