"""
Build the unified SQLite database from all processed parquet files.

Database: data/sentinel.db
Tables:
  cases_national_weekly    — national weekly cases 2012–2023
  cases_regional_annual    — regional annual cases 1999–2020
  cases_provincial_monthly — provincial monthly cases 1993–2010
  weather_daily            — daily weather per region 2012–2023
  news                     — dengue news articles from GDELT
  trends_weekly            — Google Trends weekly interest
  region_centroids         — region name + lat/lon from GADM
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
DB_PATH = Path("data/sentinel.db")

# Map of table name → parquet filename. Order matters for FK integrity.
TABLE_MAP: dict[str, str] = {
    "cases_national_weekly":    "cases_national_weekly.parquet",
    "cases_regional_annual":    "cases_regional_annual.parquet",
    "cases_provincial_monthly": "cases_provincial_monthly.parquet",
    "weather_daily":            "weather_daily.parquet",
    "news":                     "news.parquet",
    "trends_weekly":            "trends_weekly.parquet",
    "region_centroids":         "region_centroids.parquet",
}


def _load_parquet(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        logger.warning("Parquet not found, skipping: %s", path)
        return None
    df = pd.read_parquet(path)
    # SQLite doesn't support timezone-aware datetimes — strip tz if present
    for col in df.select_dtypes(include=["datetime64[ns, UTC]", "datetimetz"]).columns:
        df[col] = df[col].dt.tz_localize(None)
    return df


def build_database(
    processed_dir: Path = PROCESSED_DIR,
    db_path: Path = DB_PATH,
) -> None:
    """
    Load every available parquet file and write it as a table in sentinel.db.
    Existing tables are replaced. Missing parquet files are skipped with a warning.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    loaded = 0
    for table, filename in TABLE_MAP.items():
        df = _load_parquet(processed_dir / filename)
        if df is None:
            continue
        df.to_sql(table, conn, if_exists="replace", index=False)
        logger.info("Loaded %-35s → %6d rows", table, len(df))
        loaded += 1

    conn.close()
    size_kb = db_path.stat().st_size / 1024
    logger.info("sentinel.db built: %d tables, %.1f KB at %s", loaded, size_kb, db_path)


def query(sql: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Run a SQL query against sentinel.db and return a DataFrame."""
    conn = sqlite3.connect(db_path)
    result = pd.read_sql_query(sql, conn)
    conn.close()
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    build_database()

    print("\nTable row counts:")
    for table in TABLE_MAP:
        try:
            df = query(f"SELECT COUNT(*) AS n FROM {table}")
            print(f"  {table:<35} {df['n'].iloc[0]:>7} rows")
        except Exception as exc:
            print(f"  {table:<35} MISSING ({exc})")
