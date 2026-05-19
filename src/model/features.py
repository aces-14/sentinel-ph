"""
Phase 3 Step 1 — Feature Engineering

Builds the weekly feature matrix for the dengue risk model.

One row per week (indexed by week_start). Target column is
'target_log_cases' = log1p(cases of the NEXT week).

All feature columns use only information available at or before week_start
(no future leakage).

Feature groups:
  - Case lags (log-scaled): lag 1, 2, 4, 8 weeks + 4-week rolling mean
  - Weather (national weekly avg): t_max, t_min, precip_sum, rh_mean
    at current week and 1-week lag
  - Google Trends: interest for "dengue", "dengue symptoms", "dengue fever"
    at current week and 1-week lag
  - News: weekly article count at current week and 1-week lag
  - Calendar: epiweek, month, is_rainy_season (June–November)
  - Year: for long-term trend
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CASES_PATH   = Path("data/processed/cases_national_weekly.parquet")
WEATHER_PATH = Path("data/processed/weather_daily.parquet")
TRENDS_PATH  = Path("data/processed/trends_weekly.parquet")
NEWS_PATH    = Path("data/processed/news.parquet")

RAINY_MONTHS = {6, 7, 8, 9, 10, 11}  # June–November (Philippine wet season)

TREND_KEYWORDS = ["dengue", "dengue symptoms", "dengue fever"]


# ── Loaders / aggregators ────────────────────────────────────────────────────

def _load_cases() -> pd.DataFrame:
    df = pd.read_parquet(CASES_PATH)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_end"]   = pd.to_datetime(df["week_end"])
    return df.sort_values("week_start").reset_index(drop=True)


def _load_weather_weekly(cases: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily regional weather to national weekly averages/sums."""
    weather = pd.read_parquet(WEATHER_PATH)
    weather["date"] = pd.to_datetime(weather["date"])

    # National daily mean across all regions
    daily = (
        weather.groupby("date")[["t_max", "t_min", "precip", "rh_mean"]]
        .mean()
        .reset_index()
        .sort_values("date")
    )

    # Assign each day to its case week using backward merge
    cases_weeks = cases[["week_start", "week_end"]].sort_values("week_start")
    merged = pd.merge_asof(
        daily,
        cases_weeks,
        left_on="date",
        right_on="week_start",
        direction="backward",
    )
    # Drop days that fall after their assigned week's end
    merged = merged[merged["date"] <= merged["week_end"]]

    weekly = (
        merged.groupby("week_start")
        .agg(
            weather_t_max=("t_max", "mean"),
            weather_t_min=("t_min", "mean"),
            weather_precip=("precip", "sum"),   # total rainfall for the week
            weather_rh=("rh_mean", "mean"),
        )
        .reset_index()
    )
    logger.debug("Weather weekly: %d rows", len(weekly))
    return weekly


def _load_trends_weekly(cases: pd.DataFrame) -> pd.DataFrame:
    """Pivot trends by keyword and align to case weeks."""
    trends = pd.read_parquet(TRENDS_PATH)
    trends["date"] = pd.to_datetime(trends["date"])

    # Keep only the three most complete keywords
    trends = trends[trends["keyword"].isin(TREND_KEYWORDS)]

    pivoted = (
        trends.pivot_table(index="date", columns="keyword", values="interest", aggfunc="mean")
        .reset_index()
        .rename(columns={
            "date": "trend_date",
            "dengue": "trend_dengue",
            "dengue symptoms": "trend_symptoms",
            "dengue fever": "trend_fever",
        })
        .rename_axis(None, axis=1)
    )
    pivoted["trend_date"] = pd.to_datetime(pivoted["trend_date"]).astype("datetime64[us]")

    # Align trend weeks to case week_start via backward merge
    cases_dates = cases[["week_start"]].sort_values("week_start")
    merged = pd.merge_asof(
        cases_dates,
        pivoted.sort_values("trend_date"),
        left_on="week_start",
        right_on="trend_date",
        direction="nearest",
        tolerance=pd.Timedelta("7 days"),
    )
    merged = merged.drop(columns=["trend_date"], errors="ignore")
    # Fill keywords that have no data in early years with 0 (no search interest)
    for col in ["trend_dengue", "trend_symptoms", "trend_fever"]:
        if col not in merged.columns:
            merged[col] = np.nan
        merged[col] = merged[col].fillna(0)

    logger.debug("Trends weekly: %d rows", len(merged))
    return merged


def _load_news_weekly(cases: pd.DataFrame) -> pd.DataFrame:
    """Count news articles per case week."""
    news = pd.read_parquet(NEWS_PATH)
    news["seen_date"] = pd.to_datetime(news["seen_date"])

    cases_weeks = cases[["week_start", "week_end"]].sort_values("week_start")

    # Assign each article to a case week
    news_sorted = news[["seen_date"]].sort_values("seen_date")
    merged = pd.merge_asof(
        news_sorted,
        cases_weeks,
        left_on="seen_date",
        right_on="week_start",
        direction="backward",
    )
    merged = merged[merged["seen_date"] <= merged["week_end"]]

    counts = (
        merged.groupby("week_start")
        .size()
        .reset_index(name="news_count")
    )
    # Fill weeks with no articles
    full = cases[["week_start"]].merge(counts, on="week_start", how="left")
    full["news_count"] = full["news_count"].fillna(0).astype(int)
    logger.debug("News weekly: %d rows", len(full))
    return full


# ── Lag / rolling helpers ────────────────────────────────────────────────────

def _add_lags(df: pd.DataFrame, col: str, lags: list[int], prefix: str) -> pd.DataFrame:
    for lag in lags:
        df[f"{prefix}_lag{lag}"] = df[col].shift(lag)
    return df


def _add_rolling(df: pd.DataFrame, col: str, window: int, prefix: str) -> pd.DataFrame:
    # Rolling mean of the lag-1 through lag-window values (no current-week leakage)
    df[f"{prefix}_roll{window}"] = df[col].shift(1).rolling(window).mean()
    return df


# ── Main builder ─────────────────────────────────────────────────────────────

def build_features(
    cases_path: Path = CASES_PATH,
    weather_path: Path = WEATHER_PATH,
    trends_path: Path = TRENDS_PATH,
    news_path: Path = NEWS_PATH,
) -> pd.DataFrame:
    """
    Build the full feature matrix for the dengue risk model.

    Returns
    -------
    pd.DataFrame
        One row per week. Columns include all features and the target.
        Rows with NaN in any column (from lag initialisation) are dropped.
        Index is a RangeIndex; 'week_start' is a regular column.

    Target
    ------
    'target_log_cases' = log1p(cases of the FOLLOWING week)
    """
    logger.info("Loading raw data…")
    cases   = _load_cases()
    weather = _load_weather_weekly(cases)
    trends  = _load_trends_weekly(cases)
    news    = _load_news_weekly(cases)

    # ── Merge all sources ────────────────────────────────────────────────────
    df = cases[["week_start", "year", "epiweek", "cases"]].copy()
    df = df.merge(weather, on="week_start", how="left")
    df = df.merge(trends,  on="week_start", how="left")
    df = df.merge(news,    on="week_start", how="left")

    # ── Target (next week's cases, log-scaled) ───────────────────────────────
    df["log_cases"] = np.log1p(df["cases"])
    df["target_log_cases"] = df["log_cases"].shift(-1)

    # ── Case lag features ────────────────────────────────────────────────────
    df = _add_lags(df, "log_cases", [1, 2, 4, 8], "cases")
    df = _add_rolling(df, "log_cases", 4, "cases")

    # ── Weather lag features ─────────────────────────────────────────────────
    for w_col in ["weather_t_max", "weather_t_min", "weather_precip", "weather_rh"]:
        df = _add_lags(df, w_col, [1, 2], w_col)
    # Drop raw (same-week) weather — dengue reacts to past conditions, not current
    df = df.drop(columns=["weather_t_max", "weather_t_min", "weather_precip", "weather_rh"])

    # ── Trends lag features ──────────────────────────────────────────────────
    for t_col in ["trend_dengue", "trend_symptoms", "trend_fever"]:
        df = _add_lags(df, t_col, [1], t_col)
    # Keep current-week trends (search interest precedes diagnosis by ~1 week)

    # ── News lag feature ─────────────────────────────────────────────────────
    df = _add_lags(df, "news_count", [1], "news_count")

    # ── Calendar features ────────────────────────────────────────────────────
    df["month"] = df["week_start"].dt.month
    df["is_rainy_season"] = df["month"].isin(RAINY_MONTHS).astype(int)

    # ── Drop helper columns not used as features ─────────────────────────────
    df = df.drop(columns=["cases", "log_cases"])

    # ── Drop rows with NaN (lag initialisation at start, target at end) ──────
    n_before = len(df)
    df = df.dropna().reset_index(drop=True)
    logger.info(
        "Feature matrix: %d rows (dropped %d for NaN from lags/target)",
        len(df), n_before - len(df),
    )
    return df


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the ordered list of input feature columns (excludes week_start and target)."""
    return [c for c in df.columns if c not in {"week_start", "target_log_cases"}]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = build_features()
    print(f"Shape: {df.shape}")
    print(f"\nFeature columns ({len(get_feature_columns(df))}):")
    for col in get_feature_columns(df):
        print(f"  {col}")
    print(f"\nDate range: {df['week_start'].min().date()} to {df['week_start'].max().date()}")
    print(f"\nTarget stats:\n{df['target_log_cases'].describe()}")
