"""
Download and process OpenDengue V1.3 Philippines case data.

Source: https://github.com/OpenDengue/master-repo

What OpenDengue has for the Philippines (confirmed as of V1.3):
  - Admin0 / National / Weekly  : 2012–2023  →  cases_national_weekly.parquet
  - Admin1 / Region   / Annual  : 1999–2020  →  cases_regional_annual.parquet
  - Admin2 / Province / Monthly : 1993–2010  →  cases_provincial_monthly.parquet

The project uses:
  - National weekly  → risk model time series + trend charts
  - Regional annual  → choropleth map breakdown
  - Provincial monthly → historical reference / EDA only
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

SPATIAL_URL = (
    "https://github.com/OpenDengue/master-repo/raw/main"
    "/data/releases/V1.3/Spatial_extract_V1_3.zip"
)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def _download_zip(url: str) -> bytes:
    logger.info("Downloading %s", url)
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def _read_csv_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError("No CSV files found inside ZIP archive.")
        logger.info("Reading %s from ZIP", csv_names[0])
        with zf.open(csv_names[0]) as f:
            return pd.read_csv(f, low_memory=False)


def _filter_philippines(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["adm_0_name"].str.strip().str.upper() == "PHILIPPINES"
    result = df[mask].copy()
    logger.info("Philippines rows: %d (of %d total)", len(result), len(df))
    if result.empty:
        raise ValueError(
            "No Philippines rows found. Check 'adm_0_name' values: "
            + str(df["adm_0_name"].unique()[:10])
        )
    return result


def _parse_dates_and_epiweek(df: pd.DataFrame) -> pd.DataFrame:
    df["week_start"] = pd.to_datetime(df["calendar_start_date"], errors="coerce")
    df["week_end"] = pd.to_datetime(df["calendar_end_date"], errors="coerce")
    iso = df["week_start"].dt.isocalendar()
    df["year"] = iso.year.astype("Int64")
    df["epiweek"] = iso.week.astype("Int64")
    df["cases"] = pd.to_numeric(df["dengue_total"], errors="coerce")
    return df


def _validate(df: pd.DataFrame, label: str) -> None:
    null_cases = df["cases"].isna().sum()
    null_dates = df["week_start"].isna().sum()
    neg_cases = (df["cases"] < 0).sum()
    logger.info(
        "[%s] rows: %d | null cases: %d | null dates: %d | negative: %d",
        label, len(df), null_cases, null_dates, neg_cases,
    )


def _build_national_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Admin0 + Weekly — 2012–2023, 544 rows."""
    sub = df[(df["S_res"] == "Admin0") & (df["T_res"] == "Week")].copy()
    sub = sub[["week_start", "week_end", "year", "epiweek", "cases"]].reset_index(drop=True)
    _validate(sub, "national_weekly")
    return sub


def _build_regional_annual(df: pd.DataFrame) -> pd.DataFrame:
    """Admin1 + Year — 1999–2020, 224 rows."""
    sub = df[(df["S_res"] == "Admin1") & (df["T_res"] == "Year")].copy()
    sub = sub.rename(columns={"adm_1_name": "region"})
    sub = sub[["region", "week_start", "week_end", "year", "cases"]].reset_index(drop=True)
    _validate(sub, "regional_annual")
    return sub


def _build_provincial_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Admin2 + Month — 1993–2010, 9,060 rows."""
    sub = df[(df["S_res"] == "Admin2") & (df["T_res"] == "Month")].copy()
    sub = sub.rename(columns={"adm_1_name": "region", "adm_2_name": "province"})
    sub = sub[["region", "province", "week_start", "week_end", "year", "epiweek", "cases"]].reset_index(drop=True)
    _validate(sub, "provincial_monthly")
    return sub


def load_opendengue(
    raw_dir: Path = RAW_DIR,
    processed_dir: Path = PROCESSED_DIR,
    force_download: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Download OpenDengue spatial extract, filter to Philippines, and save three
    resolution-specific parquet files. Returns a dict with keys:
      'national_weekly', 'regional_annual', 'provincial_monthly'
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    zip_path = raw_dir / "opendengue_spatial_v1_3.zip"

    if not zip_path.exists() or force_download:
        zip_bytes = _download_zip(SPATIAL_URL)
        zip_path.write_bytes(zip_bytes)
        logger.info("Saved raw ZIP to %s", zip_path)
    else:
        logger.info("Using cached ZIP at %s", zip_path)
        zip_bytes = zip_path.read_bytes()

    raw_df = _read_csv_from_zip(zip_bytes)
    ph_df = _filter_philippines(raw_df)
    ph_df = _parse_dates_and_epiweek(ph_df)

    results = {
        "national_weekly": _build_national_weekly(ph_df),
        "regional_annual": _build_regional_annual(ph_df),
        "provincial_monthly": _build_provincial_monthly(ph_df),
    }

    for key, frame in results.items():
        out = processed_dir / f"cases_{key}.parquet"
        frame.to_parquet(out, index=False)
        logger.info("Saved %d rows → %s", len(frame), out)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    data = load_opendengue()

    for name, df in data.items():
        print(f"\n=== {name} ===")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Year range: {df['year'].min()} – {df['year'].max()}")
        print(df.head(3).to_string())
