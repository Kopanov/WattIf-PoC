"""WattIf — descriptive-only what-if simulator (PoC UI).

Run: ``streamlit run src/whatif/ui/streamlit_app.py``

The whole pipeline runs live here: ML touches inputs only → the deterministic engine computes
the three indicators exactly → exact attribution → a grounded, guardrailed explanation → a SAREF
JSON-LD export. Every section carries a plain-language guide, and there is never an advice or
optimization control anywhere (descriptive only — the Challenge-10 boundary).
"""
from __future__ import annotations

import os

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_folium import st_folium

from whatif import __version__
from whatif.adapters.data_open import EU_LOCATIONS, build_assets
from whatif.adapters.publisher_saref import publish_to_disk, to_jsonld, validate
from whatif.core.catalogue import (
    ATTRIBUTION_ORDER,
    INDICATOR_LABELS,
    PARAM_LABELS,
    SLIDER_RANGES,
    baseline_params,
    tariff_catalogue,
)
from whatif.core import guardrail
from whatif.core.indicators import energy_flows
from whatif.core.schema import ScenarioParams
from whatif.core.service import run_whatif

_FAV = os.path.join(os.path.dirname(__file__), "assets", "favicon.png")
st.set_page_config(page_title="WattIf — energy what-if simulator",
                   page_icon=_FAV if os.path.exists(_FAV) else "⚡", layout="wide")

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "out"))
HERO_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "assets", "hero.png"))
HOUSE_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "assets", "house.png"))

_WINDOWS = {
    "Summer week": "2023-07-10",
    "Winter week": "2023-01-16",
    "Spring week": "2023-04-10",
    "Autumn week": "2023-10-09",
}


# --------------------------------------------------------------------------- compute (cached)

@st.cache_data(show_spinner=False)
def _compute(location, annual_kwh, ev_kwh, pv_kwp, consumption_pct, ev, battery_kwh, battery_power, tariff_name):
    assets = build_assets(location, annual_kwh=annual_kwh, ev_kwh_per_day=ev_kwh,
                          use_cache=True, allow_network=True)
    base = baseline_params()
    target = ScenarioParams(pv_kwp, consumption_pct, ev, battery_kwh, battery_power, tariff_name)
    out = run_whatif(base, target, assets)  # rule-based (grounded template) narrative
    return {
        "base_ind": out.base_ind, "wi_ind": out.wi_ind, "deltas": out.deltas,
        "attribution": out.attribution, "narrative": out.narrative, "audit": out.audit,
        "guardrail_passed": out.guardrail_passed, "currency": out.currency,
        "flows_base": energy_flows(out.base_scn), "flows_wi": energy_flows(out.wi_scn),
        "location": assets.location, "base": base, "target": target,
        "saref": to_jsonld(target, assets.location, out.base_ind, out.wi_ind, out.currency),
    }


@st.cache_data(show_spinner=False)
def _llm_rephrase(template_text, backend, model):
    """Rephrase the grounded template with a local LLM, re-checked by the guardrail.
    Returns (text, status): status True = LLM used, False = blocked→fell back, None = unavailable."""
    from whatif.core import explainer
    try:
        if backend == "hf":
            from whatif.adapters.llm_hf import HFInferenceClient
            client = HFInferenceClient(model=model)
        else:
            from whatif.adapters.llm_local import OllamaClient
            client = OllamaClient(model=model)
        draft = explainer.phrase_with_llm(template_text, client)
        if draft and guardrail.check(draft).passed:
            return draft, True
        return template_text, False
    except Exception:
        return template_text, None


@st.cache_data(show_spinner=False)
def _forecast_week(location, annual_kwh, ev_kwh, pv_kwp, consumption_pct, ev, battery_kwh, battery_power, tariff_name):
    """Build a 7-day scenario driven by the LIVE Open-Meteo forecast (real weather → PV).
    Returns flows + 7-day indicators, or None if the weather service is unreachable."""
    from whatif.adapters.data_open import forecast_week_weather
    from whatif.core import profiles
    from whatif.core.catalogue import tariff_catalogue
    from whatif.core.indicators import compute_indicators, energy_flows
    from whatif.core.schema import BatteryConfig, Scenario

    wx = forecast_week_weather(location)
    if wx is None or len(wx) == 0:
        return None
    idx = wx.index
    load = profiles.synthesize_load_on(idx, annual_kwh) * (1.0 + consumption_pct / 100.0)
    if ev:
        load = load.add(profiles.ev_charging_profile(idx, kwh_per_day=ev_kwh), fill_value=0.0)
    pv = wx["unit_pv"] * float(pv_kwp)
    profile = pd.DataFrame({"load_kwh": load.to_numpy(float), "pv_kwh": pv.to_numpy(float)}, index=idx)
    battery = BatteryConfig(battery_kwh, battery_power, battery_power) if battery_kwh > 0 else None
    scn = Scenario(profile=profile, tariff=tariff_catalogue()[tariff_name], battery=battery, name="forecast-week")
    return {
        "flows": energy_flows(scn),
        "ind": compute_indicators(scn),
        "temp_mean": float(wx["temp_c"].mean()),
        "start": str(idx[0].date()),
        "end": str(idx[-1].date()),
    }


def guide(body: str, expanded: bool, title: str = "ℹ️ Guide — what am I looking at?"):
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def _sym(cur: str) -> str:
    return {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur, "")


def _money(v: float, cur: str) -> str:
    return f"-{cur}{abs(v):,.0f}" if v < 0 else f"{cur}{v:,.0f}"


def _profile_chart(fw, fb=None):
    """Energy profile figure for a flows frame (what-if), optional baseline overlay."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=fw.index, y=fw["load_kwh"], name="Load (what-if)",
                             line=dict(color="#1f77b4")), secondary_y=False)
    if fb is not None:
        fig.add_trace(go.Scatter(x=fb.index, y=fb["load_kwh"], name="Load (baseline)",
                                 line=dict(color="#1f77b4", dash="dot", width=1)), secondary_y=False)
    fig.add_trace(go.Scatter(x=fw.index, y=fw["pv_kwh"], name="PV",
                             line=dict(color="#ff7f0e")), secondary_y=False)
    fig.add_trace(go.Scatter(x=fw.index, y=fw["import_kwh"], name="Grid import",
                             line=dict(color="#d62728"), fill="tozeroy", opacity=0.3), secondary_y=False)
    if "soc_kwh" in fw.columns:
        fig.add_trace(go.Scatter(x=fw.index, y=fw["soc_kwh"], name="Battery SoC",
                                 line=dict(color="#2ca02c", dash="dash")), secondary_y=True)
        fig.update_yaxes(title_text="Battery SoC (kWh)", secondary_y=True)
    fig.update_yaxes(title_text="Energy per hour (kWh)", secondary_y=False)
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12))
    return fig


# --------------------------------------------------------------------------- header + provenance

st.markdown(
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@500;600;800&display=swap');"
    ".wattif-eyebrow{font-family:'Rubik',sans-serif;font-weight:600;font-size:0.9rem;color:#2c7fb8;"
    "text-transform:uppercase;letter-spacing:2.5px;margin-bottom:4px;}"
    ".wattif-wordmark{font-family:'Rubik',sans-serif;font-weight:800;font-size:4.4rem;color:#1f4e6b;"
    "line-height:1.0;letter-spacing:-1.5px;margin:0;}"
    ".wattif-wordmark .accent{color:#2c7fb8;}"
    ".wattif-tagline{font-family:'Rubik',sans-serif;font-weight:500;font-size:1.06rem;color:#46586a;"
    "margin-top:10px;max-width:36rem;}"
    "</style>",
    unsafe_allow_html=True,
)
_hl, _hr = st.columns([3, 1], vertical_alignment="center")
with _hl:
    st.markdown(
        "<div class='wattif-eyebrow'>⚡ Energy what-if simulator</div>"
        "<div class='wattif-wordmark'>Watt<span class='accent'>If</span></div>"
        "<div class='wattif-tagline'>See how solar, batteries &amp; tariffs change your cost, "
        "self-consumption and grid use — clearly, with <b>no advice</b>.</div>",
        unsafe_allow_html=True,
    )
with _hr:
    if os.path.exists(HOUSE_PATH):
        st.image(HOUSE_PATH, use_container_width=True)
st.caption("ODEON Open Call #1, Challenge 10 — *Improving Prosumer Understanding Through What-If "
           "Scenario Analysis* · Proof of Concept by Core Ideas Ltd.")

st.markdown("#### How it works — the idea in three steps")
_s1, _s2, _s3 = st.columns(3)
with _s1:
    with st.container(border=True, height=270):
        st.markdown(
            "**1 · 📥 Inputs — data & forecasts**\n\n"
            "Your household profile + a PV forecast.\n\n"
            "*Today:* open EU data + real **PVGIS**.\n"
            "*Production:* **ODEON** data space + an **ODEON AI forecast** artefact.\n\n"
            "_A small **trained ML model** (gradient-boosted trees) can also synthesise a profile "
            "for data-poor homes — in this PoC that step uses simple scaling._"
        )
with _s2:
    with st.container(border=True, height=270):
        st.markdown(
            "**2 · 🧮 Deterministic engine — the exact core**\n\n"
            "Plain energy-balance maths computes the three indicators and attributes every change.\n\n"
            "**No model, no prediction** — reproducible by anyone."
        )
with _s3:
    with st.container(border=True, height=270):
        st.markdown(
            "**3 · 🗣️ Explanation — plain language**\n\n"
            "A grounded template says *what changed and why* (always on).\n\n"
            "Optionally a **local LLM** rephrases the *same locked facts* — re-checked by the "
            "no-advice guardrail."
        )
st.caption("**The point:** the headline numbers are always computed **exactly**; the ML model and "
           "the LLM only ever touch the *inputs* and the *wording* — never the numbers, and never advice.")
st.write("")

st.info(
    "**This is a Proof of Concept running on open-source / synthetic EU data**, so anyone can "
    "reproduce it. The PV generation is **real data from PVGIS (EU Joint Research Centre)**; the "
    "household load is a **representative EU residential profile** (BDEW/Low-Carbon-London style); "
    "the EV shape is **ElaadNL-style**; tariffs are **modelled structures** (ENTSO-E is the "
    "wholesale price source). **In production these inputs are replaced by ODEON** — household data "
    "from the **ODEON Energy Data Space** and forecasts from **ODEON AI artefacts** — by swapping "
    "three adapters; the engine and explanations do not change.",
    icon="🔓",
)
st.warning(
    "**Descriptive only.** This tool shows *what changes and why a number moved* — it never gives "
    "advice, optimization, or personalized recommendations. That boundary is built in and "
    "demonstrated below (the explanation is checked by a no-advice guardrail).",
    icon="🛡️",
)
show_wt = st.toggle("📖 Show the full PoC walkthrough (expand every guide box)", value=True)

with st.expander("🔌 How this plugs into ODEON (the three swap points)", expanded=show_wt):
    st.markdown(
        "The PoC runs the **production pipeline** on open data through three swappable adapters — "
        "going live on ODEON means implementing these three, nothing else changes:\n\n"
        "- **Data** → *PoC:* open EU data + cached **PVGIS**. *Production:* **ODEON Energy Data Space**.\n"
        "- **Forecast** → *PoC:* **PVGIS / local stand-in** for PV. *Production:* an **ODEON AI "
        "artefact** (renewable-generation / load forecasting). ⟵ *this is the marked, **skipped** "
        "integration point — wired in the code path (`forecaster_odeon.py`) but not called in the PoC.*\n"
        "- **Publish** → *PoC:* **SAREF JSON-LD** to disk. *Production:* **ODEON Results Explorer**.\n\n"
        "The core — engine, attribution, guardrail, SAREF output — is identical in both."
    )

st.divider()


# --------------------------------------------------------------------------- sidebar controls

st.sidebar.header("📍 Location")
st.session_state.setdefault("location", "Amiens, FR")
loc_names = list(EU_LOCATIONS.keys())
sel = st.sidebar.selectbox(
    "Where do you live?", loc_names, index=loc_names.index(st.session_state.location),
    help="Sets the location for the real PVGIS PV, weather and price zone. EU only.",
)
# A selectbox change applies in this same run; only the map click needs an explicit rerun.
st.session_state.location = sel
location = sel

st.sidebar.header("🏠 Your household (baseline)")
annual_kwh = st.sidebar.slider(
    "Annual consumption (kWh)", 1500, 6000, 3500, 250,
    help="Your current yearly electricity use. The baseline is this household with "
         "3 kWp PV, no battery, on a flat tariff.",
)

st.sidebar.header("🔧 What-if parameters")
pv_lo, pv_hi, pv_step = SLIDER_RANGES["pv_kwp"]
pv_kwp = st.sidebar.slider("PV system size (kWp)", pv_lo, pv_hi, 4.0, pv_step)
bat_lo, bat_hi, bat_step = SLIDER_RANGES["battery_kwh"]
battery_kwh = st.sidebar.slider("Battery capacity (kWh)", bat_lo, bat_hi, 5.0, bat_step,
                                help="0 = no battery. Dispatch maximizes self-consumption.")
bp_lo, bp_hi, bp_step = SLIDER_RANGES["battery_power_kw"]
battery_power = st.sidebar.slider("Battery power (kW)", bp_lo, bp_hi, 2.5, bp_step)
tariff_name = st.sidebar.selectbox("Tariff", list(tariff_catalogue().keys()), index=0)
c_lo, c_hi, c_step = SLIDER_RANGES["consumption_pct"]
consumption_pct = st.sidebar.slider("Consumption change (%)", c_lo, c_hi, 0, c_step,
                                    help="Apply a uniform change to your load (e.g. -10%).")
ev = st.sidebar.toggle("Add an electric vehicle", value=False)
ev_lo, ev_hi, ev_step = SLIDER_RANGES["ev_kwh_per_day"]
ev_kwh = st.sidebar.slider("EV charging (kWh/day)", ev_lo, ev_hi, 8.0, ev_step, disabled=not ev)

st.sidebar.divider()
st.sidebar.caption("Baseline = your current setup: **3 kWp PV, no battery, Flat tariff**. "
                   "Move the sliders to compare a what-if against it.")

R = _compute(location, annual_kwh, ev_kwh, pv_kwp, consumption_pct, ev,
             battery_kwh, battery_power, tariff_name)
cur = _sym(R["currency"])


# --------------------------------------------------------------------------- location + map

left, right = st.columns([1, 1])
with left:
    st.subheader("📍 Where you live")
    st.write(f"**{location}** — PV forecast: **{R['location']['pv_source']}** "
             "*(PoC stand-in for the ODEON forecast artefact)*")
    st.caption(f"Latitude {R['location']['lat']:.3f}, longitude {R['location']['lon']:.3f} · "
               f"price zone {R['location']['country']}")
    guide(
        "Click a marker (or anywhere) on the map to choose where you live — it snaps to the "
        "nearest EU example city. Your location sets the **real PVGIS** solar profile, so a sunnier "
        "city visibly raises PV output. This is just an **input** — the tool never suggests *where* "
        "to live or *what* to install.",
        expanded=show_wt,
    )
with right:
    # Map removed from the hosted demo: re-embedding the leaflet iframe on every rerun was the
    # payload the free Space websocket dropped (white screen on any interaction). City selection
    # is via the sidebar Location selector; PV and prices update for the chosen city. A light
    # static panel replaces the map so reruns carry a tiny delta.
    _names = ", ".join(n.split(",")[0] for n in EU_LOCATIONS)
    st.markdown(
        "<div style='border:1px solid #e3e8ef;border-radius:10px;padding:18px 20px;"
        "background:#f7f9fc'><div style='font-size:1.15rem'>\U0001F4CD <b>" + str(location) +
        "</b></div><div style='color:#5b6b7b;margin-top:6px'>Available EU locations: " + _names +
        ". Switch from the <b>Location</b> selector in the sidebar; the PV yield and prices update "
        "for the chosen city.</div></div>",
        unsafe_allow_html=True,
    )

st.divider()


# --------------------------------------------------------------------------- indicator cards

st.subheader("📊 The three indicators (based on sample open-source data)")
b, w, d = R["base_ind"], R["wi_ind"], R["deltas"]
m1, m2, m3 = st.columns(3)
m1.metric("Energy cost", f"{_money(w.energy_cost, cur)}/yr",
          f"{d['energy_cost']:+,.0f} {R['currency']}/yr vs baseline", delta_color="off")
m2.metric("Self-consumption", f"{w.self_consumption*100:.0f}%",
          f"{d['self_consumption']*100:+.0f} pts vs baseline", delta_color="off")
m3.metric("Grid dependency", f"{w.grid_dependency*100:.0f}%",
          f"{d['grid_dependency']*100:+.0f} pts vs baseline", delta_color="off")
st.caption(f"Baseline: cost {cur}{b.energy_cost:,.0f}/yr · self-consumption "
           f"{b.self_consumption*100:.0f}% · grid dependency {b.grid_dependency*100:.0f}%. "
           "Deltas are shown in neutral grey on purpose — no value judgement.")
guide(
    "These three numbers are **computed exactly** by energy-balance accounting (no model, no "
    "prediction), so a third party can reproduce them:\n\n"
    "- **Energy cost** = Σ(import × import price) − Σ(export × export price) + fixed charge\n"
    "- **Self-consumption** = (Σ PV − Σ export) / Σ PV — share of your PV used on site\n"
    "- **Grid dependency** = Σ import / Σ load — share of your load drawn from the grid\n\n"
    "With a battery, import/export come from a deterministic state-of-charge dispatch (physics, "
    "not ML).",
    expanded=show_wt,
)
st.divider()


# --------------------------------------------------------------------------- profile chart

st.subheader("🔌 Energy profile — baseline vs what-if")
_WEATHER_OPT = "🌤️ Next 7 days (live weather)"
win = st.segmented_control("Chart window",
                           list(_WINDOWS.keys()) + ["Full year (daily)", _WEATHER_OPT],
                           default="Summer week", selection_mode="single",
                           key="chart_window") or "Summer week"

if "live weather" in str(win).lower():  # emoji-agnostic match (survives session-state round-trips)
    with st.spinner("Fetching the live Open-Meteo forecast…"):
        fc = _forecast_week(location, annual_kwh, ev_kwh, pv_kwp, consumption_pct, ev,
                            battery_kwh, battery_power, tariff_name)
    if fc is None:
        st.warning("Live weather (Open-Meteo) is unavailable right now — pick another window above.")
    else:
        st.caption(f"Real **Open-Meteo** forecast for **{location}**, {fc['start']} → {fc['end']} "
                   f"· avg temp **{fc['temp_mean']:.0f} °C** · PV is driven by the live irradiance "
                   "forecast. Forecasts are short-term, so the annual indicators above stay on "
                   "historical / seasonal data.")
        _wi = fc["ind"]
        _w1, _w2, _w3 = st.columns(3)
        _w1.metric("This week — cost", _money(_wi.energy_cost, cur))
        _w2.metric("This week — self-consumption", f"{_wi.self_consumption * 100:.0f}%")
        _w3.metric("This week — grid dependency", f"{_wi.grid_dependency * 100:.0f}%")
        st.plotly_chart(_profile_chart(fc["flows"]), use_container_width=True)
else:
    def _slice(df):
        if win == "Full year (daily)":
            agg = df.resample("D").sum()
            if "soc_kwh" in df:
                agg["soc_kwh"] = df["soc_kwh"].resample("D").mean()
            return agg
        start = _WINDOWS[win]
        end = start[:8] + f"{int(start[8:]) + 6:02d}"  # +6 days within the month
        return df.loc[start:end]

    st.plotly_chart(_profile_chart(_slice(R["flows_wi"]), _slice(R["flows_base"])),
                    use_container_width=True)
guide(
    "The same household, **baseline (dotted)** vs **what-if (solid)**. Load is blue, PV is orange, "
    "the red shaded area is what you still draw from the grid, and the green dashed line is the "
    "battery's state of charge. Watch the grid-import area shrink as PV and the battery cover more "
    "of the evening load. Pick **🌤️ Next 7 days (live weather)** to drive PV from a **real "
    "Open-Meteo forecast** for your location — the same engine, on the actual coming weather "
    "instead of the seasonal average.",
    expanded=show_wt,
)
st.divider()


# --------------------------------------------------------------------------- attribution waterfall

st.subheader("🧩 What drove the change? (exact attribution)")
ind_key = st.segmented_control("Indicator", list(INDICATOR_LABELS.keys()),
                               format_func=lambda k: INDICATOR_LABELS[k],
                               default="energy_cost", selection_mode="single",
                               key="attr_indicator") or "energy_cost"
changed = [f for f in ATTRIBUTION_ORDER if R["base"].as_dict()[f] != R["target"].as_dict()[f]]
if not changed:
    st.info("No parameters changed yet — move a slider to see the breakdown.")
else:
    is_cost = ind_key == "energy_cost"
    scale = 1.0 if is_cost else 100.0
    vals = [R["attribution"][f][ind_key] * scale for f in changed]
    labels = [PARAM_LABELS[f] for f in changed]
    total = sum(vals)

    def _fmt(v):
        if is_cost:
            return f"+{cur}{v:,.0f}" if v >= 0 else f"-{cur}{abs(v):,.0f}"
        return f"{v:+.1f} pts"

    # Diverging bars from a 0 baseline: each parameter goes up or down from zero, then the net.
    fig2 = go.Figure(go.Bar(
        x=labels + ["Net change"],
        y=vals + [total],
        marker_color=["#6699CC"] * len(vals) + ["#B07AA1"],
        text=[_fmt(v) for v in vals + [total]],
        textposition="outside",
    ))
    fig2.add_hline(y=0, line_color="#aaaaaa", line_width=1)  # baseline
    fig2.add_hline(y=total, line_dash="dash", line_color="#B07AA1",  # where it all balances out
                   annotation_text=f"net {_fmt(total)}", annotation_position="top left")
    fig2.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
                       yaxis_title=("Cost change (" + cur + ")") if is_cost else "Change (pts)")
    st.plotly_chart(fig2, use_container_width=True)
guide(
    "Because the engine is an **exact function**, attribution is exact too — no SHAP, no "
    "approximation. We step from the baseline to your what-if **one change at a time** and record "
    "each change's effect. **Each bar rises or falls from the zero line**, and the **dashed line "
    "marks the net** — so you can see how the ups and downs balance out. The bars **sum exactly to "
    "that net change** (often large effects cancel — e.g. an EV adds cost while a bigger PV system "
    "removes it).",
    expanded=show_wt,
)
st.divider()


# --------------------------------------------------------------------------- narrative + audit

st.subheader("📝 Plain-language explanation")
st.caption("Both answers describe the **same computed facts** — pick how they are worded.")
exp_mode = st.segmented_control(
    "Answer style", ["📐 Rule-based", "🧠 LLM-based"],
    default="📐 Rule-based", selection_mode="single", key="answer_style") or "📐 Rule-based"

narrative = R["narrative"]
if exp_mode == "🧠 LLM-based":
    import os
    from whatif.adapters.llm_local import list_models
    from whatif.adapters.llm_hf import hf_available, DEFAULT_HF_MODEL
    _local = list_models()
    if _local:
        _model = _local[0]
        with st.spinner(f"Rephrasing the same facts with {_model}…"):
            narrative, status = _llm_rephrase(R["narrative"], "ollama", _model)
        if status is True:
            src = (f"**local LLM — `{_model}`** running on your machine (no data leaves it); "
                   "the guardrail re-checked the wording")
        elif status is False:
            src = f"rule-based template — the `{_model}` draft was blocked by the guardrail, so we fell back"
        else:
            src = f"rule-based template — `{_model}` was unavailable, so we fell back"
    elif hf_available():
        _model = os.getenv("WHATIF_HF_MODEL", DEFAULT_HF_MODEL)
        with st.spinner(f"Rephrasing the same facts with {_model} (HF Inference)…"):
            narrative, status = _llm_rephrase(R["narrative"], "hf", _model)
        if status is True:
            src = f"**HF Inference — `{_model}`** (free serverless); the guardrail re-checked the wording"
        elif status is False:
            src = f"rule-based template — the `{_model}` draft was blocked by the guardrail, so we fell back"
        else:
            src = f"rule-based template — `{_model}` was rate-limited or unavailable, so we fell back"
    else:
        src = "rule-based template — no LLM backend available"
        st.info("No LLM backend available. Locally, run Ollama (e.g. `ollama pull llama3.1`); "
                "on the hosted demo, set an `HF_TOKEN` secret to enable the LLM answer.")
else:
    src = "**rule-based** — a deterministic template that fills the computed facts into fixed slots"

st.markdown(
    "<div style='color:#0e1117; font-size:1.06rem; line-height:1.6; background:#f7f9fc; "
    "border:1px solid #e3e8ef; border-left:4px solid #2c7fb8; border-radius:8px; "
    f"padding:16px 20px'>{narrative}</div>",
    unsafe_allow_html=True,
)
st.write("")
badge = "✅ passed" if guardrail.check(narrative).passed else "⛔ blocked"
st.caption(f"No-advice guardrail: **{badge}** · explanation source: {src}")
with st.expander("🔎 Audit — how this explanation is kept honest", expanded=show_wt):
    aud = R["audit"]
    st.markdown("**Why it cannot hallucinate a number or a cause:** the explanation is built by "
                "filling descriptive slots with values copied from the indicator engine *before* "
                "any language is produced. There is no slot for advice.")
    st.markdown(f"**Method:** {aud.get('method', 'n/a')}")
    gr = aud.get("guardrail", {})
    st.markdown(f"**Guardrail verdict:** {gr.get('verdict', 'n/a')}")
    st.markdown("**Checks run:**")
    for c in gr.get("checks_run", []):
        st.markdown(f"- {c}")
    if gr.get("matches"):
        st.markdown(f"**Advice phrases found:** {gr['matches']}")
    st.markdown("**Facts used:**")
    st.json(aud.get("facts_used", {}), expanded=False)
guide(
    "The explanation **describes** the computed result and the exact cause; it is forbidden from "
    "**prescribing**. A second guardrail re-scans the text for any advice/optimization wording and "
    "would block it. Try it: the red-team check (`scripts/redteam_demo.py`) shows advice phrasings "
    "being caught 100% of the time.",
    expanded=show_wt,
)
st.divider()


# --------------------------------------------------------------------------- SAREF export

st.subheader("🧾 Export — SAREF / IEC-CIM JSON-LD")
import json as _json

doc = R["saref"]
ok, n_triples = validate(doc)
path = publish_to_disk(doc, out_dir=OUT_DIR)
c1, c2 = st.columns([1, 2])
with c1:
    st.download_button("⬇️ Download SAREF JSON-LD", data=_json.dumps(doc, indent=2),
                       file_name="whatif_scenario.jsonld", mime="application/ld+json")
    st.caption(f"Validates as RDF: **{'yes' if ok else 'no'}** ({n_triples} triples)")
with c2:
    with st.expander("Preview the JSON-LD", expanded=False):
        st.json(doc, expanded=False)
guide(
    "The scenario and its indicators are exported as **SAREF-aligned JSON-LD** — the same semantic "
    "model ODEON uses (SAREF / IEC CIM). This is what proves *we already speak ODEON's language*: "
    "in production the Publisher posts this exact asset to the **ODEON Results Explorer** instead of "
    "writing it to disk.",
    expanded=show_wt,
)

st.divider()


# --------------------------------------------------------------------------- roadmap

st.subheader("🚀 Roadmap — from this PoC to ODEON")
st.caption("What today's demo proves, what the funded project adds, and how it fits ODEON.")
_r1, _r2, _r3 = st.columns(3)
with _r1:
    with st.container(border=True, height=330):
        st.markdown(
            "**✅ This PoC demonstrates**\n\n"
            "- Exact, **reproducible** indicators + exact attribution\n"
            "- Provably **descriptive** explanation (rule-based + optional local LLM) with a "
            "no-advice guardrail\n"
            "- **SAREF / IEC-CIM** JSON-LD export\n"
            "- Runs on **open EU data** (real PVGIS + representative profiles), key-free"
        )
with _r2:
    with st.container(border=True, height=330):
        st.markdown(
            "**🔜 The funded project adds**\n\n"
            "- A **trained profile feeder** (gradient-boosted trees) + a *generated-beats-scaled* "
            "realism benchmark\n"
            "- Real **ODEON integration**: Energy Data Space data, PV/load forecasts from **ODEON "
            "AI artefacts**, results to the **Results Explorer**\n"
            "- Validation with **real prosumers** at a pilot site (FR/ES/GR/DK/IE) + transparency KPIs\n"
            "- Live ENTSO-E prices, more assets (heat pump), richer scenarios"
        )
with _r3:
    with st.container(border=True, height=330):
        st.markdown(
            "**🧩 Aligned with ODEON requirements**\n\n"
            "- **API-centric**: three swappable adapters, no platform duplication\n"
            "- Speaks the ODEON **Semantic Data Model** (SAREF / IEC CIM)\n"
            "- **Descriptive-only** — complements, doesn't overlap, ODEON's prosumer services\n"
            "- Results **open-source**, offered to the ODEON ecosystem"
        )

st.divider()
st.caption(f"WattIf v{__version__} · PoC for ODEON (Horizon Europe, GA No. 101136128). "
           "Open-source EU data today; ODEON Energy Data Space + AI artefacts in production. "
           "Descriptive only — no recommendations.")
