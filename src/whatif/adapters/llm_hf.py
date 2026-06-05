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

# Must be an *instruct* (non-reasoning) model served by the HF Inference API. Reasoning
# models (e.g. Qwen3 / Qwen3.5) spend the whole token budget on hidden thinking and return
# empty content here, which silently falls back to the template. Override via WHATIF_HF_MODEL.
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

        # timeout so a slow/cold model call can never hang the Streamlit run (white screen);
        # on timeout it raises, the caller catches it and falls back to the exact template.
        client = InferenceClient(token=self.token or None, timeout=30)
        resp = client.chat_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
            temperature=0.2,
        )
        choices = getattr(resp, "choices", None)
        content = choices[0].message.content if choices else None
        # Fail loudly instead of returning empty text: reasoning models / rate limits can
        # yield no content, and a silent "" would make the LLM answer mirror the template.
        if not content or not content.strip():
            raise RuntimeError(
                f"HF Inference returned empty content for model '{self.model}' "
                "(it may be a reasoning model or rate-limited)."
            )
        return content
