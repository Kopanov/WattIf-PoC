"""FastAPI application — serves the SAME core logic as the UI, with adapters injected.

This is the M8 seam: the UI and the API both call ``service.run_whatif``, so a reviewer can
hit the pipeline programmatically and get identical, exact, descriptive-only results. ``fastapi``
and ``pydantic`` are imported lazily inside ``create_app`` so importing this module — and the
``whatif`` package — never requires the API extra.

    uvicorn "whatif.api.app:create_app" --factory --port 8000
"""
# NOTE: no `from __future__ import annotations` here — FastAPI must see the real (locally
# defined) Pydantic model class on the endpoint signature, not a string forward-ref.


def create_app():
    from fastapi import FastAPI
    from pydantic import BaseModel

    from whatif import __version__

    from whatif.adapters.data_open import EU_LOCATIONS, build_assets
    from whatif.adapters.publisher_saref import to_jsonld
    from whatif.core.catalogue import baseline_params, tariff_catalogue
    from whatif.core.schema import ScenarioParams
    from whatif.core.service import run_whatif

    app = FastAPI(
        title="WattIf API (PoC)",
        version=__version__,
        description="Descriptive-only what-if engine for residential prosumers (ODEON Challenge 10).",
    )

    class WhatIfRequest(BaseModel):
        location: str = "Amiens, FR"
        annual_kwh: float = 3500.0
        pv_kwp: float = 4.0
        consumption_pct: float = 0.0
        ev: bool = False
        ev_kwh_per_day: float = 8.0
        battery_kwh: float = 5.0
        battery_power_kw: float = 2.5
        tariff_name: str = "Flat"

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "whatif"}

    @app.get("/locations")
    def locations() -> list:
        return list(EU_LOCATIONS.keys())

    @app.get("/tariffs")
    def tariffs() -> list:
        return list(tariff_catalogue().keys())

    @app.post("/whatif")
    def whatif(req: WhatIfRequest) -> dict:
        assets = build_assets(req.location, annual_kwh=req.annual_kwh,
                              ev_kwh_per_day=req.ev_kwh_per_day)
        out = run_whatif(
            baseline_params(),
            ScenarioParams(req.pv_kwp, req.consumption_pct, req.ev,
                           req.battery_kwh, req.battery_power_kw, req.tariff_name),
            assets,
        )
        return {
            "location": assets.location,
            "baseline": out.base_ind.__dict__,
            "whatif": out.wi_ind.__dict__,
            "deltas": out.deltas,
            "attribution": out.attribution,
            "narrative": out.narrative,
            "guardrail_passed": out.guardrail_passed,
            "audit": out.audit,
            "saref_jsonld": to_jsonld(
                ScenarioParams(req.pv_kwp, req.consumption_pct, req.ev,
                               req.battery_kwh, req.battery_power_kw, req.tariff_name),
                assets.location, out.base_ind, out.wi_ind, out.currency,
            ),
        }

    return app
