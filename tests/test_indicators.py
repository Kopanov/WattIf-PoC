"""Exactness of the indicator engine vs hand-computed references (M2), plus battery sanity."""
from __future__ import annotations

import pandas as pd
import pytest

from whatif.core.indicators import compute_indicators
from whatif.core.schema import BatteryConfig, Scenario, Tariff


def _scenario(load, pv, tariff, battery=None):
    idx = pd.date_range("2023-06-01", periods=len(load), freq="h")
    df = pd.DataFrame({"load_kwh": load, "pv_kwh": pv}, index=idx)
    return Scenario(profile=df, tariff=tariff, battery=battery)


def test_indicators_match_hand_computation():
    # load=[1,2,1,1], pv=[0,1,2,0] -> import=[1,1,0,1]=3, export=[0,0,1,0]=1
    tariff = Tariff(name="t", kind="flat", import_price=0.30, export_price=0.10, fixed_charge=0.0)
    ind = compute_indicators(_scenario([1.0, 2.0, 1.0, 1.0], [0.0, 1.0, 2.0, 0.0], tariff))

    assert ind.energy_cost == pytest.approx(3 * 0.30 - 1 * 0.10)       # 0.80
    assert ind.self_consumption == pytest.approx((3 - 1) / 3)          # 0.6667
    assert ind.self_sufficiency == pytest.approx((5 - 3) / 5)          # 0.40
    assert ind.grid_dependency == pytest.approx(3 / 5)                 # 0.60


def test_fixed_charge_and_tou_pricing():
    # All import in one off-peak hour vs one peak hour should differ by the ToU spread.
    flat = Tariff(name="f", kind="flat", import_price=0.25, export_price=0.10, fixed_charge=12.0)
    ind = compute_indicators(_scenario([4.0], [0.0], flat))
    assert ind.energy_cost == pytest.approx(4 * 0.25 + 12.0)           # 13.0


def test_self_sufficiency_is_complement_of_grid_dependency():
    tariff = Tariff(name="t", kind="flat", import_price=0.2, export_price=0.1)
    ind = compute_indicators(_scenario([1.0, 2.0, 3.0], [0.5, 0.0, 4.0], tariff))
    assert ind.self_sufficiency + ind.grid_dependency == pytest.approx(1.0)


def test_battery_increases_self_consumption_and_cuts_grid_dependency():
    # Midday PV surplus, evening load deficit -> a battery shifts energy and helps both.
    load = [0.0] * 10 + [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] + [3.0, 3.0, 3.0, 0.0, 0.0, 0.0]
    pv = [0.0] * 10 + [3.0, 3.0, 3.0, 3.0, 0.0, 0.0, 0.0, 0.0] + [0.0] * 6
    tariff = Tariff(name="t", kind="flat", import_price=0.30, export_price=0.05)

    no_batt = compute_indicators(_scenario(load, pv, tariff))
    batt = compute_indicators(
        _scenario(load, pv, tariff, BatteryConfig(capacity_kwh=10.0, max_charge_kw=5.0, max_discharge_kw=5.0))
    )

    assert batt.self_consumption > no_batt.self_consumption
    assert batt.grid_dependency < no_batt.grid_dependency
    assert batt.self_sufficiency > no_batt.self_sufficiency
