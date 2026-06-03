"""Tariff catalogue, baseline parameters, and UI/attribution metadata.

Tariffs are modelled as configurable structures (there is no clean open retail-tariff
dataset). Values are representative French residential prices (EUR/kWh). ENTSO-E day-ahead
prices are the production wholesale source.
"""
from __future__ import annotations

from whatif.core.schema import ScenarioParams, Tariff

# Time-of-use: off-peak (Heures Creuses) overnight, peak (Heures Pleines) during the day.
_HC_HOURS = {22, 23, 0, 1, 2, 3, 4, 5}


def tariff_catalogue() -> dict:
    """Return name -> Tariff. Representative French residential structures (EUR/kWh)."""
    tou_prices = {h: (0.20 if h in _HC_HOURS else 0.27) for h in range(24)}
    return {
        "Flat": Tariff(
            name="Flat",
            kind="flat",
            import_price=0.25,
            export_price=0.10,
            fixed_charge=0.0,
            currency="EUR",
        ),
        "Time-of-use (HP/HC)": Tariff(
            name="Time-of-use (HP/HC)",
            kind="tou",
            import_price=0.27,
            export_price=0.10,
            fixed_charge=0.0,
            tou_import_prices=tou_prices,
            currency="EUR",
        ),
    }


def baseline_params() -> ScenarioParams:
    """The 'current setup' the what-if is compared against (slider defaults)."""
    return ScenarioParams(
        pv_kwp=3.0,
        consumption_pct=0.0,
        ev=False,
        battery_kwh=0.0,
        battery_power_kw=2.5,
        tariff_name="Flat",
    )


# Change-groups applied (in order) for exact attribution. Grouping battery capacity with its
# power rating ensures the stepwise walk ends EXACTLY at the target, so contributions telescope
# to the total delta. Each group is keyed by its primary field (used as the display label).
ATTRIBUTION_GROUPS = [
    ("pv_kwp", ["pv_kwp"]),
    ("battery_kwh", ["battery_kwh", "battery_power_kw"]),
    ("tariff_name", ["tariff_name"]),
    ("consumption_pct", ["consumption_pct"]),
    ("ev", ["ev"]),
]
ATTRIBUTION_ORDER = [key for key, _ in ATTRIBUTION_GROUPS]

PARAM_LABELS = {
    "pv_kwp": "PV size",
    "battery_kwh": "Battery",
    "tariff_name": "Tariff",
    "consumption_pct": "Consumption",
    "ev": "EV",
}

INDICATOR_NAMES = ["energy_cost", "self_consumption", "self_sufficiency", "grid_dependency"]

INDICATOR_LABELS = {
    "energy_cost": "Energy cost",
    "self_consumption": "Self-consumption",
    "self_sufficiency": "Self-sufficiency",
    "grid_dependency": "Grid dependency",
}

# Slider ranges for the UI: (min, max, step, default).
SLIDER_RANGES = {
    "pv_kwp": (0.0, 10.0, 0.5),
    "consumption_pct": (-30, 30, 5),
    "battery_kwh": (0.0, 15.0, 0.5),
    "battery_power_kw": (1.0, 7.0, 0.5),
    "ev_kwh_per_day": (4.0, 16.0, 1.0),
}
