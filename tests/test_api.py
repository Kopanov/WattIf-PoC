"""FastAPI wrapper serves the same exact, descriptive-only results as the UI (M8)."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from whatif.api.app import create_app  # noqa: E402

client = TestClient(create_app())


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_locations_include_amiens():
    assert "Amiens, FR" in client.get("/locations").json()


def test_whatif_returns_exact_descriptive_result():
    r = client.post("/whatif", json={"location": "Amiens, FR", "pv_kwp": 4.0,
                                     "battery_kwh": 5.0, "ev": True, "tariff_name": "Flat"})
    assert r.status_code == 200
    d = r.json()
    for key in ("baseline", "whatif", "deltas", "attribution", "narrative", "guardrail_passed"):
        assert key in d
    assert d["guardrail_passed"] is True
    # attribution sums to the total delta for energy cost (exactness via the API)
    total = sum(d["attribution"][f]["energy_cost"] for f in d["attribution"])
    assert total == pytest.approx(d["deltas"]["energy_cost"], abs=1e-6)
