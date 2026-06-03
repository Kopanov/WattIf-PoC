"""Counterfactual generator — routes each parameter change to the right method.

  - PV change (kWp)        -> linear scaling of the real per-kWp PV series (exact)
  - Battery add/resize     -> deterministic dispatch in battery.py (via the engine)
  - Tariff change          -> a different price vector only (profiles unchanged)
  - Consumption (+/- %)    -> deterministic scaling of the load   [PoC]
  - EV add                 -> add a deterministic EV charging shape [PoC]

The consumption/EV routes are the place where, in the funded work, a TRAINED conditional
generator replaces naive scaling (Moat 1: "generated beats scaled"). That decision is M5;
the deterministic routes here keep the PoC exact, reproducible, and honest in the meantime.
This is the single seam where a model would ever touch the *inputs* — never the indicators.
"""
from __future__ import annotations

import pandas as pd

from whatif.core.schema import Assets, BatteryConfig, Scenario, ScenarioParams


def scenario_from_params(
    params: ScenarioParams, assets: Assets, name: str = "scenario"
) -> Scenario:
    """Build a full Scenario (profile + tariff + battery) from absolute parameters."""
    load = assets.base_load * (1.0 + params.consumption_pct / 100.0)
    if params.ev:
        load = load.add(assets.ev_shape, fill_value=0.0)
    pv = assets.unit_pv * float(params.pv_kwp)

    profile = pd.DataFrame(
        {"load_kwh": load.to_numpy(float), "pv_kwh": pv.to_numpy(float)},
        index=assets.base_load.index,
    )

    battery = None
    if params.battery_kwh and params.battery_kwh > 0:
        battery = BatteryConfig(
            capacity_kwh=float(params.battery_kwh),
            max_charge_kw=float(params.battery_power_kw),
            max_discharge_kw=float(params.battery_power_kw),
        )

    tariff = assets.tariffs[params.tariff_name]
    return Scenario(profile=profile, tariff=tariff, battery=battery, name=name)
