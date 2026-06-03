<div align="center">

<img src="src/whatif/ui/assets/favicon.png" width="130" alt="WattIf logo" />

# WattIf

**energy what-if simulator**

See how solar, batteries, tariffs and an EV change your home's **energy cost, self-consumption and grid dependency** — clearly, and with **no advice**.

</div>

---

## What it is

WattIf is a **descriptive-only** what-if sandbox for home energy. Adjust a few inputs — PV size,
battery, tariff, consumption, EV, location — and instantly see the impact on three high-level
indicators, with a plain-language explanation of *why* each number moved. It never tells you what to
do; it shows what changes.

## How it works

One rule governs the whole stack: **the headline numbers are always computed exactly; the ML model
and the language model only ever touch the *inputs* and the *wording* — never the numbers, and never
advice.**

**1 · 📥 Inputs — data & forecasts.** Your household profile plus a PV forecast. PV uses real open
data (**PVGIS**) for the chosen location; a live‑weather view uses **Open‑Meteo** for the next 7 days.
*(A small trained model can synthesise a profile for data‑poor homes; this PoC uses simple scaling.)*

**2 · 🧮 Deterministic engine — the exact core.** Plain energy‑balance maths computes the three
indicators and attributes every change. No prediction, fully reproducible by anyone.

**3 · 🗣️ Explanation — plain language.** A grounded template states what changed and why; optionally a
local LLM (**Ollama**) rephrases the *same locked facts*, re‑checked by a no‑advice guardrail.

### The three indicators
- **Energy cost** — Σ(import × price) − Σ(export × price) + fixed charge
- **Self‑consumption** — share of your PV used on site
- **Grid dependency** — share of your load drawn from the grid

## Features

- Real **PVGIS** solar data per location + an interactive **OpenStreetMap** "choose where you live" picker
- **Live weather** view (Open‑Meteo) — the next 7 days drive PV
- Deterministic **battery** dispatch, flat & **time‑of‑use** tariffs, **EV** add‑on
- **Exact attribution** (no SHAP) — the bars sum to the total change
- **Grounded explanation** + optional local LLM, both behind a demonstrable **no‑advice guardrail**
- **SAREF / IEC‑CIM JSON‑LD** export
- Runs on open / synthetic data — **no API keys required**

## Quick start

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ui,pv,data,semantics]"
streamlit run streamlit_app.py        # → http://localhost:8501
pytest                                 # run the test suite
```

No keys needed. Optional: a local **Ollama** model enables the LLM‑phrased explanation; an Anthropic
key (server‑side, via `.env`) is an alternative. Copy `.env.example` → `.env` only if you want those.

## Architecture

The core — engine, attribution, guardrail, SAREF output — is fixed. Three **swappable adapters**
isolate the outside world, so the same logic runs on open data today and against a real energy‑data
platform's APIs in production:

- **Data** — household profiles & tariffs
- **Forecaster** — PV / load forecasts
- **Publisher** — results as SAREF JSON‑LD

```
src/whatif/
  core/       exact engine · battery · attribution · explainer · guardrail
  adapters/   data · forecaster · publisher · LLM   (swappable)
  ui/         Streamlit app
  api/        FastAPI wrapper
tests/        exactness · attribution‑sums‑to‑delta · guardrail · API
```

## Tech

Python · Streamlit · Plotly · pandas / NumPy · pvlib / PVGIS · Open‑Meteo · rdflib (SAREF) ·
FastAPI · optional Ollama / Anthropic.

## Deploy

Runs unchanged on **Replit** or **Hugging Face Spaces** (both just run Streamlit) — no API keys, since
PV data is cached and the explainer is local. Entry point: `streamlit_app.py`; dependencies in
`requirements.txt`.

## License

[Apache‑2.0](LICENSE).
