"""PoC data adapter over open EU sources.

PV: **real PVGIS** (EC JRC) per-kWp hourly series, cached to data/samples/ so the demo runs
offline, fast, and key-free; a clear-sky model is the fallback if PVGIS is unreachable.
Load: a representative EU residential profile (real metered data arrives via ODEON).
Tariffs: configurable structures (ENTSO-E day-ahead is the production wholesale source).
EV: an ElaadNL-style charging shape.

Everything is assembled into a per-location ``Assets`` object the engine builds scenarios from.
"""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from whatif.adapters.base import DataSource
from whatif.core import profiles
from whatif.core.catalogue import tariff_catalogue
from whatif.core.schema import Assets

if TYPE_CHECKING:
    from whatif.core.schema import Tariff

# Repo-relative samples directory (committed cached snapshots).
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "samples")

# EU locations for the "choose where you live" picker (ODEON-pilot-relevant + sunny spread).
EU_LOCATIONS = {
    "Amiens, FR": {"lat": 49.894, "lon": 2.296, "country": "FR", "specific_yield": 1000.0},
    "Lyon, FR": {"lat": 45.764, "lon": 4.835, "country": "FR", "specific_yield": 1250.0},
    "Madrid, ES": {"lat": 40.417, "lon": -3.703, "country": "ES", "specific_yield": 1600.0},
    "Athens, GR": {"lat": 37.984, "lon": 23.728, "country": "GR", "specific_yield": 1550.0},
    "Copenhagen, DK": {"lat": 55.676, "lon": 12.568, "country": "DK", "specific_yield": 1050.0},
    "Dublin, IE": {"lat": 53.350, "lon": -6.260, "country": "IE", "specific_yield": 950.0},
}

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"


def list_locations() -> dict:
    return EU_LOCATIONS


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _cache_path(name: str) -> str:
    return os.path.normpath(os.path.join(SAMPLES_DIR, f"pv_{_slug(name)}.csv"))


def pvgis_unit_pv(
    lat: float, lon: float, tilt: float = 35.0, azimuth: float = 0.0,
    year: int = 2020, timeout: float = 30.0,
) -> np.ndarray:
    """Fetch real hourly PV (kWh/h) for a 1 kWp system from PVGIS. Length normalised to 8760."""
    import requests

    params = {
        "lat": lat, "lon": lon, "peakpower": 1, "loss": 14, "pvcalculation": 1,
        "angle": tilt, "aspect": azimuth, "startyear": year, "endyear": year,
        "outputformat": "json",
    }
    resp = requests.get(PVGIS_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    hourly = resp.json()["outputs"]["hourly"]
    p_kwh = np.array([h["P"] for h in hourly], dtype=float) / 1000.0  # W → kWh per hour
    if len(p_kwh) >= profiles.HOURS_PER_YEAR:
        return p_kwh[: profiles.HOURS_PER_YEAR]
    return np.pad(p_kwh, (0, profiles.HOURS_PER_YEAR - len(p_kwh)), mode="wrap")


def load_unit_pv(
    location_name: str, index: pd.DatetimeIndex, use_cache: bool = True, allow_network: bool = True
) -> "tuple[pd.Series, str]":
    """Return (per-kWp hourly PV series, source label). Cache → live PVGIS → clear-sky."""
    loc = EU_LOCATIONS[location_name]
    cache = _cache_path(location_name)

    if use_cache and os.path.exists(cache):
        arr = pd.read_csv(cache)["pv_kwh"].to_numpy(dtype=float)[: len(index)]
        return pd.Series(arr, index=index, name="pv_kwh"), "PVGIS (real, cached)"

    if allow_network:
        try:
            arr = pvgis_unit_pv(loc["lat"], loc["lon"])
            os.makedirs(SAMPLES_DIR, exist_ok=True)
            pd.DataFrame({"pv_kwh": arr}).to_csv(cache, index=False)
            return pd.Series(arr[: len(index)], index=index, name="pv_kwh"), "PVGIS (real, live)"
        except Exception:
            pass

    series = profiles.synthesize_pv_unit(index, lat=loc["lat"], specific_yield=loc["specific_yield"])
    return series, "clear-sky model (PVGIS unavailable)"


def forecast_week_weather(location_name: str, days: int = 7, timeout: float = 20.0):
    """Live short-term weather from Open-Meteo (real, keyless).

    Returns a DataFrame indexed by the next ``days`` of hourly forecast timestamps with
    ``unit_pv`` (kWh/h per kWp, from forecast irradiance) and ``temp_c``. Returns None if the
    service is unreachable (the caller falls back to another chart window).
    """
    import requests

    loc = EU_LOCATIONS[location_name]
    params = {
        "latitude": loc["lat"], "longitude": loc["lon"],
        "hourly": "shortwave_radiation,temperature_2m",
        "forecast_days": days, "timezone": "auto",
    }
    try:
        resp = requests.get(OPEN_METEO_FORECAST, params=params, timeout=timeout)
        resp.raise_for_status()
        hourly = resp.json()["hourly"]
        index = pd.to_datetime(hourly["time"])
        ghi = np.clip(np.array(hourly["shortwave_radiation"], dtype=float), 0.0, None)  # W/m^2
        temp = np.array(hourly["temperature_2m"], dtype=float)
        unit_pv = ghi / 1000.0 * 0.90  # kWh/h per kWp (performance ratio incl. approx tilt gain)
        return pd.DataFrame({"unit_pv": unit_pv, "temp_c": temp}, index=index)
    except Exception:
        return None


def build_assets(
    location_name: str = "Amiens, FR",
    annual_kwh: float = 3500.0,
    ev_kwh_per_day: float = 8.0,
    use_cache: bool = True,
    allow_network: bool = True,
) -> Assets:
    """Assemble the per-location building blocks for the engine."""
    index = profiles.hourly_index()
    unit_pv, pv_source = load_unit_pv(location_name, index, use_cache, allow_network)
    loc = EU_LOCATIONS[location_name]
    return Assets(
        base_load=profiles.synthesize_load(index, annual_kwh=annual_kwh),
        unit_pv=unit_pv,
        ev_shape=profiles.ev_charging_profile(index, kwh_per_day=ev_kwh_per_day),
        tariffs=tariff_catalogue(),
        location={
            "name": location_name,
            "lat": loc["lat"],
            "lon": loc["lon"],
            "country": loc["country"],
            "pv_source": pv_source,
            "annual_kwh": annual_kwh,
        },
    )


class OpenDataSource(DataSource):
    """DataSource over open EU data. Households are the EU example locations."""

    def list_households(self) -> list:
        return list(EU_LOCATIONS.keys())

    def load_profile(self, household_id: str) -> pd.DataFrame:
        assets = build_assets(household_id)
        return pd.DataFrame(
            {"load_kwh": assets.base_load.to_numpy(float), "pv_kwh": assets.unit_pv.to_numpy(float)},
            index=assets.base_load.index,
        )

    def tariff(self, name: str) -> "Tariff":
        return tariff_catalogue()[name]
