---
name: HF Inference reasoning models return empty content
description: Why the HF Inference LLM backend must use an instruct (non-reasoning) model
---

On the HF Inference API (`huggingface_hub.InferenceClient.chat_completion`), **reasoning
models return EMPTY content** for short rephrase-style tasks: they spend the whole
`max_tokens` budget on hidden thinking, so `choices[0].message.content` is `""` with
`finish_reason="length"`. Raising `max_tokens` or prepending `/no_think` did NOT help.

Observed (June 2026):
- `Qwen/Qwen3-8B`, `Qwen/Qwen3.5-9B` → served but return empty content (reasoning).
- `Qwen/Qwen3.5-4B`, `Qwen/Qwen3-4B`, `Qwen/Qwen2.5-14B-Instruct` → BadRequest (not served).
- `Qwen/Qwen2.5-7B-Instruct`, `meta-llama/Llama-3.1-8B-Instruct` → return proper text.

**Rule:** the HF explainer backend must use an *instruct* (non-reasoning) model. Empty
content must `raise` so the UI fallback shows status `None` rather than silently echoing
the deterministic template (which made the "LLM-based" answer identical to "Rule-based").

**Why:** silent empty-string returns made the LLM answer mirror the rule-based template.
**How to apply:** when changing `DEFAULT_HF_MODEL` / `WHATIF_HF_MODEL`, verify the model
is served AND returns non-empty content for a short prompt before shipping.
