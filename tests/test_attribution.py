"""Attribution decomposition sums exactly to the total delta per indicator (M3)."""
from __future__ import annotations

import pytest

from whatif.adapters.data_open import build_assets
from whatif.core.attribution import attribute
from whatif.core.catalogue import INDICATOR_NAMES
from whatif.core.generator import scenario_from_params
from whatif.core.indicators import compute_indicators
from whatif.core.schema import ScenarioParams


def test_contributions_sum_to_total_delta():
    assets = build_assets("Amiens, FR", allow_network=False)  # clear-sky if uncached; hermetic
    base = ScenarioParams(pv_kwp=3.0, tariff_name="Flat")
    target = ScenarioParams(
        pv_kwp=6.0, consumption_pct=-10, ev=True,
        battery_kwh=8.0, battery_power_kw=3.0, tariff_name="Time-of-use (HP/HC)",
    )

    base_ind = compute_indicators(scenario_from_params(base, assets))
    wi_ind = compute_indicators(scenario_from_params(target, assets))
    contrib = attribute(base, target, assets)

    for ind in INDICATOR_NAMES:
        total = sum(contrib[f][ind] for f in contrib)
        delta = getattr(wi_ind, ind) - getattr(base_ind, ind)
        assert total == pytest.approx(delta, abs=1e-6)


def test_unchanged_params_have_zero_contribution():
    assets = build_assets("Amiens, FR", allow_network=False)
    base = ScenarioParams(pv_kwp=3.0)
    target = ScenarioParams(pv_kwp=5.0)  # only PV changes
    contrib = attribute(base, target, assets)
    for field in ("battery_kwh", "tariff_name", "consumption_pct", "ev"):
        assert all(abs(v) < 1e-12 for v in contrib[field].values())
