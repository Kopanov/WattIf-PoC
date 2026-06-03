"""The optional LLM layer: descriptive output is used; advice or errors fall back to the
deterministic template — all re-checked by the guardrail. Hermetic (no Ollama needed)."""
from __future__ import annotations

from whatif.adapters.data_open import build_assets
from whatif.core.catalogue import baseline_params
from whatif.core.schema import ScenarioParams
from whatif.core.service import run_whatif


class _DummyLLM:
    def __init__(self, text):
        self._text = text

    def complete(self, system, prompt, schema=None):
        return self._text


def _run(llm):
    return run_whatif(
        baseline_params(),
        ScenarioParams(pv_kwp=5.0, battery_kwh=4.0, tariff_name="Flat"),
        build_assets("Amiens, FR", allow_network=False),
        llm=llm,
    )


def test_descriptive_llm_output_is_used():
    out = _run(_DummyLLM("The annual cost is lower and self-consumption is higher; the battery "
                         "stored midday solar for the evening."))
    assert "local LLM" in out.audit["explanation_source"]
    assert out.guardrail_passed


def test_advice_llm_output_falls_back_to_template():
    out = _run(_DummyLLM("You should install a bigger battery to save money."))
    assert "fell back" in out.audit["explanation_source"]
    assert out.guardrail_passed  # the final narrative is the safe template


def test_llm_exception_falls_back_to_template():
    class _Boom:
        def complete(self, *a, **k):
            raise RuntimeError("no server")

    out = _run(_Boom())
    assert "unavailable" in out.audit["explanation_source"]
    assert out.guardrail_passed
