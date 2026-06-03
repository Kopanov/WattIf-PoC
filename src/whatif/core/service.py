"""Orchestration: run one what-if end to end. This is the single seam the UI and the
(M8) API both call, so they are guaranteed to produce identical results.
"""
from __future__ import annotations

from dataclasses import dataclass

from whatif.core import explainer, guardrail
from whatif.core.attribution import attribute
from whatif.core.catalogue import INDICATOR_NAMES
from whatif.core.generator import scenario_from_params
from whatif.core.indicators import compute_indicators
from whatif.core.schema import Assets, Indicators, Scenario, ScenarioParams


@dataclass
class WhatIfOutput:
    base_ind: Indicators
    wi_ind: Indicators
    deltas: dict
    attribution: dict
    narrative: str
    audit: dict
    guardrail_passed: bool
    base_scn: Scenario
    wi_scn: Scenario
    currency: str = "EUR"


def run_whatif(
    base_params: ScenarioParams, target_params: ScenarioParams, assets: Assets, llm=None
) -> WhatIfOutput:
    """Compute baseline + what-if indicators, exact attribution, and a guarded narrative.

    If ``llm`` is given, it rephrases the grounded template; the result is re-checked by the
    guardrail and we fall back to the template if the model is unavailable or the draft is
    blocked. The explanation source is recorded in the audit either way.
    """
    currency = assets.tariffs[target_params.tariff_name].currency

    base_scn = scenario_from_params(base_params, assets, "baseline")
    wi_scn = scenario_from_params(target_params, assets, "what-if")

    base_ind = compute_indicators(base_scn)
    wi_ind = compute_indicators(wi_scn)
    deltas = {ind: getattr(wi_ind, ind) - getattr(base_ind, ind) for ind in INDICATOR_NAMES}

    attribution = attribute(base_params, target_params, assets)

    expl = explainer.explain(base_ind, wi_ind, attribution, base_params, target_params, currency)
    narrative = expl["text"]
    source = "grounded template (deterministic slot-filling over the computed facts)"
    audit = dict(expl["audit"])

    if llm is not None:
        try:
            draft = explainer.phrase_with_llm(expl["text"], llm)
            gr_draft = guardrail.check(draft)
            if draft and gr_draft.passed:
                narrative = draft
                source = ("local LLM (Ollama) — rephrased the locked facts, then re-checked and "
                          "cleared by the no-advice guardrail")
            else:
                source = ("grounded template — the LLM draft tripped the guardrail, so we fell "
                          "back automatically")
                audit["llm_blocked_reasons"] = gr_draft.reasons
        except Exception as exc:  # noqa: BLE001
            source = f"grounded template — LLM unavailable ({type(exc).__name__})"

    gr = guardrail.check(narrative)
    audit["guardrail"] = guardrail.audit_record(narrative, gr)
    audit["explanation_source"] = source

    return WhatIfOutput(
        base_ind=base_ind,
        wi_ind=wi_ind,
        deltas=deltas,
        attribution=attribution,
        narrative=narrative,
        audit=audit,
        guardrail_passed=gr.passed,
        base_scn=base_scn,
        wi_scn=wi_scn,
        currency=currency,
    )
