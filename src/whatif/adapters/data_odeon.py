"""ODEON Energy Data Space adapter — the explicit production swap point.

Stays a stub in the PoC (no platform access before award). The interface is identical
to ``OpenDataSource``; going live means implementing these three methods against the
ODEON Open API Gateway, nothing else.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from whatif.adapters.base import DataSource

if TYPE_CHECKING:
    import pandas as pd

    from whatif.core.schema import Tariff

_MSG = "ODEON Energy Data Space adapter — implement against the ODEON Open API Gateway after award."


class OdeonDataSource(DataSource):
    def list_households(self) -> list[str]:
        raise NotImplementedError(_MSG)

    def load_profile(self, household_id: str) -> "pd.DataFrame":
        raise NotImplementedError(_MSG)

    def tariff(self, name: str) -> "Tariff":
        raise NotImplementedError(_MSG)
