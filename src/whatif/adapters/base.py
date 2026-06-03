"""Adapter contracts — defined first; everything depends on them.

The three adapters (Data, Forecaster, Publisher) are the only throwaway layer between
the PoC and production. PoC implementations call open EU sources and local models;
the ``*_odeon`` implementations call ODEON APIs and stay as stubs until award.
``LLMClient`` makes the explainer's language model pluggable (local by default).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # avoid importing heavy/optional deps at runtime
    import pandas as pd

    from whatif.core.schema import Tariff


class DataSource(ABC):
    """Supplies household profiles and tariffs."""

    @abstractmethod
    def list_households(self) -> list[str]:
        ...

    @abstractmethod
    def load_profile(self, household_id: str) -> "pd.DataFrame":
        """Return a tidy time-indexed frame with at least ``['load_kwh', 'pv_kwh']``
        at a fixed granularity (15min or 60min)."""
        ...

    @abstractmethod
    def tariff(self, name: str) -> "Tariff":
        ...


class Forecaster(ABC):
    """Produces a PV generation series for the PV what-if.

    Contract mirrors the ODEON PV artefacts: history 7–14 days where needed,
    15min/60min granularity, output as a pandas object. PoC: pvlib/PVGIS.
    Production: an ODEON Renewable Energy Generation Forecasting artefact.
    """

    @abstractmethod
    def pv_series(
        self,
        kwp: float,
        tilt: float,
        azimuth: float,
        lat: float,
        lon: float,
        index: "pd.DatetimeIndex",
    ) -> "pd.Series":
        ...


class Publisher(ABC):
    """Serializes a scenario result. PoC: SAREF JSON-LD to disk (return path).
    Production: POST to the ODEON Results Explorer (return asset id)."""

    @abstractmethod
    def publish(self, scenario_result: dict) -> str:
        ...


class LLMClient(ABC):
    """Pluggable language model for the explainer. Default local (Ollama)."""

    @abstractmethod
    def complete(self, system: str, prompt: str, schema: Optional[dict] = None) -> str:
        ...
