"""SAREF-aligned internal data model.

A single tidy structure for a scenario (time-indexed load + PV, optional battery,
tariff, metadata) plus the computed indicators. A thin internal->SAREF term mapping
lets the Publisher (M6) emit conformant JSON-LD without leaking these names into the
rest of the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

try:  # pandas is a core dependency; the guard only helps static/edge tooling
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore


# --- Configuration objects -------------------------------------------------

@dataclass(frozen=True)
class Tariff:
    """Tariff modelled as a configurable structure (no open retail-tariff dataset exists)."""

    name: str
    kind: str = "flat"                       # "flat" or "tou"
    import_price: float = 0.30               # currency/kWh
    export_price: float = 0.10               # currency/kWh (feed-in)
    fixed_charge: float = 0.0                # currency over the whole period
    tou_import_prices: Optional[Mapping[int, float]] = None  # hour-of-day -> price (ToU)
    currency: str = "EUR"


@dataclass(frozen=True)
class BatteryConfig:
    """Parameters for the deterministic state-of-charge dispatch (M2)."""

    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    round_trip_efficiency: float = 0.90
    initial_soc_kwh: float = 0.0


# --- Scenario + results ----------------------------------------------------

@dataclass
class Scenario:
    """One what-if scenario. ``profile`` is a time-indexed frame with at least
    ``load_kwh`` and ``pv_kwh`` columns."""

    profile: "pd.DataFrame"
    tariff: Tariff
    battery: Optional[BatteryConfig] = None
    name: str = "scenario"
    meta: dict = field(default_factory=dict)

    REQUIRED_COLUMNS = ("load_kwh", "pv_kwh")

    def __post_init__(self) -> None:
        missing = [c for c in self.REQUIRED_COLUMNS if c not in self.profile.columns]
        if missing:
            raise ValueError(f"Scenario.profile is missing required columns: {missing}")


@dataclass(frozen=True)
class Indicators:
    """The three headline indicators (plus self-sufficiency), all exact."""

    energy_cost: float           # currency over the period
    self_consumption: float      # share of generated PV used on site [0..1]
    self_sufficiency: float      # share of load covered without import [0..1]
    grid_dependency: float       # import / load [0..1]


@dataclass
class ScenarioResult:
    """Everything the UI and Publisher need for one what-if."""

    baseline: Indicators
    whatif: Indicators
    deltas: dict = field(default_factory=dict)
    attribution: dict = field(default_factory=dict)
    narrative: str = ""
    audit: dict = field(default_factory=dict)


# --- Internal -> SAREF / IEC-CIM mapping (refined at M6) --------------------

SAREF = "https://saref.etsi.org/core/"
S4ENER = "https://saref.etsi.org/saref4ener/"

# Placeholder mapping; the Publisher fills in concrete term IRIs at M6.
SAREF_TERMS: dict[str, str] = {
    "load_kwh": "s4ener:ConsumedEnergy",
    "pv_kwh": "s4ener:ProducedEnergy",
    "import_kwh": "s4ener:ConsumedEnergy",
    "export_kwh": "s4ener:ProducedEnergy",
    "energy_cost": "saref:hasPrice",
    "self_consumption": "saref:hasValue",
    "self_sufficiency": "saref:hasValue",
    "grid_dependency": "saref:hasValue",
}


# --- Parameters + per-location assets --------------------------------------

@dataclass(frozen=True)
class ScenarioParams:
    """The adjustable parameter set (the sliders). Baseline and what-if are both instances."""

    pv_kwp: float = 3.0
    consumption_pct: float = 0.0
    ev: bool = False
    battery_kwh: float = 0.0
    battery_power_kw: float = 2.5
    tariff_name: str = "Flat"

    def as_dict(self) -> dict:
        return {
            "pv_kwp": self.pv_kwp,
            "consumption_pct": self.consumption_pct,
            "ev": self.ev,
            "battery_kwh": self.battery_kwh,
            "battery_power_kw": self.battery_power_kw,
            "tariff_name": self.tariff_name,
        }


@dataclass
class Assets:
    """Immutable building blocks for a location, from which any scenario is built."""

    base_load: "pd.Series"   # reference annual load at consumption_pct = 0
    unit_pv: "pd.Series"     # PV per 1 kWp at the location (real PVGIS, or clear-sky fallback)
    ev_shape: "pd.Series"    # EV charging to add when ev=True
    tariffs: dict            # name -> Tariff
    location: dict = field(default_factory=dict)  # {name, lat, lon, country, pv_source}
