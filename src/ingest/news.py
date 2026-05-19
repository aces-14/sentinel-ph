"""
Pull dengue-related news articles for the Philippines from GDELT Doc 2.0 API.

Endpoint: https://api.gdeltproject.org/api/v2/doc/doc
No API key required. Max 250 articles per request.
We query by quarter to maximise coverage across 2012-2023.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
PROCESSED_DIR = Path("data/processed")

QUERY = "dengue philippines"


def _quarter_ranges(start_year: int, end_year: int) -> list[tuple[str, str]]:
    """Generate (start, end) datetime strings for each quarter YYYYMMDDHHMMSS."""
    ranges = []
    for year in range(start_year, end_year + 1):
        quarters = [
            (date(year, 1, 1),  date(year, 3, 31)),
            (date(year, 4, 1),  date(year, 6, 30)),
            (date(year, 7, 1),  date(year, 9, 30)),
            (date(year, 10, 1), date(year, 12, 31)),
        ]
        for start, end in quarters:
            ranges.append((
                start.strftime("%Y%m%d") + "000000",
                end.strftime("%Y%m%d")   + "235959",
            ))
    return ranges


def _fetch_articles(start_dt: str, end_dt: str) -> list[dict]:
    params = {
        "query": QUERY,
        "mode": "artlist",
        "maxrecords": 250,
        "format": "json",
        "sort": "DateDesc",
        "startdatetime": start_dt,
        "enddatetime": end_dt,
    }
    response = requests.get(GDELT_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("articles", [])


def load_news(
    processed_dir: Path = PROCESSED_DIR,
    start_year: int = 2012,
    end_year: int = 2023,
    sleep_between: float = 2.0,
) -> pd.DataFrame:
    """
    Fetch dengue-related PH news articles from GDELT, one request per quarter.
    Saves to data/processed/news.parquet. Returns the combined DataFrame.
    """
    processed_dir.mkdir(parents=True, exist_ok=True)
    quarters = _quarter_ranges(start_year, end_year)
    all_articles: list[dict] = []

    for i, (start_dt, end_dt) in enumerate(quarters, 1):
        logger.info("[%d/%d] Fetching %s – %s …", i, len(quarters), start_dt[:8], end_dt[:8])
        try:
            articles = _fetch_articles(start_dt, end_dt)
            logger.info("  → %d articles", len(articles))
            all_articles.extend(articles)
        except Exception as exc:
            logger.warning("  ✗ Failed for %s–%s: %s", start_dt[:8], end_dt[:8], exc)
        time.sleep(sleep_between)

    if not all_articles:
        raise RuntimeError("No articles retrieved from GDELT.")

    df = pd.DataFrame(all_articles)

    # Normalise the columns GDELT returns
    rename = {
        "url": "url",
        "title": "title",
        "seendate": "seen_date",
        "socialimage": "image_url",
        "domain": "domain",
        "language": "language",
        "sourcecountry": "source_country",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "seen_date" in df.columns:
        df["seen_date"] = pd.to_datetime(df["seen_date"], format="%Y%m%dT%H%M%SZ", errors="coerce")

    # Drop duplicates by URL
    before = len(df)
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    logger.info("Dropped %d duplicate URLs. Final: %d articles.", before - len(df), len(df))

    out = processed_dir / "news.parquet"
    df.to_parquet(out, index=False)
    logger.info("Saved %d rows → %s", len(df), out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_news()
    print(df.dtypes)
    print(df.head(5).to_string())
    print(f"\nTotal articles: {len(df)}")
    if "seen_date" in df.columns:
        print(f"Date range: {df['seen_date'].min()} – {df['seen_date'].max()}")
