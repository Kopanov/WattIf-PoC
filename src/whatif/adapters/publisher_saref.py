"""Publisher: serialize a scenario result to SAREF-aligned JSON-LD.

PoC writes to ``out/`` and returns the path. The JSON-LD is built directly (no rdflib needed
to emit); rdflib is used only to *validate* that it parses as RDF. Production posts the same
asset to the ODEON Results Explorer (``OdeonResultsPublisher`` — stub until award).

This backs the "we already speak your semantic model" claim: indicators are emitted as
SAREF Measurements aligned to SAREF / SAREF4ENER terms.
"""
from __future__ import annotations

import json
import os

from whatif.adapters.base import Publisher
from whatif.core.schema import Indicators, ScenarioParams

_CONTEXT = {
    "saref": "https://saref.etsi.org/core/",
    "s4ener": "https://saref.etsi.org/saref4ener/",
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "whatif": "https://coreideas.example/whatif#",
}

_PROPERTY = {
    "energy_cost": ("Energy cost", "EUR/year"),
    "self_consumption": ("Self-consumption ratio", "ratio"),
    "self_sufficiency": ("Self-sufficiency ratio", "ratio"),
    "grid_dependency": ("Grid dependency ratio", "ratio"),
}


def _measurements(indicators: Indicators, scenario_tag: str) -> list:
    out = []
    for field, (label, unit) in _PROPERTY.items():
        out.append(
            {
                "@type": "saref:Measurement",
                "whatif:scenario": scenario_tag,
                "saref:relatesToProperty": {"@type": "saref:Property", "rdfs:label": label},
                "saref:hasValue": round(float(getattr(indicators, field)), 6),
                "saref:isMeasuredIn": unit,
            }
        )
    return out


def to_jsonld(
    target_params: ScenarioParams,
    location: dict,
    base_ind: Indicators,
    wi_ind: Indicators,
    currency: str = "EUR",
) -> dict:
    """Build a SAREF-aligned JSON-LD document describing the scenario and its indicators."""
    context = dict(_CONTEXT)
    context["rdfs"] = "http://www.w3.org/2000/01/rdf-schema#"
    return {
        "@context": context,
        "@id": "urn:whatif:scenario:poc",
        "@type": "saref:Device",
        "rdfs:label": "WattIf what-if scenario (PoC, open data)",
        "saref:hasDescription": (
            "Residential what-if scenario computed by WattIf on open EU data. "
            "Descriptive only; no optimization or recommendation."
        ),
        "geo:lat": float(location.get("lat", 0.0)),
        "geo:long": float(location.get("lon", 0.0)),
        "whatif:locationName": location.get("name", "unknown"),
        "whatif:currency": currency,
        "whatif:parameters": {
            "whatif:pv_kwp": target_params.pv_kwp,
            "whatif:battery_kwh": target_params.battery_kwh,
            "whatif:battery_power_kw": target_params.battery_power_kw,
            "whatif:consumption_pct": target_params.consumption_pct,
            "whatif:ev": target_params.ev,
            "whatif:tariff": target_params.tariff_name,
        },
        "saref:makesMeasurement": (
            _measurements(base_ind, "baseline") + _measurements(wi_ind, "what-if")
        ),
    }


def publish_to_disk(doc: dict, out_dir: str = "out", filename: str = "scenario.jsonld") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
    return path


def validate(doc: dict) -> "tuple[bool, int]":
    """Validate the JSON-LD parses as RDF. Returns (ok, n_triples). rdflib is optional."""
    try:
        from rdflib import Graph
    except Exception:
        return (False, 0)
    g = Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    n = len(g)
    return (n > 0, n)


class SarefPublisher(Publisher):
    """PoC publisher: write SAREF JSON-LD to ``out/`` and return the path."""

    def __init__(self, out_dir: str = "out") -> None:
        self.out_dir = out_dir

    def publish(self, scenario_result: dict) -> str:
        return publish_to_disk(scenario_result, self.out_dir)


class OdeonResultsPublisher(Publisher):
    """Production swap point: POST the result asset to the ODEON Results Explorer."""

    def publish(self, scenario_result: dict) -> str:
        raise NotImplementedError(
            "ODEON Results Explorer publisher — POST derived asset via the API after award."
        )
