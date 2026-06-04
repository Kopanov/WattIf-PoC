"""HF Inference LLM client (hosted-demo explainer backend, no local model needed).

Used on the hosted Hugging Face Space, where there is no local Ollama. It rephrases the
ALREADY-grounded facts into more natural prose via the HF Inference API; the UI/service
re-check the output with the no-advice guardrail and fall back to the deterministic
template if the model is rate-limited, unavailable, or the draft trips the guardrail.

The token is read from the HF_TOKEN environment variable (set as a Space secret) and is
never committed. The model is configurable via WHATIF_HF_MODEL. ``huggingface_hub`` is
imported lazily so importing this module never requires it.
"""
from __future__ import annotations

import os
from typing import Optional

from whatif.adapters.base import LLMClient

DEFAULT_HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def hf_token() -> str:
    """The HF token from the environment (Space secret), or empty string if unset."""
    return os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or ""


def hf_available() -> bool:
    """True if an HF token is present, so the hosted LLM answer can be offered."""
    return bool(hf_token())


class HFInferenceClient(LLMClient):
    def __init__(self, model: Optional[str] = None, token: Optional[str] = None) -> None:
        self.model = model or os.getenv("WHATIF_HF_MODEL", DEFAULT_HF_MODEL)
        self.token = token or hf_token()

    def complete(self, system: str, prompt: str, schema: Optional[dict] = None) -> str:
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=self.token or None)
        resp = client.chat_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
            temperature=0.2,
        )
        return resp.choices[0].message.content
