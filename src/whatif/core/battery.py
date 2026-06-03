"""Deterministic battery state-of-charge dispatch. Physics, not ML, on purpose.

Dispatch rule: maximize self-consumption. Charge the battery from PV surplus and
discharge it to cover load deficit, bounded by usable capacity, charge/discharge power,
and round-trip efficiency. The output is an adjusted import/export/SoC series that the
indicator engine consumes exactly the same way it consumes a no-battery net series.

Round-trip efficiency ``rte`` is split symmetrically: charge_eff = discharge_eff = sqrt(rte).
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from whatif.core.schema import BatteryConfig


def infer_dt_hours(index: pd.DatetimeIndex) -> float:
    """Interval length in hours, inferred from the index (defaults to 1.0)."""
    if len(index) >= 2:
        seconds = (index[1] - index[0]).total_seconds()
        if seconds > 0:
            return seconds / 3600.0
    return 1.0


def dispatch(
    profile: pd.DataFrame,
    config: BatteryConfig,
    dt_hours: Optional[float] = None,
) -> pd.DataFrame:
    """Return ``profile`` with battery-adjusted grid flows and SoC.

    Columns added: ``grid_import_kwh``, ``grid_export_kwh``, ``soc_kwh``.
    """
    load = profile["load_kwh"].to_numpy(dtype=float)
    pv = profile["pv_kwh"].to_numpy(dtype=float)
    n = len(load)

    if dt_hours is None:
        dt_hours = infer_dt_hours(profile.index)

    cap = max(float(config.capacity_kwh), 0.0)
    eff = math.sqrt(max(float(config.round_trip_efficiency), 1e-9))  # per-side efficiency
    max_charge = max(float(config.max_charge_kw), 0.0) * dt_hours
    max_discharge = max(float(config.max_discharge_kw), 0.0) * dt_hours

    soc = min(max(float(config.initial_soc_kwh), 0.0), cap)

    grid_import = np.zeros(n)
    grid_export = np.zeros(n)
    soc_series = np.zeros(n)

    for t in range(n):
        surplus = pv[t] - load[t]
        if surplus >= 0:
            # Excess PV: charge what fits by power and capacity headroom, export the rest.
            headroom_ac = (cap - soc) / eff if eff > 0 else 0.0
            charge_ac = max(min(surplus, max_charge, headroom_ac), 0.0)
            soc += charge_ac * eff
            grid_export[t] = surplus - charge_ac
            grid_import[t] = 0.0
        else:
            # Deficit: discharge to cover, bounded by power and available energy.
            deficit = -surplus
            available_ac = soc * eff
            discharge_ac = max(min(deficit, max_discharge, available_ac), 0.0)
            soc -= discharge_ac / eff
            grid_import[t] = deficit - discharge_ac
            grid_export[t] = 0.0
        soc = min(max(soc, 0.0), cap)
        soc_series[t] = soc

    out = profile.copy()
    out["grid_import_kwh"] = grid_import
    out["grid_export_kwh"] = grid_export
    out["soc_kwh"] = soc_series
    return out
