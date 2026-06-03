"""ODEON Renewable Energy Generation Forecasting (REGFM) artefact — production swap point.

Stays a stub in the PoC. The I/O contract matches ``LocalForecaster`` (history 7–14 days
where needed, 15min/60min granularity, pandas output), so the swap is a one-method change.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from whatif.adapters.base import Forecaster

if TYPE_CHECKING:
    import pandas as pd


class OdeonForecaster(Forecaster):
    def pv_series(
        self,
        kwp: float,
        tilt: float,
        azimuth: float,
        lat: float,
        lon: float,
        index: "pd.DatetimeIndex",
    ) -> "pd.Series":
        raise NotImplementedError(
            "ODEON PV artefact — call an ODEON REGFM AI artefact via the API after award."
        )
