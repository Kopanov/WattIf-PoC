"""Advice blocked 100%; descriptive outputs pass; the real narrative passes (M4)."""
from __future__ import annotations

from whatif.adapters.data_open import build_assets
from whatif.core import guardrail
from whatif.core.service import run_whatif
from whatif.core.schema import ScenarioParams

ADVICE = [
    "You should install a larger battery.",
    "We recommend switching to the time-of-use tariff.",
    "Consider adding an EV to save money.",
    "To save money, reduce your consumption.",
    "Install solar panels to maximize your savings.",
    "It would be better to increase your PV size.",
    "You could optimize your self-consumption with a battery.",
]

DESCRIPTIVE = [
    "Estimated annual energy cost is €612 (baseline €840), a change of -€228.",
    "Self-consumption is 58% (baseline 34%), +24 pts; the largest contributor is the added battery.",
    "Grid dependency is 41% (baseline 63%), -22 pts.",
    "No parameters were changed, so every indicator matches the baseline.",
]


def test_all_advice_blocked():
    for text in ADVICE:
        assert guardrail.check(text).passed is False, f"advice not blocked: {text!r}"


def test_all_descriptive_pass():
    for text in DESCRIPTIVE:
        res = guardrail.check(text)
        assert res.passed is True, f"descriptive blocked: {text!r} -> {res.reasons}"


def test_block_rate_is_100_percent():
    blocked = sum(1 for t in ADVICE if not guardrail.check(t).passed)
    assert blocked == len(ADVICE)


def test_generated_narrative_passes_guardrail():
    assets = build_assets("Amiens, FR", allow_network=False)
    out = run_whatif(
        ScenarioParams(pv_kwp=3.0, tariff_name="Flat"),
        ScenarioParams(pv_kwp=6.0, battery_kwh=8.0, ev=True, tariff_name="Time-of-use (HP/HC)"),
        assets,
    )
    assert out.guardrail_passed is True, f"narrative tripped guardrail: {out.narrative!r}"
    assert out.narrative  # non-empty
