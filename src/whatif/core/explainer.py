"""Grounded explainer: render the computed facts into a strictly descriptive narrative.

This PoC uses deterministic **slot-filling over the computed numbers** — the strongest form
of the "structural guarantee" in the design: there is literally no slot for advice, and every
number is copied from the indicator engine, so the text cannot misstate a value or invent a
cause. (An optional local LLM can phrase the same locked facts more fluently — see
adapters/llm_local.py — but it never sees raw data and its output is re-checked by the
guardrail.)

Input is structured facts only (baseline indicators, what-if indicators, exact attribution).
Output is a descriptive narrative plus an audit record of the facts used.
"""
from __future__ import annotations

from whatif.core.catalogue import ATTRIBUTION_ORDER, PARAM_LABELS
from whatif.core.schema import Indicators, ScenarioParams

_CURRENCY_SYMBOL = {"EUR": "€", "USD": "$", "GBP": "£"}


def _money(x: float, currency: str = "EUR") -> str:
    sym = _CURRENCY_SYMBOL.get(currency, "")
    return f"-{sym}{abs(x):,.0f}" if x < 0 else f"{sym}{x:,.0f}"


def _money_delta(x: float, currency: str = "EUR") -> str:
    sign = "+" if x >= 0 else "-"
    return f"{sign}{_CURRENCY_SYMBOL.get(currency, '')}{abs(x):,.0f}"


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _pts(x: float) -> str:
    return f"{x * 100:+.0f} pts"


def _cap(s: str) -> str:
    """Capitalize the first letter only (so 'PV' stays 'PV')."""
    return s[:1].upper() + s[1:]


def _changed_fields(base: ScenarioParams, target: ScenarioParams) -> list:
    bd, td = base.as_dict(), target.as_dict()
    return [f for f in ATTRIBUTION_ORDER if bd[f] != td[f]]


def _driver_phrase(field: str, base: ScenarioParams, target: ScenarioParams) -> str:
    if field == "pv_kwp":
        return "the larger PV system" if target.pv_kwp > base.pv_kwp else "the smaller PV system"
    if field == "battery_kwh":
        if base.battery_kwh == 0 and target.battery_kwh > 0:
            return "the added battery"
        if target.battery_kwh == 0:
            return "removing the battery"
        return "the larger battery" if target.battery_kwh > base.battery_kwh else "the smaller battery"
    if field == "tariff_name":
        return f"the {target.tariff_name} tariff"
    if field == "consumption_pct":
        return "lower consumption" if target.consumption_pct < base.consumption_pct else "higher consumption"
    if field == "ev":
        return "the added EV charging" if target.ev else "removing the EV"
    return PARAM_LABELS.get(field, field)


def _drivers_for(attribution: dict, indicator: str, changed: list) -> list:
    items = [(f, attribution[f][indicator]) for f in changed if abs(attribution[f][indicator]) > 1e-9]
    items.sort(key=lambda kv: abs(kv[1]), reverse=True)
    return items


def explain(
    base: Indicators,
    whatif: Indicators,
    attribution: dict,
    base_params: ScenarioParams,
    target_params: ScenarioParams,
    currency: str = "EUR",
) -> dict:
    """Return ``{"text": str, "audit": dict}`` — a descriptive narrative + audit record."""
    changed = _changed_fields(base_params, target_params)

    if not changed:
        text = "No parameters were changed, so every indicator matches the baseline."
        return {
            "text": text,
            "audit": {
                "method": "grounded slot-filling over computed facts (no free generation)",
                "facts_used": {"changed_parameters": []},
            },
        }

    lines: list = []

    # Energy cost. Only show a percentage when it is meaningful (same sign, non-zero base);
    # if the bill flips below zero, describe it as a net credit instead of a misleading %.
    d_cost = whatif.energy_cost - base.energy_cost
    same_sign = bool(base.energy_cost) and ((whatif.energy_cost >= 0) == (base.energy_cost >= 0))
    change_str = (
        f"{_money_delta(d_cost, currency)} ({d_cost / base.energy_cost * 100:+.0f}%)"
        if same_sign
        else _money_delta(d_cost, currency)
    )
    credit = " (now a net credit)" if whatif.energy_cost < 0 else ""
    cost_line = (
        f"Estimated annual energy cost is {_money(whatif.energy_cost, currency)}{credit} "
        f"(baseline {_money(base.energy_cost, currency)}) — a change of {change_str}."
    )
    cost_drivers = _drivers_for(attribution, "energy_cost", changed)
    if cost_drivers:
        f0, v0 = cost_drivers[0]
        cost_line += (
            f" The largest contributor is {_driver_phrase(f0, base_params, target_params)} "
            f"({_money_delta(v0, currency)})."
        )
        if len(cost_drivers) > 1:
            f1, v1 = cost_drivers[1]
            cost_line += (
                f" {_cap(_driver_phrase(f1, base_params, target_params))} contributes "
                f"{_money_delta(v1, currency)}."
            )
    lines.append(cost_line)

    # Self-consumption
    d_sc = whatif.self_consumption - base.self_consumption
    sc_line = (
        f"Self-consumption is {_pct(whatif.self_consumption)} "
        f"(baseline {_pct(base.self_consumption)}), {_pts(d_sc)}."
    )
    sc_drivers = _drivers_for(attribution, "self_consumption", changed)
    if sc_drivers:
        f0, v0 = sc_drivers[0]
        sc_line += (
            f" The largest contributor is {_driver_phrase(f0, base_params, target_params)} "
            f"({_pts(v0)})."
        )
    lines.append(sc_line)

    # Grid dependency
    d_gd = whatif.grid_dependency - base.grid_dependency
    gd_line = (
        f"Grid dependency is {_pct(whatif.grid_dependency)} "
        f"(baseline {_pct(base.grid_dependency)}), {_pts(d_gd)}."
    )
    gd_drivers = _drivers_for(attribution, "grid_dependency", changed)
    if gd_drivers:
        f0, v0 = gd_drivers[0]
        gd_line += (
            f" The largest contributor is {_driver_phrase(f0, base_params, target_params)} "
            f"({_pts(v0)})."
        )
    lines.append(gd_line)

    audit = {
        "method": "grounded slot-filling over computed facts (no free generation)",
        "facts_used": {
            "changed_parameters": [PARAM_LABELS.get(f, f) for f in changed],
            "baseline": base.__dict__,
            "whatif": whatif.__dict__,
        },
    }
    return {"text": " ".join(lines), "audit": audit}


_LLM_SYSTEM = (
    "You rewrite a fixed energy summary into clear, natural English for a homeowner. "
    "Strict rules: keep every number and fact EXACTLY as given; do not add, infer, omit or "
    "reorder facts; never give advice, recommendations, opinions, or optimization suggestions; "
    "stay purely descriptive. Return only the rewritten summary in 2-4 short sentences."
)


def phrase_with_llm(template_text: str, llm) -> str:
    """Ask an LLM to rephrase the grounded template more naturally (the facts stay locked)."""
    return llm.complete(_LLM_SYSTEM, f"Rewrite this summary:\n\n{template_text}").strip()
