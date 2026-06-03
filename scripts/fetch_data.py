"""Download + cache the real PVGIS PV series for each EU demo location into data/samples/.

Run once (online) to populate committed snapshots; the demo then runs offline and key-free.
Falls back gracefully per-location (the app uses a clear-sky model if a city is uncached).

    python scripts/fetch_data.py
"""
from __future__ import annotations

import pandas as pd

from whatif.adapters import data_open
from whatif.core import profiles


def main() -> None:
    index = profiles.hourly_index()
    print(f"Caching PVGIS PV for {len(data_open.EU_LOCATIONS)} EU locations -> {data_open.SAMPLES_DIR}")
    for name, loc in data_open.EU_LOCATIONS.items():
        try:
            arr = data_open.pvgis_unit_pv(loc["lat"], loc["lon"])
            path = data_open._cache_path(name)
            pd.DataFrame({"pv_kwh": arr}).to_csv(path, index=False)
            print(f"  OK   {name:16s} annual {arr.sum():7.1f} kWh/kWp -> {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name:16s} {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
