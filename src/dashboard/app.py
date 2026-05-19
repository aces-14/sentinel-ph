"""
SentinelPH — Philippines Dengue Risk Monitor
No-scroll, single-page dashboard. Right panel is the feature area.
Data: OpenDengue V1.3 (Philippines, 1999–2023)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SentinelPH — Dengue Risk Monitor",
    page_icon=":material/monitor_heart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Secrets bridge ────────────────────────────────────────────────────────────
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ.setdefault("GROQ_API_KEY", st.secrets["GROQ_API_KEY"])
except Exception:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR      = Path("data/processed")
BRIEFINGS_DIR = Path("data/processed/weekly_briefings")

# ── Palette ───────────────────────────────────────────────────────────────────
P = dict(
    bg      = "#0F172A",
    panel   = "#1E293B",
    panel2  = "#141D2D",
    border  = "#2D3F55",
    border2 = "#1E2D3F",
    text    = "#F1F5F9",
    muted   = "#64748B",
    sub     = "#94A3B8",
    teal    = "#0EA5A4",
    red     = "#EF4444",
    amber   = "#F59E0B",
    blue    = "#3B82F6",
    green   = "#22C55E",
)

_RISK_COLOR = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#0EA5A4"}
_RISK_LABEL = {"HIGH": "HIGH RISK", "MEDIUM": "MODERATE", "LOW": "LOW RISK"}

# ── Region coordinates ────────────────────────────────────────────────────────
_REGION_COORDS: dict[str, tuple[float, float]] = {
    "AUTONOMOUS REGION IN MUSLIM MINDANAO (ARMM)":             (6.9,  124.3),
    "BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO (BARMM)": (6.9,  124.3),
    "CORDILLERA ADMINISTRATIVE REGION (CAR)":                  (17.4, 121.2),
    "NATIONAL CAPITAL REGION (NCR)":                           (14.6, 121.0),
    "REGION 4":                                                (13.8, 121.5),
    "REGION CARAGA (CARAGA)":                                  (9.2,  125.8),
    "REGION I (ILOCOS REGION)":                                (17.6, 120.4),
    "REGION II (CAGAYAN VALLEY)":                              (17.6, 121.7),
    "REGION III (CENTRAL LUZON)":                              (15.5, 120.9),
    "REGION IV-A (CALABARZON)":                                (14.1, 121.1),
    "REGION IV-B (MIMAROPA)":                                  (11.5, 120.5),
    "REGION IX (ZAMBOANGA PENINSULA)":                         (8.1,  123.3),
    "REGION V (BICOL REGION)":                                 (13.4, 123.4),
    "REGION VI (WESTERN VISAYAS)":                             (11.0, 122.5),
    "REGION VII (CENTRAL VISAYAS)":                            (10.3, 123.9),
    "REGION VIII (EASTERN VISAYAS)":                           (11.3, 124.9),
    "REGION X (NORTHERN MINDANAO)":                            (8.0,  124.7),
    "REGION XI (DAVAO REGION)":                                (7.1,  125.6),
    "REGION XII (SOCCSKSARGEN)":                               (6.3,  124.7),
    "REGION XIII (CARAGA)":                                    (9.2,  125.8),
}

_REGION_SHORT: dict[str, str] = {
    "AUTONOMOUS REGION IN MUSLIM MINDANAO (ARMM)":             "ARMM",
    "BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO (BARMM)": "BARMM",
    "CORDILLERA ADMINISTRATIVE REGION (CAR)":                  "CAR",
    "NATIONAL CAPITAL REGION (NCR)":                           "NCR",
    "REGION 4":                                                "Region 4",
    "REGION CARAGA (CARAGA)":                                  "Caraga",
    "REGION I (ILOCOS REGION)":                                "Ilocos",
    "REGION II (CAGAYAN VALLEY)":                              "Cagayan Valley",
    "REGION III (CENTRAL LUZON)":                              "Central Luzon",
    "REGION IV-A (CALABARZON)":                                "CALABARZON",
    "REGION IV-B (MIMAROPA)":                                  "MIMAROPA",
    "REGION IX (ZAMBOANGA PENINSULA)":                         "Zamboanga",
    "REGION V (BICOL REGION)":                                 "Bicol",
    "REGION VI (WESTERN VISAYAS)":                             "W. Visayas",
    "REGION VII (CENTRAL VISAYAS)":                            "C. Visayas",
    "REGION VIII (EASTERN VISAYAS)":                           "E. Visayas",
    "REGION X (NORTHERN MINDANAO)":                            "N. Mindanao",
    "REGION XI (DAVAO REGION)":                                "Davao",
    "REGION XII (SOCCSKSARGEN)":                               "SOCCSKSARGEN",
    "REGION XIII (CARAGA)":                                    "Caraga XIII",
}

# ── Nav config ────────────────────────────────────────────────────────────────
_NAV = [
    ("explore", ":material/bar_chart:",        "Explore Data"),
    ("chat",    ":material/chat:",             "Ask AI"),
    ("tips",    ":material/health_and_safety:","Prevention"),
    ("report",  ":material/lab_research:",     "Report"),
]


# ── CSS ───────────────────────────────────────────────────────────────────────
def _css() -> None:
    st.markdown(f"""
<style>
/* ── Chrome ── */
#MainMenu, footer, header        {{ visibility: hidden; }}
[data-testid="collapsedControl"] {{ display: none; }}
[data-testid="stSidebar"]        {{ display: none; }}

/* ── Base ── */
html, body {{ background:{P["bg"]}; overflow:hidden; }}
.stApp     {{ background:{P["bg"]}; }}
.block-container {{
    padding:0.9rem 2.0rem 0.4rem !important;
    max-width:100% !important;
}}
html,body,[class*="css"] {{
    font-family:'Inter','Segoe UI',Roboto,sans-serif;
}}

/* ── Header ── */
.app-header {{
    display:flex; align-items:center; gap:14px; margin-bottom:9px;
}}
.brand {{
    font-size:1.35rem; font-weight:900; color:{P["text"]};
    letter-spacing:-0.02em; line-height:1;
}}
.brand em {{ font-style:normal; color:{P["teal"]}; }}
.tagline {{
    font-size:0.72rem; color:{P["muted"]};
    border-left:2px solid {P["border"]}; padding-left:12px; line-height:1.45;
}}
.data-badge {{
    margin-left:auto; font-size:0.64rem; color:{P["muted"]};
    background:{P["panel"]}; border:1px solid {P["border"]};
    border-radius:20px; padding:3px 11px;
}}

/* ── Risk banner ── */
.risk-banner {{
    border-radius:10px; padding:10px 18px; margin-bottom:9px;
    display:flex; align-items:center; gap:20px;
}}

/* ── Section label ── */
.plbl {{
    font-size:0.60rem; font-weight:700; text-transform:uppercase;
    letter-spacing:0.15em; color:{P["teal"]}; margin:0 0 5px 0;
}}

/* ── Map container ── */
.map-wrap {{
    border-radius:12px; overflow:hidden;
    border:1px solid {P["border2"]};
}}

/* ── Right panel ── */
.right-panel {{
    background:{P["panel2"]};
    border:1px solid {P["border2"]};
    border-radius:12px;
    padding:13px 15px 10px;
    display:flex; flex-direction:column;
    height:100%;
}}

/* ── Nav tab strip ── */
.nav-strip {{
    display:flex; gap:6px; margin-top:6px;
    border-top:1px solid {P["border2"]}; padding-top:8px;
}}

/* Compact nav buttons */
div[data-testid="stHorizontalBlock"] .stButton button {{
    height:36px !important;
    font-size:0.75rem !important;
    font-weight:600 !important;
    border-radius:8px !important;
    padding:0 8px !important;
    transition:all 0.12s ease !important;
}}

/* ── Tip items ── */
.tip-item {{
    display:flex; gap:12px; align-items:flex-start;
    padding:9px 0; border-bottom:1px solid {P["border2"]};
}}
.tip-item:last-child {{ border-bottom:none; }}
.tip-num {{
    min-width:22px; height:22px; border-radius:6px;
    background:{P["teal"]}18; border:1px solid {P["teal"]}44;
    color:{P["teal"]}; font-size:0.60rem; font-weight:800;
    display:flex; align-items:center; justify-content:center;
    margin-top:1px; letter-spacing:0.04em;
}}
.tip-num.warn {{
    background:{P["amber"]}18; border-color:{P["amber"]}44; color:{P["amber"]};
}}
.tip-title {{
    font-size:0.78rem; font-weight:700; color:{P["text"]};
    margin-bottom:2px; line-height:1.3;
}}
.tip-body {{
    font-size:0.70rem; color:{P["muted"]}; line-height:1.55;
}}

/* ── Scrollable message container border ── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border:1px solid {P["border2"]} !important;
    border-radius:10px !important;
}}

/* ── Footer ── */
.footer {{
    font-size:0.58rem; color:{P["muted"]};
    border-top:1px solid {P["border2"]};
    padding-top:5px; margin-top:5px;
}}
.footer a {{ color:{P["teal"]}; text-decoration:none; }}
</style>
""", unsafe_allow_html=True)


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data
def _cases_weekly() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "cases_national_weekly.parquet")
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


@st.cache_data
def _cases_regional() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "cases_regional_annual.parquet")
    df["cases"] = pd.to_numeric(df["cases"], errors="coerce").fillna(0)
    return df


# ── Seasonal risk ─────────────────────────────────────────────────────────────

@st.cache_data
def _seasonal_risk(cases: pd.DataFrame, month: int) -> tuple[str, float]:
    monthly = (
        cases.assign(month=cases["week_start"].dt.month)
        .groupby("month")["cases"]
        .mean()
    )
    q33 = monthly.quantile(0.33)
    q67 = monthly.quantile(0.67)
    avg = float(monthly.get(month, monthly.mean()))
    if avg >= q67:
        return "HIGH", avg
    if avg >= q33:
        return "MEDIUM", avg
    return "LOW", avg


# ── Latest cached briefing ────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _latest_briefing() -> dict | None:
    if not BRIEFINGS_DIR.exists():
        return None
    try:
        dirs = sorted(
            [d for d in BRIEFINGS_DIR.iterdir() if (d / "briefing.json").exists()],
            reverse=True,
        )
        if dirs:
            with open(dirs[0] / "briefing.json", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _base_layout(**kw) -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=P["muted"], size=9.5),
        margin=dict(l=2, r=4, t=18, b=2),
        showlegend=False,
        **kw,
    )


# ── Map data ──────────────────────────────────────────────────────────────────

def _map_df(regional: pd.DataFrame) -> pd.DataFrame:
    totals = regional.groupby("region")["cases"].sum().reset_index()
    rows = []
    for _, r in totals.iterrows():
        coords = _REGION_COORDS.get(r["region"])
        short  = _REGION_SHORT.get(r["region"], r["region"])
        if coords:
            rows.append({
                "label": short,
                "full":  r["region"],
                "cases": r["cases"],
                "lat":   coords[0],
                "lon":   coords[1],
            })
    return pd.DataFrame(rows)


def _map_fig(mdf: pd.DataFrame) -> go.Figure:
    norm = (mdf["cases"] / mdf["cases"].max()).clip(0.06, 1.0)
    fig  = go.Figure()

    # Glow ring
    fig.add_trace(go.Scattermap(
        lat=mdf["lat"], lon=mdf["lon"], mode="markers",
        marker=dict(
            size=norm * 58 + 16,
            color=mdf["cases"],
            colorscale=[[0, "rgba(14,165,164,0.15)"],
                        [0.5, "rgba(245,158,11,0.15)"],
                        [1,   "rgba(239,68,68,0.15)"]],
            opacity=1.0, showscale=False,
        ),
        hoverinfo="skip", showlegend=False,
    ))

    # Core bubble + labels
    fig.add_trace(go.Scattermap(
        lat=mdf["lat"], lon=mdf["lon"],
        mode="markers+text",
        marker=dict(
            size=norm * 38 + 9,
            color=mdf["cases"],
            colorscale=[[0, P["teal"]], [0.5, P["amber"]], [1, P["red"]]],
            opacity=0.90, showscale=False,
        ),
        text=mdf["label"],
        textfont=dict(color="rgba(241,245,249,0.88)", size=8,
                      family="Inter,Segoe UI,sans-serif"),
        textposition="bottom center",
        customdata=mdf[["cases", "full"]].values,
        hovertemplate=(
            "<b>%{customdata[1]}</b><br>"
            "Total cases (1999–2020): <b>%{customdata[0]:,.0f}</b>"
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    fig.update_layout(
        map=dict(style="carto-darkmatter",
                 center={"lat": 12.2, "lon": 122.5}, zoom=4.2),
        height=358,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=P["panel"], bordercolor=P["border"],
                        font=dict(color=P["text"], size=12,
                                  family="Inter,sans-serif")),
    )
    return fig


# ── Right-panel content renderers ─────────────────────────────────────────────

def _right_default(cases: pd.DataFrame, briefing: dict | None,
                   regional: pd.DataFrame) -> None:
    """Seasonal chart + latest briefing snippet + data limitations note."""
    st.markdown('<div class="plbl">Typical Dengue Season · avg 2012–2023</div>',
                unsafe_allow_html=True)

    seasonal = (
        cases.groupby("epiweek")["cases"].mean().reset_index()
        .rename(columns={"cases": "avg"})
    )
    seasonal["dt"] = pd.to_datetime("2023-01-01") + pd.to_timedelta(
        (seasonal["epiweek"] - 1) * 7, unit="D"
    )

    fig_s = go.Figure()
    fig_s.add_vrect(x0="2023-06-01", x1="2023-11-30",
                    fillcolor="rgba(239,68,68,0.08)", line_width=0,
                    annotation_text="Peak (Jun–Nov)",
                    annotation_position="top left",
                    annotation_font_size=8, annotation_font_color=P["red"])
    fig_s.add_trace(go.Scatter(
        x=seasonal["dt"], y=seasonal["avg"],
        mode="lines",
        line=dict(color=P["teal"], width=2.0),
        fill="tozeroy", fillcolor="rgba(14,165,164,0.09)",
        hovertemplate="Wk %{customdata}: avg <b>%{y:,.0f}</b> cases<extra></extra>",
        customdata=seasonal["epiweek"],
    ))
    fig_s.update_layout(
        **_base_layout(height=148),
        xaxis=dict(tickformat="%b", dtick="M1",
                   gridcolor=P["border2"], linecolor=P["border2"]),
        yaxis=dict(gridcolor=P["border2"], linecolor=P["border2"],
                   title=dict(text="avg cases/wk", font=dict(size=8.5))),
    )
    st.plotly_chart(fig_s, use_container_width=True,
                    config={"displayModeBar": False})

    # ── Briefing snippet or bar chart fallback ────────────────────────────────
    st.markdown('<div class="plbl" style="margin-top:6px">Latest AI Briefing</div>',
                unsafe_allow_html=True)

    if briefing:
        rl_b    = briefing.get("risk", {}).get("risk_level", "MEDIUM")
        rc_b    = _RISK_COLOR.get(rl_b, P["amber"])
        rl_txt  = _RISK_LABEL.get(rl_b, "MODERATE")
        text    = briefing.get("briefing", "")
        snippet = (text[:240].rsplit(" ", 1)[0] + "…") if len(text) > 240 else text
        date_s  = briefing.get("generated_at", "")[:10]
        st.markdown(f"""
<div style="background:{P["panel"]};border:1px solid {rc_b}35;
            border-left:3px solid {rc_b};border-radius:8px;
            padding:9px 12px;font-size:0.73rem;color:{P["muted"]};
            line-height:1.68;margin-bottom:2px;">
  <span style="font-size:0.58rem;font-weight:700;text-transform:uppercase;
               letter-spacing:0.10em;color:{rc_b};">{rl_txt} · {date_s}</span><br>
  {snippet}
  <br><span style="font-size:0.62rem;color:{P["muted"]}55;">
    Open Report below for full analysis →
  </span>
</div>""", unsafe_allow_html=True)
    else:
        mdf_s = _map_df(regional).sort_values("cases").tail(6).copy()
        fig_b = go.Figure(go.Bar(
            x=mdf_s["cases"], y=mdf_s["label"], orientation="h",
            marker=dict(
                color=mdf_s["cases"],
                colorscale=[[0, P["panel"]], [0.5, P["teal"]], [1, P["red"]]],
                showscale=False,
            ),
            hovertemplate="%{y}: <b>%{x:,.0f}</b> cases<extra></extra>",
        ))
        fig_b.update_layout(
            **_base_layout(height=148),
            xaxis=dict(tickformat=",", gridcolor=P["border2"]),
            yaxis=dict(tickfont=dict(size=8.5)),
        )
        st.plotly_chart(fig_b, use_container_width=True,
                        config={"displayModeBar": False})

    # ── Data limitations notice ───────────────────────────────────────────────
    st.markdown(f"""
<div style="margin-top:8px;padding:9px 12px;
            background:{P["bg"]};border:1px solid {P["border2"]};
            border-radius:8px;font-size:0.64rem;color:{P["muted"]};
            line-height:1.75;">
  <span style="font-size:0.58rem;font-weight:700;text-transform:uppercase;
               letter-spacing:0.11em;color:{P["sub"]};">About this data</span><br>
  · Historical records only (2012–2023) — <b style="color:{P["sub"]}">no live or real-time data</b><br>
  · Risk levels reflect seasonal historical patterns, not current outbreaks<br>
  · National case totals only — no province or city-level breakdown available<br>
  · AI briefings are generated from historical data, not current surveillance<br>
  · Not a medical tool — consult a physician for any health concern
</div>""", unsafe_allow_html=True)


def _right_explore(cases: pd.DataFrame) -> None:
    """Historical weekly case explorer with year filter."""
    st.markdown('<div class="plbl">Weekly Cases — Historical View</div>',
                unsafe_allow_html=True)

    min_yr = int(cases["week_start"].dt.year.min())
    max_yr = int(cases["week_start"].dt.year.max())

    yr_range = st.slider(
        "Year range",
        min_value=min_yr, max_value=max_yr,
        value=(2018, max_yr),
        key="explore_years",
        label_visibility="collapsed",
    )
    filtered = cases[
        (cases["week_start"].dt.year >= yr_range[0]) &
        (cases["week_start"].dt.year <= yr_range[1])
    ]

    fig = go.Figure()
    fig.add_vrect(x0=f"{yr_range[0]}-06-01",
                  x1=f"{min(yr_range[1], max_yr-1)}-11-30",
                  fillcolor="rgba(239,68,68,0.07)", line_width=0)
    fig.add_trace(go.Scatter(
        x=filtered["week_start"], y=filtered["cases"],
        mode="lines",
        line=dict(color=P["teal"], width=1.6),
        fill="tozeroy", fillcolor="rgba(14,165,164,0.08)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:,.0f} cases<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=232),
        xaxis=dict(gridcolor=P["border2"], linecolor=P["border2"],
                   tickformat="%Y"),
        yaxis=dict(gridcolor=P["border2"], linecolor=P["border2"],
                   title=dict(text="cases/week", font=dict(size=8.5))),
    )
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})

    total = int(filtered["cases"].sum())
    peak_row = filtered.loc[filtered["cases"].idxmax()]
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total cases in range", f"{total:,}")
    with c2:
        st.metric("Peak week",
                  f"{int(peak_row['cases']):,}",
                  peak_row["week_start"].strftime("%b %Y"))


def _rag_answer(question: str) -> tuple[str, str]:
    """Call the RAG pipeline and return (answer, meta). Safe to call anywhere."""
    try:
        from src.rag.chat import ask
        res = ask(question)
        meta = (
            "Verified against source documents"
            if res["valid"] else
            "Could not be fully verified — treat with care"
        )
        return res["answer"], meta
    except Exception:
        return "Could not retrieve an answer. Please try again.", ""


def _right_chat() -> None:
    """Inline RAG chat — no dialog, fits in the right panel."""
    st.markdown('<div class="plbl">Ask About Dengue</div>', unsafe_allow_html=True)
    st.caption(
        "Answers sourced from WHO guidelines and Philippine health research. "
        "Not a substitute for medical advice."
    )

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Process any question queued by a suggestion button click
    pending = st.session_state.pop("chat_pending", None)
    if pending:
        with st.spinner("Searching guidelines…"):
            answer, meta = _rag_answer(pending)
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": answer, "meta": meta}
        )

    # Show suggestion pills only when conversation is empty and nothing is pending
    if not st.session_state.chat_messages:
        suggestions = [
            "Warning signs of severe dengue?",
            "How to prevent dengue at home?",
            "When should I go to a hospital?",
            "How long does dengue fever last?",
        ]
        cols = st.columns(2)
        for i, q in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(q, key=f"sug_{i}", use_container_width=True):
                    st.session_state.chat_messages.append(
                        {"role": "user", "content": q}
                    )
                    st.session_state.chat_pending = q
                    st.rerun()

    if st.session_state.chat_messages:
        with st.container(height=210):
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant" and msg.get("meta"):
                        st.caption(msg["meta"])

    question = st.chat_input("Ask anything about dengue…", key="chat_input_key")
    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})
        with st.spinner("Searching guidelines…"):
            answer, meta = _rag_answer(question)
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": answer, "meta": meta}
        )
        st.rerun()

    if st.session_state.chat_messages:
        if st.button("Clear", key="chat_clear", use_container_width=False):
            st.session_state.chat_messages = []
            st.rerun()


def _right_tips() -> None:
    """Prevention tips as a compact numbered list — no emoji."""
    st.markdown('<div class="plbl">Prevention Tips</div>', unsafe_allow_html=True)

    tips = [
        ("01", False, "Remove Standing Water",
         "Empty drums, flower pots, old tires, and gutters at least once a week. "
         "Mosquitoes breed only in still water."),
        ("02", False, "Use Mosquito Repellent",
         "Apply DEET-based repellent on exposed skin. Most critical during early "
         "morning and late afternoon when Aedes mosquitoes are most active."),
        ("03", False, "Wear Protective Clothing",
         "Long sleeves and pants during the rainy season (June–November). "
         "Light-colored fabric is cooler and less attractive to mosquitoes."),
        ("04", False, "Screen Your Home",
         "Install window and door screens. Use a mosquito net if your room is not "
         "fully screened. Air conditioning reduces mosquito activity indoors."),
        ("05", True,  "High Fever for 2+ Days — Seek Help",
         "Sudden high fever is a dengue warning sign. Go to the nearest health "
         "center promptly. Avoid aspirin and ibuprofen — they can worsen bleeding."),
    ]

    items_html = ""
    for num, warn, title, body in tips:
        num_cls = "tip-num warn" if warn else "tip-num"
        items_html += f"""
<div class="tip-item">
  <div class="{num_cls}">{num}</div>
  <div>
    <div class="tip-title">{title}</div>
    <div class="tip-body">{body}</div>
  </div>
</div>"""

    st.markdown(
        f'<div style="overflow-y:auto;max-height:278px;">{items_html}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="font-size:0.60rem;color:{P["muted"]}66;margin-top:6px;">'
        f'Sources: WHO Dengue Guidelines · DOH Philippines · CDC</p>',
        unsafe_allow_html=True,
    )


def _right_report(cases: pd.DataFrame) -> None:
    """AI situation report — inline, no dialog."""
    st.markdown('<div class="plbl">AI Situation Report</div>', unsafe_allow_html=True)

    latest_dt   = cases["week_start"].max().date()
    earliest_dt = cases["week_start"].min().date()

    c1, c2 = st.columns([3, 1])
    with c1:
        as_of = st.date_input(
            "Week",
            value=latest_dt,
            min_value=earliest_dt,
            max_value=latest_dt,
            key="report_date",
            label_visibility="collapsed",
        )
    with c2:
        generate = st.button("Generate", type="primary", key="report_gen",
                             use_container_width=True)

    saved = BRIEFINGS_DIR / str(as_of) / "briefing.json"

    if saved.exists() and not generate:
        with open(saved, encoding="utf-8") as f:
            data = json.load(f)
        st.caption(f"Cached — {data.get('generated_at','')[:10]}")
        _render_report(data, compact=True)
    elif generate:
        with st.spinner("Writing report — takes about 20 seconds…"):
            try:
                from src.agents.briefing import run
                result = run(str(as_of))
                _render_report(result, compact=True)
                try:
                    from src.agents.weekly_run import save_output
                    save_output(result)
                except Exception:
                    pass
            except Exception as e:
                st.error(f"Could not generate report: {e}")
    else:
        # Preview of latest cached briefing
        latest = _latest_briefing()
        if latest:
            rl_b  = latest.get("risk", {}).get("risk_level", "MEDIUM")
            rc_b  = _RISK_COLOR.get(rl_b, P["amber"])
            rl_txt = _RISK_LABEL.get(rl_b, "MODERATE")
            text   = latest.get("briefing", "")
            snip   = (text[:220].rsplit(" ", 1)[0] + "…") if len(text) > 220 else text
            date_s = latest.get("generated_at", "")[:10]
            st.markdown(
                f'<p style="font-size:0.60rem;color:{P["muted"]};margin:8px 0 4px">'
                f'Latest cached report</p>',
                unsafe_allow_html=True,
            )
            st.markdown(f"""
<div style="background:{P["panel"]};border:1px solid {rc_b}30;
            border-left:3px solid {rc_b};border-radius:8px;
            padding:10px 13px;font-size:0.73rem;color:{P["muted"]};
            line-height:1.68;">
  <span style="font-size:0.58rem;font-weight:700;text-transform:uppercase;
               letter-spacing:0.10em;color:{rc_b};">{rl_txt} · {date_s}</span><br>
  {snip}
</div>""", unsafe_allow_html=True)
        else:
            st.markdown(
                f'<p style="font-size:0.76rem;color:{P["muted"]};padding:10px 0">'
                f'Select a week and click <b style="color:{P["text"]}">Generate</b> '
                f'to produce an AI intelligence briefing for that period.</p>',
                unsafe_allow_html=True,
            )


def _render_report(result: dict, compact: bool = False) -> None:
    risk  = result.get("risk", {})
    ctx   = result.get("context", {})
    valid = result.get("valid", False)

    rl    = risk.get("risk_level", "MEDIUM")
    color = _RISK_COLOR.get(rl, P["amber"])
    label = _RISK_LABEL.get(rl, "MODERATE")
    pred  = risk.get("predicted_cases")

    c1, c2 = st.columns(2)
    with c1:
        pred_line = (
            f'<div style="font-size:0.68rem;color:{P["muted"]};margin-top:4px">'
            f'Next week est.: <b style="color:{P["text"]}">{pred:,}</b></div>'
        ) if pred else ""
        st.markdown(f"""
<div style="background:{color}0E;border:1px solid {color}40;
            border-left:4px solid {color};border-radius:0 8px 8px 0;
            padding:10px 14px;">
  <div style="font-size:0.55rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.12em;color:{color};margin-bottom:2px">Risk</div>
  <div style="font-size:1.15rem;font-weight:800;color:{P["text"]};line-height:1">
    {label}
  </div>
  {pred_line}
</div>""", unsafe_allow_html=True)
    with c2:
        lc = ctx.get("latest_cases", {})
        if lc:
            st.metric(
                "Cases that week",
                f"{int(lc.get('cases', 0)):,}",
                f"{lc.get('wow_change_pct', 0):+.1f}% vs prev. week",
                delta_color="inverse",
            )

    st.divider()
    text = result.get("briefing", "")
    if compact and len(text) > 600:
        with st.container(height=160):
            st.markdown(text)
    elif text:
        st.markdown(text)

    verified = "Verified" if valid else "Partially verified"
    st.caption(f"Quality check: {verified} — {result.get('attempts','?')} pass(es)")


# ── Nav strip ─────────────────────────────────────────────────────────────────

def _nav_strip(active: str | None) -> None:
    """4-button navigation rendered inside the right panel."""
    cols = st.columns(len(_NAV), gap="small")
    for col, (pid, icon, label) in zip(cols, _NAV):
        with col:
            is_active = active == pid
            clicked = st.button(
                label, icon=icon, key=f"nav_{pid}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            )
            if clicked:
                st.session_state.active_panel = None if is_active else pid
                st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _css()

    cases    = _cases_weekly()
    regional = _cases_regional()
    briefing = _latest_briefing()

    now        = pd.Timestamp.now()
    risk_level, month_avg = _seasonal_risk(cases, now.month)
    month_name = now.strftime("%B")
    rc         = _RISK_COLOR[risk_level]
    rl_text    = _RISK_LABEL[risk_level]

    if "active_panel" not in st.session_state:
        st.session_state.active_panel = None

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
<div class="app-header">
  <div class="brand">Sentinel<em>PH</em></div>
  <div class="tagline">Dengue Risk Monitor<br>Philippines</div>
  <div class="data-badge">Based on 2012–2023 surveillance data</div>
</div>
""", unsafe_allow_html=True)

    # ── Risk Banner ───────────────────────────────────────────────────────────
    st.markdown(f"""
<div class="risk-banner"
     style="background:{rc}0D;border:1px solid {rc}35;border-left:5px solid {rc};">
  <div style="min-width:140px;">
    <div style="font-size:0.57rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.13em;color:{rc};margin-bottom:2px;">
      Typical Risk — {month_name}
    </div>
    <div style="font-size:1.45rem;font-weight:900;color:{P["text"]};
                letter-spacing:-0.01em;line-height:1.1;">
      {rl_text}
    </div>
  </div>
  <div style="color:{P["muted"]};font-size:0.73rem;line-height:1.75;flex:1;
              border-left:1px solid {P["border"]};padding-left:18px;">
    {month_name} historically averages
    <b style="color:{P["text"]}">{month_avg:,.0f} cases per week</b>
    nationwide (2012–2023).
    <span style="font-size:0.65rem;display:block;margin-top:3px;color:{P["muted"]}99;">
      Based on historical seasonal patterns —
      <b style="color:{P["amber"]}">this is not live surveillance data.</b>
      Open the <b style="color:{P["text"]}">Report</b> panel for an AI-generated briefing
      from the historical record.
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Two-column layout ─────────────────────────────────────────────────────
    col_map, col_right = st.columns([56, 44], gap="medium")

    # ── Left: Map (always visible) ────────────────────────────────────────────
    with col_map:
        st.markdown('<div class="plbl">Regional Dengue Burden · 1999–2020</div>',
                    unsafe_allow_html=True)
        mdf = _map_df(regional)
        if not mdf.empty:
            st.plotly_chart(_map_fig(mdf), use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Map data unavailable.")

    # ── Right: Feature area ───────────────────────────────────────────────────
    with col_right:
        panel = st.session_state.active_panel

        # Content block (switches based on active panel)
        if panel is None:
            _right_default(cases, briefing, regional)
        elif panel == "explore":
            _right_explore(cases)
        elif panel == "chat":
            _right_chat()
        elif panel == "tips":
            _right_tips()
        elif panel == "report":
            _right_report(cases)

        # Nav strip — always at the bottom of the right column
        st.markdown(
            f'<div style="border-top:1px solid {P["border2"]};margin-top:8px;'
            f'padding-top:7px;"></div>',
            unsafe_allow_html=True,
        )
        _nav_strip(panel)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="footer">'
        f'Data: OpenDengue V1.3 &nbsp;·&nbsp; Open-Meteo ERA5 &nbsp;·&nbsp; '
        f'Google Trends &nbsp;·&nbsp; GDELT &nbsp;·&nbsp; '
        f'Not a medical tool — consult a physician for any health concern. &nbsp;·&nbsp; '
        f'<a href="https://github.com/aces-14/sentinel-ph">GitHub</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
