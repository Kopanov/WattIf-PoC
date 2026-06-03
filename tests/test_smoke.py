"""M0 smoke suite: the package imports, config carries the France/EU defaults,
the adapter contracts exist, and the schema validates its inputs."""
from __future__ import annotations

import pandas as pd
import pytest

import whatif
from whatif.adapters import base
from whatif.config import settings
from whatif.core.schema import Indicators, Scenario, Tariff


def test_package_imports():
    assert whatif.__version__ == "0.1.0"


def test_settings_france_eu_defaults():
    assert settings.bidding_zone == "FR"
    assert settings.currency == "EUR"
    assert settings.tz == "Europe/Paris"
    assert settings.llm_provider in {"local", "anthropic"}


def test_adapter_contracts_present():
    for name in ("DataSource", "Forecaster", "Publisher", "LLMClient"):
        assert hasattr(base, name), f"missing adapter contract: {name}"


def test_scenario_construction_ok():
    idx = pd.date_range("2024-06-01", periods=4, freq="h", tz="Europe/Paris")
    df = pd.DataFrame(
        {"load_kwh": [1.0, 0.5, 0.2, 0.8], "pv_kwh": [0.0, 0.0, 1.2, 0.3]}, index=idx
    )
    s = Scenario(profile=df, tariff=Tariff(name="flat-default"))
    assert len(s.profile) == 4
    assert s.battery is None


def test_scenario_requires_pv_and_load_columns():
    idx = pd.date_range("2024-06-01", periods=2, freq="h")
    df = pd.DataFrame({"load_kwh": [1.0, 1.0]}, index=idx)  # missing pv_kwh
    with pytest.raises(ValueError):
        Scenario(profile=df, tariff=Tariff(name="x"))


def test_indicators_is_frozen():
    ind = Indicators(energy_cost=1.0, self_consumption=0.5, self_sufficiency=0.4, grid_dependency=0.6)
    with pytest.raises(Exception):
        ind.energy_cost = 2.0  # type: ignore[misc]
