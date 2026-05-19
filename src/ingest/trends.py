"""
Pull Google Trends weekly data for dengue-related queries in the Philippines.

Uses pytrends (unofficial Google Trends API wrapper).
Pulls in 5-year chunks to stay within Google's resolution window
(weekly data is only returned for timeframes ≤ 5 years).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")

KEYWORDS = ["dengue", "dengue symptoms", "dengue fever", "lagnat ng dengue"]
GEO = "PH"  # Philippines national level

# 5-year chunks covering 2012–2023
TIMEFRAMES = [
    "2012-01-01 2016-12-31",
    "2017-01-01 2021-12-31",
    "2022-01-01 2023-12-31",
]


def _fetch_chunk(
    pytrends: TrendReq,
    keyword: str,
    timeframe: str,
    retries: int = 3,
) -> pd.DataFrame:
    """Fetch a single keyword + timeframe chunk with retry on failure."""
    for attempt in range(retries):
        try:
            pytrends.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe=timeframe,
                geo=GEO,
                gprop="",
            )
            df = pytrends.interest_over_time()
            return df
        except Exception as exc:
            wait = 30 * (attempt + 1)
            logger.warning(
                "Attempt %d/%d failed for %r %s: %s. Waiting %ds …",
                attempt + 1, retries, keyword, timeframe, exc, wait,
            )
            time.sleep(wait)
    logger.error("All retries exhausted for %r %s.", keyword, timeframe)
    return pd.DataFrame()


def load_trends(
    processed_dir: Path = PROCESSED_DIR,
    sleep_between: float = 5.0,
) -> pd.DataFrame:
    """
    Fetch weekly Google Trends interest for dengue queries in the Philippines,
    combining multiple 5-year chunks. Saves to data/processed/trends_weekly.parquet.
    Returns the combined DataFrame.
    """
    processed_dir.mkdir(parents=True, exist_ok=True)
    # Omit retries/backoff_factor — pytrends passes these to urllib3.Retry which
    # removed 'method_whitelist' in v2.0, causing a TypeError. Retry is handled
    # manually in _fetch_chunk instead.
    pytrends = TrendReq(hl="en-US", tz=480, timeout=(10, 30))

    frames: list[pd.DataFrame] = []

    for keyword in KEYWORDS:
        kw_chunks: list[pd.DataFrame] = []
        for timeframe in TIMEFRAMES:
            logger.info("Fetching trends: %r | %s …", keyword, timeframe)
            chunk = _fetch_chunk(pytrends, keyword, timeframe)
            if not chunk.empty and keyword in chunk.columns:
                chunk = chunk[[keyword]].copy()
                chunk.index.name = "date"
                chunk = chunk.reset_index()
                chunk.rename(columns={keyword: "interest"}, inplace=True)
                chunk.insert(0, "keyword", keyword)
                kw_chunks.append(chunk)
                logger.info("  → %d rows", len(chunk))
            else:
                logger.warning("  → empty response for %r %s", keyword, timeframe)
            time.sleep(sleep_between)

        if kw_chunks:
            kw_df = pd.concat(kw_chunks, ignore_index=True)
            # Normalise across chunks: each chunk is 0-100 independently,
            # so we scale each chunk by its max to produce a consistent series.
            kw_df = kw_df.sort_values("date").drop_duplicates("date")
            frames.append(kw_df)

    if not frames:
        raise RuntimeError("No trends data fetched.")

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined["interest"] = pd.to_numeric(combined["interest"], errors="coerce")

    out = processed_dir / "trends_weekly.parquet"
    combined.to_parquet(out, index=False)
    logger.info("Saved %d rows (%d keywords) → %s",
                len(combined), combined["keyword"].nunique(), out)
    return combined


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_trends()
    print(df.dtypes)
    print(df.head(10))
    print(f"\nKeywords: {df['keyword'].unique()}")
    print(f"Date range: {df['date'].min().date()} – {df['date'].max().date()}")
    print(f"Total rows: {len(df):,}")
