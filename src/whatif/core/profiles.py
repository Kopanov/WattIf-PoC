"""Profile builders for the PoC.

The PV what-if uses **real PVGIS** data where available (see adapters/data_open.py); this
module provides the deterministic building blocks: a representative EU residential load
shape (used when a household has no metered data — the inclusivity case), a clear-sky PV
fallback (used only if PVGIS is unreachable), an EV charging shape, and scaling helpers.

Everything here is deterministic and reproducible (fixed seeds, closed-form shapes).
All series are hourly and tz-naive (local standard time) to keep pricing-by-hour and the
battery loop free of DST edge cases.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HOURS_PER_YEAR = 8760
REFERENCE_YEAR = 2023  # non-leap → exactly 8760 hourly steps


def hourly_index(year: int = REFERENCE_YEAR, periods: int = HOURS_PER_YEAR) -> pd.DatetimeIndex:
    return pd.date_range(start=f"{year}-01-01", periods=periods, freq="h")


# --- Residential load ------------------------------------------------------

# Normalised 24-hour shapes (relative units; absolute scale is set by annual_kwh).
_WEEKDAY_SHAPE = np.array(
    [0.30, 0.28, 0.27, 0.27, 0.30, 0.40, 0.65, 0.90, 0.80, 0.60, 0.55, 0.55,
     0.58, 0.55, 0.52, 0.55, 0.70, 0.95, 1.15, 1.20, 1.05, 0.85, 0.60, 0.40]
)
_WEEKEND_SHAPE = np.array(
    [0.32, 0.30, 0.28, 0.28, 0.30, 0.35, 0.45, 0.60, 0.80, 0.90, 0.92, 0.90,
     0.88, 0.82, 0.78, 0.80, 0.88, 1.00, 1.18, 1.20, 1.08, 0.92, 0.70, 0.48]
)


def _load_shape(index: pd.DatetimeIndex) -> np.ndarray:
    """Unnormalised residential load shape (double-peak, weekday/weekend, seasonal)."""
    hours = index.hour.to_numpy()
    is_weekend = index.dayofweek.to_numpy() >= 5
    month = index.month.to_numpy()
    base = np.where(is_weekend, _WEEKEND_SHAPE[hours], _WEEKDAY_SHAPE[hours])
    seasonal = 1.0 + 0.25 * np.cos((month - 1) / 12.0 * 2 * np.pi)  # higher in winter
    return np.clip(base * seasonal, 0.0, None)


def synthesize_load(
    index: pd.DatetimeIndex, annual_kwh: float = 3500.0, seed: int = 7
) -> pd.Series:
    """Representative EU residential load (BDEW H0 / Low Carbon London style), scaled so the
    total over ``index`` equals ``annual_kwh``. Deterministic given ``seed``."""
    rng = np.random.default_rng(seed)
    raw = np.clip(_load_shape(index) * rng.normal(1.0, 0.05, size=len(index)), 0.0, None)
    raw *= annual_kwh / raw.sum()
    return pd.Series(raw, index=index, name="load_kwh")


def load_scale_factor(annual_kwh: float) -> float:
    """Per-hour scale so the seasonal shape integrates to ``annual_kwh`` over a full year."""
    return annual_kwh / _load_shape(hourly_index()).sum()


def synthesize_load_on(index: pd.DatetimeIndex, annual_kwh: float) -> pd.Series:
    """Load for an arbitrary window (e.g. a forecast week) at the correct magnitude,
    using the global annual scale so seasonality is preserved."""
    return pd.Series(_load_shape(index) * load_scale_factor(annual_kwh), index=index, name="load_kwh")


def ev_charging_profile(
    index: pd.DatetimeIndex, kwh_per_day: float = 8.0, start_hour: int = 18, end_hour: int = 23
) -> pd.Series:
    """Deterministic home EV charging shape (evening-concentrated, ElaadNL-style).

    Spreads ``kwh_per_day`` uniformly across the evening charging window each day.
    """
    hours = index.hour.to_numpy()
    window = (hours >= start_hour) & (hours < end_hour)
    width = max(end_hour - start_hour, 1)
    ev = np.where(window, kwh_per_day / width, 0.0)
    return pd.Series(ev, index=index, name="ev_kwh")


# --- PV (clear-sky fallback; real data comes from PVGIS) -------------------

def synthesize_pv_unit(
    index: pd.DatetimeIndex, lat: float = 49.9, specific_yield: float = 1000.0
) -> pd.Series:
    """Clear-sky PV for a 1 kWp system (kWh/h), used ONLY if PVGIS is unreachable.

    Closed-form solar-geometry bell per day, scaled so the annual total equals
    ``specific_yield`` kWh/kWp (≈1000 for northern France). Deterministic.
    """
    doy = index.dayofyear.to_numpy()
    hour = index.hour.to_numpy() + 0.5  # mid-interval
    lat_r = np.radians(lat)
    decl = np.radians(23.45) * np.sin(2 * np.pi * (doy - 81) / 365.0)
    hour_angle = np.radians(15.0 * (hour - 12.0))
    sin_elev = (
        np.sin(lat_r) * np.sin(decl) + np.cos(lat_r) * np.cos(decl) * np.cos(hour_angle)
    )
    clear = np.clip(sin_elev, 0.0, None)
    # Mild seasonal cloudiness damping (sunnier summer).
    seasonal = 0.85 + 0.15 * np.cos(2 * np.pi * (doy - 172) / 365.0)
    raw = clear * seasonal
    total = raw.sum()
    if total > 0:
        raw *= specific_yield / total
    return pd.Series(raw, index=index, name="pv_kwh")


def scale_pv(unit_pv: pd.Series, kwp: float) -> pd.Series:
    """PV scales linearly with installed kWp (exact: PVGIS output is per-kWp)."""
    return (unit_pv * float(kwp)).rename("pv_kwh")
