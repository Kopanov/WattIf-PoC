"""Configuration: read environment, select providers, hold demo defaults.

Defaults theme the demo to northern France (Hauts-de-France), which aligns with the
ODEON French pilot region (SICAE) and is climatically close to the Low Carbon London
load profiles we use as an EU load proxy.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # load .env if present; silently no-op otherwise


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM ---
    llm_provider: str = "local"            # "local" (Ollama) or "anthropic"
    ollama_model: str = "llama3.1"
    ollama_host: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    # --- Data ---
    entsoe_api_token: str = ""
    use_cache: bool = True                 # prefer committed cached data over live APIs
    # --- Demo theming (northern France) ---
    lat: float = 49.894
    lon: float = 2.296
    tz: str = "Europe/Paris"
    bidding_zone: str = "FR"
    currency: str = "EUR"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "local").strip().lower(),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            entsoe_api_token=os.getenv("ENTSOE_API_TOKEN", ""),
            use_cache=_bool("WHATIF_USE_CACHE", True),
            lat=_float("WHATIF_LAT", 49.894),
            lon=_float("WHATIF_LON", 2.296),
            tz=os.getenv("WHATIF_TZ", "Europe/Paris"),
            bidding_zone=os.getenv("WHATIF_BIDDING_ZONE", "FR"),
            currency=os.getenv("WHATIF_CURRENCY", "EUR"),
        )


settings = Settings.from_env()
