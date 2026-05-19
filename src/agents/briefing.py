"""
Phase 3 Step 5 — Multi-Agent Briefing Workflow

LangGraph 4-node graph that produces a weekly dengue situation
briefing for the Philippines from the SQLite database.

Graph topology:
  build_context → score_risk → generate_briefing → evaluate_briefing
                                      ↑                      |
                                      └────── retry ──────────┘
                                              (max MAX_RETRIES=3)

Tools used:
  - sqlite3 / pandas  : DB queries
  - langchain-groq    : ChatGroq (llama-3.3-70b-versatile)
  - langgraph         : StateGraph
  - src.model.risk_scorer : RiskScorer
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.model.risk_scorer import RiskScorer

load_dotenv()
logger = logging.getLogger(__name__)

DB_PATH    = Path("data/sentinel.db")
MAX_RETRIES = 3
MODEL_NAME  = "llama-3.3-70b-versatile"
RAINY_MONTHS = {6, 7, 8, 9, 10, 11}

# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    as_of_date: str
    context: dict
    risk: dict
    briefing: str
    attempts: int
    valid: bool
    feedback: str


# ── Prompts ───────────────────────────────────────────────────────────────────

BRIEFING_SYSTEM = """\
You are SentinelPH, a dengue surveillance intelligence system for the Philippines.
Write a weekly dengue situation briefing based ONLY on the data provided in the context.

Requirements:
1. Cite specific numbers from the context (case counts, % changes, weather values, trends index).
2. State the model-predicted risk level for next week and its top drivers.
3. Use appropriately hedged language: "surveillance data indicates", "the model estimates", "conditions suggest".
4. Write exactly 3 concise paragraphs suitable for a public health dashboard.
5. Do NOT include medical advice, treatment recommendations, or diagnostic guidance.
6. Do NOT present model estimates as certainties — they are estimates, not guarantees.
"""

BRIEFING_PROMPT = """\
Context data (JSON):
{context_json}

Risk model output (JSON):
{risk_json}

Write the weekly dengue situation briefing now.
"""

REFINEMENT_PROMPT = """\
Your previous briefing had the following issue:
{feedback}

Context data (JSON):
{context_json}

Risk model output (JSON):
{risk_json}

Rewrite the briefing addressing the issue above.
"""

EVALUATOR_PROMPT = """\
You are a quality auditor for a public health surveillance dashboard.

Audit the briefing below against these three criteria:
1. DATA_GROUNDING  — every number or statistic must come from the context provided
2. UNCERTAINTY     — estimates must use hedged language, not definitive statements
3. NO_MEDICAL      — must not contain treatment, diagnosis, or medical recommendations

Context (JSON):
{context_json}

Briefing:
{briefing}

Respond with exactly one line — either:
  PASS
  FAIL_DATA_GROUNDING: <first unsupported claim>
  FAIL_UNCERTAINTY: <first overconfident statement>
  FAIL_NO_MEDICAL: <medical advice found>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set in environment / .env")
    return ChatGroq(model=MODEL_NAME, temperature=0, api_key=api_key)


_scorer: RiskScorer | None = None

def _get_scorer() -> RiskScorer:
    global _scorer
    if _scorer is None:
        _scorer = RiskScorer.load()
    return _scorer


def _build_context(as_of_date: str) -> dict:
    """Query SQLite and build a structured context object for the briefing LLM."""
    conn = sqlite3.connect(DB_PATH)

    # ── Cases ──────────────────────────────────────────────────────────────
    df_cases = pd.read_sql_query(
        "SELECT week_start, year, epiweek, cases FROM cases_national_weekly ORDER BY week_start",
        conn,
        parse_dates=["week_start"],
    )
    df_cases = df_cases[df_cases["week_start"] <= pd.Timestamp(as_of_date)]

    if len(df_cases) < 2:
        raise ValueError(f"Not enough case data available on or before {as_of_date}")

    recent = df_cases.tail(8).reset_index(drop=True)
    latest = recent.iloc[-1]
    prev   = recent.iloc[-2]

    wow = round(((latest["cases"] - prev["cases"]) / prev["cases"] * 100), 1) if prev["cases"] > 0 else 0.0

    same_epiweek_ly = df_cases[
        (df_cases["epiweek"] == latest["epiweek"]) &
        (df_cases["year"]    == latest["year"] - 1)
    ]
    yoy = (
        round(((latest["cases"] - same_epiweek_ly.iloc[0]["cases"]) / same_epiweek_ly.iloc[0]["cases"] * 100), 1)
        if len(same_epiweek_ly) > 0 else None
    )

    last4 = [int(c) for c in recent.tail(4)["cases"].tolist()]
    if last4[-1] > last4[0] * 1.05:
        trend_dir = "rising"
    elif last4[-1] < last4[0] * 0.95:
        trend_dir = "falling"
    else:
        trend_dir = "stable"

    # ── Weather ────────────────────────────────────────────────────────────
    week_start_dt = latest["week_start"]
    week_end_dt   = week_start_dt + pd.Timedelta(days=6)
    df_wx = pd.read_sql_query(
        "SELECT t_max, t_min, precip, rh_mean FROM weather_daily WHERE date >= ? AND date <= ?",
        conn,
        params=[str(week_start_dt.date()) + " 00:00:00", str(week_end_dt.date()) + " 23:59:59"],
    )
    weather = (
        {
            "avg_t_max_c":      round(float(df_wx["t_max"].mean()), 1),
            "avg_t_min_c":      round(float(df_wx["t_min"].mean()), 1),
            "total_precip_mm":  round(float(df_wx["precip"].sum()), 1),
            "avg_humidity_pct": round(float(df_wx["rh_mean"].mean()), 1),
        }
        if len(df_wx) > 0 else None
    )

    # ── Google Trends ──────────────────────────────────────────────────────
    df_trends = pd.read_sql_query(
        "SELECT date, interest FROM trends_weekly WHERE keyword = 'dengue' ORDER BY date",
        conn,
        parse_dates=["date"],
    )
    df_trends = df_trends[df_trends["date"] <= pd.Timestamp(as_of_date)]
    trends_val = int(df_trends.iloc[-1]["interest"]) if len(df_trends) > 0 else None

    # ── News count (last 4 weeks) ──────────────────────────────────────────
    four_weeks_ago = pd.Timestamp(as_of_date) - pd.Timedelta(weeks=4)
    df_news = pd.read_sql_query(
        "SELECT COUNT(*) AS cnt FROM news WHERE seen_date >= ? AND seen_date <= ?",
        conn,
        params=[
            str(four_weeks_ago.date()) + " 00:00:00",
            str(pd.Timestamp(as_of_date).date()) + " 23:59:59",
        ],
    )
    news_count = int(df_news.iloc[0]["cnt"])

    conn.close()

    month_num = pd.Timestamp(as_of_date).month
    return {
        "as_of_date": as_of_date,
        "latest_cases": {
            "week_start":     str(latest["week_start"].date()),
            "epiweek":        int(latest["epiweek"]),
            "cases":          int(latest["cases"]),
            "wow_change_pct": wow,
            "yoy_change_pct": yoy,
        },
        "four_week_trend": {
            "weekly_cases": last4,
            "direction":    trend_dir,
        },
        "weather_latest_week": weather,
        "google_trends_dengue_index": trends_val,
        "news_articles_last_4_weeks": news_count,
        "is_rainy_season": month_num in RAINY_MONTHS,
        "month_name": pd.Timestamp(as_of_date).strftime("%B"),
        "year": int(pd.Timestamp(as_of_date).year),
    }


# ── Nodes ─────────────────────────────────────────────────────────────────────

def node_build_context(state: AgentState) -> dict:
    context = _build_context(state["as_of_date"])
    logger.debug("Context built for %s: %d cases", state["as_of_date"], context["latest_cases"]["cases"])
    return {
        "context": context,
        "attempts": 0,
        "valid": False,
        "feedback": "",
        "briefing": "",
        "risk": {},
    }


def node_score_risk(state: AgentState) -> dict:
    scorer = _get_scorer()
    risk = scorer.predict(state["as_of_date"])
    logger.debug("Risk score: %s (%d cases est.)", risk["risk_level"], risk["predicted_cases"])
    return {"risk": risk}


def node_generate_briefing(state: AgentState) -> dict:
    llm = _get_llm()
    context_json = json.dumps(state["context"], indent=2)
    risk_json    = json.dumps(state["risk"],    indent=2)

    if state["attempts"] == 0:
        user_content = BRIEFING_PROMPT.format(
            context_json=context_json, risk_json=risk_json
        )
    else:
        user_content = REFINEMENT_PROMPT.format(
            feedback=state["feedback"],
            context_json=context_json,
            risk_json=risk_json,
        )

    messages  = [SystemMessage(content=BRIEFING_SYSTEM), HumanMessage(content=user_content)]
    response  = llm.invoke(messages)
    attempts  = state["attempts"] + 1
    logger.debug("Briefing generated (attempt %d)", attempts)
    return {"briefing": response.content.strip(), "attempts": attempts}


def node_evaluate_briefing(state: AgentState) -> dict:
    llm = _get_llm()
    context_json = json.dumps(state["context"], indent=2)

    messages = [
        HumanMessage(
            content=EVALUATOR_PROMPT.format(
                context_json=context_json,
                briefing=state["briefing"],
            )
        )
    ]
    response = llm.invoke(messages)
    verdict  = response.content.strip()
    logger.debug("Evaluator verdict: %s", verdict)

    if verdict.upper().startswith("PASS"):
        return {"valid": True, "feedback": ""}

    feedback = verdict.split(":", 1)[1].strip() if ":" in verdict else verdict
    return {"valid": False, "feedback": feedback}


# ── Routing ───────────────────────────────────────────────────────────────────

def _should_retry(state: AgentState) -> str:
    if state["valid"] or state["attempts"] >= MAX_RETRIES:
        return "end"
    return "generate"


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("build_context",      node_build_context)
    graph.add_node("score_risk",         node_score_risk)
    graph.add_node("generate_briefing",  node_generate_briefing)
    graph.add_node("evaluate_briefing",  node_evaluate_briefing)

    graph.set_entry_point("build_context")
    graph.add_edge("build_context",     "score_risk")
    graph.add_edge("score_risk",        "generate_briefing")
    graph.add_edge("generate_briefing", "evaluate_briefing")
    graph.add_conditional_edges(
        "evaluate_briefing",
        _should_retry,
        {"end": END, "generate": "generate_briefing"},
    )

    return graph.compile()


# ── Public API ────────────────────────────────────────────────────────────────

_graph = None


def run(as_of_date: str) -> dict:
    """
    Run the full briefing workflow for a given date.

    Parameters
    ----------
    as_of_date : str   e.g. "2023-10-01" — last date with available data

    Returns
    -------
    dict with keys: as_of_date, context, risk, briefing, attempts, valid
    """
    global _graph
    if _graph is None:
        _graph = build_graph()

    initial: AgentState = {
        "as_of_date": as_of_date,
        "context":    {},
        "risk":       {},
        "briefing":   "",
        "attempts":   0,
        "valid":      False,
        "feedback":   "",
    }
    final = _graph.invoke(initial)
    return {
        "as_of_date": final["as_of_date"],
        "context":    final["context"],
        "risk":       final["risk"],
        "briefing":   final["briefing"],
        "attempts":   final["attempts"],
        "valid":      final["valid"],
    }
