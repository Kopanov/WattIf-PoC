"""Local parametric PV via pvlib / PVGIS (the PV what-if engine). Implemented in M2.

pvlib and HTTP clients are imported lazily inside ``pv_series`` so importing this module
stays dependency-free.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from whatif.adapters.base import Forecaster

if TYPE_CHECKING:
    import pandas as pd


class LocalForecaster(Forecaster):
    """PV generated parametrically from panel size/orientation and location (not rescaled)."""

    def pv_series(
        self,
        kwp: float,
        tilt: float,
        azimuth: float,
        lat: float,
        lon: float,
        index: "pd.DatetimeIndex",
    ) -> "pd.Series":
        raise NotImplementedError("M2: pvlib/PVGIS PV series not implemented yet.")
