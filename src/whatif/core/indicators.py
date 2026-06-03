"""Exact, deterministic indicator engine. Pure pandas/numpy — no model.

Definitions (documented verbatim in the UI info boxes; reproducible by a third party):
  net_t  = load_t - pv_t;  import_t = max(net_t, 0);  export_t = max(-net_t, 0)
  (with a battery, import/export come from the deterministic dispatch in battery.py)
  energy_cost      = Σ(import_t · price_import_t) − Σ(export_t · price_export_t) + fixed_charge
  self_consumption = (Σpv − Σexport) / Σpv          # share of generated PV used on site
  self_sufficiency = (Σload − Σimport) / Σload      # share of load met without the grid
  grid_dependency  = Σimport / Σload                # share of load drawn from the grid
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from whatif.core import battery
from whatif.core.schema import Indicators, Scenario, Tariff


def _clamp01(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


def import_price_vector(tariff: Tariff, index: pd.DatetimeIndex) -> np.ndarray:
    """Per-timestep import price. Flat → constant; ToU → by hour-of-day."""
    if tariff.kind == "tou" and tariff.tou_import_prices:
        hours = index.hour
        return np.array(
            [float(tariff.tou_import_prices.get(int(h), tariff.import_price)) for h in hours]
        )
    return np.full(len(index), float(tariff.import_price))


def export_price_vector(tariff: Tariff, index: pd.DatetimeIndex) -> np.ndarray:
    """Per-timestep export (feed-in) price. Constant in this PoC."""
    return np.full(len(index), float(tariff.export_price))


def energy_flows(scenario: Scenario) -> pd.DataFrame:
    """Return a frame with load_kwh, pv_kwh, import_kwh, export_kwh (and soc_kwh if battery)."""
    profile = scenario.profile
    if scenario.battery is not None and scenario.battery.capacity_kwh > 0:
        flows = battery.dispatch(profile, scenario.battery)
        out = pd.DataFrame(
            {
                "load_kwh": flows["load_kwh"].to_numpy(float),
                "pv_kwh": flows["pv_kwh"].to_numpy(float),
                "import_kwh": flows["grid_import_kwh"].to_numpy(float),
                "export_kwh": flows["grid_export_kwh"].to_numpy(float),
                "soc_kwh": flows["soc_kwh"].to_numpy(float),
            },
            index=profile.index,
        )
    else:
        net = profile["load_kwh"].to_numpy(float) - profile["pv_kwh"].to_numpy(float)
        out = pd.DataFrame(
            {
                "load_kwh": profile["load_kwh"].to_numpy(float),
                "pv_kwh": profile["pv_kwh"].to_numpy(float),
                "import_kwh": np.clip(net, 0.0, None),
                "export_kwh": np.clip(-net, 0.0, None),
            },
            index=profile.index,
        )
    return out


def compute_indicators(scenario: Scenario) -> Indicators:
    """Compute the four indicators exactly from a scenario."""
    flows = energy_flows(scenario)
    idx = flows.index

    total_load = float(flows["load_kwh"].sum())
    total_pv = float(flows["pv_kwh"].sum())
    total_import = float(flows["import_kwh"].sum())
    total_export = float(flows["export_kwh"].sum())

    p_in = import_price_vector(scenario.tariff, idx)
    p_out = export_price_vector(scenario.tariff, idx)
    energy_cost = (
        float(np.dot(flows["import_kwh"].to_numpy(float), p_in))
        - float(np.dot(flows["export_kwh"].to_numpy(float), p_out))
        + float(scenario.tariff.fixed_charge)
    )

    self_consumption = (total_pv - total_export) / total_pv if total_pv > 0 else 0.0
    self_sufficiency = (total_load - total_import) / total_load if total_load > 0 else 0.0
    grid_dependency = total_import / total_load if total_load > 0 else 0.0

    return Indicators(
        energy_cost=float(energy_cost),  # full precision; rounding is a display concern
        self_consumption=_clamp01(self_consumption),
        self_sufficiency=_clamp01(self_sufficiency),
        grid_dependency=_clamp01(grid_dependency),
    )
