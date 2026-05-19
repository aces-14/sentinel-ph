"""
Pull historical daily weather per PH region from Open-Meteo ERA5 Archive API.

Endpoint: https://archive-api.open-meteo.com/v1/era5
No API key required. Free tier: 10,000 req/day.

Covers 2012-01-01 to 2023-12-31, matching the national weekly case data range.
One API call per region (~17 calls total).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/era5"
PROCESSED_DIR = Path("data/processed")

DATE_START = "2012-01-01"
DATE_END = "2023-12-31"

# Centroids (lat, lon) for every region name variant found in OpenDengue PH data.
# Multiple keys may map to the same coordinates where OpenDengue uses inconsistent
# names for the same geographic area.
REGION_CENTROIDS: dict[str, tuple[float, float]] = {
    "NATIONAL CAPITAL REGION (NCR)":                        (14.5995, 120.9842),
    "CORDILLERA ADMINISTRATIVE REGION (CAR)":               (17.3519, 121.1745),
    "REGION I (ILOCOS REGION)":                             (17.5645, 120.3874),
    "REGION II (CAGAYAN VALLEY)":                           (17.6132, 121.7270),
    "REGION III (CENTRAL LUZON)":                           (15.4827, 120.7120),
    "REGION IV-A (CALABARZON)":                             (14.1007, 121.0794),
    # Old pre-split Region IV (CALABARZON + MIMAROPA); centroid is midpoint
    "REGION 4":                                             (12.7000, 120.9000),
    "REGION IV-B (MIMAROPA)":                               ( 9.8432, 118.7357),
    "REGION V (BICOL REGION)":                              (13.4209, 123.4137),
    "REGION VI (WESTERN VISAYAS)":                          (11.0064, 122.5322),
    "REGION VII (CENTRAL VISAYAS)":                         (10.3157, 123.8854),
    "REGION VIII (EASTERN VISAYAS)":                        (11.2499, 125.0011),
    "REGION IX (ZAMBOANGA PENINSULA)":                      ( 7.8383, 123.2928),
    "REGION X (NORTHERN MINDANAO)":                         ( 8.0202, 124.6856),
    "REGION XI (DAVAO REGION)":                             ( 7.3041, 126.0893),
    "REGION XII (SOCCSKSARGEN)":                            ( 6.2700, 124.6860),
    "REGION XIII (CARAGA)":                                 ( 8.9456, 125.7972),
    "REGION CARAGA (CARAGA)":                               ( 8.9456, 125.7972),
    "AUTONOMOUS REGION IN MUSLIM MINDANAO (ARMM)":          ( 6.9560, 124.2422),
    "BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO (BARMM)": (6.9560, 124.2422),
}


def _fetch_weather(region: str, lat: float, lon: float) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": DATE_START,
        "end_date": DATE_END,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "relative_humidity_2m_mean",
        ]),
        "timezone": "Asia/Manila",
    }
    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    daily = payload.get("daily", {})
    if not daily:
        raise ValueError(f"Empty daily payload for region {region!r}")

    df = pd.DataFrame(daily)
    df.rename(columns={
        "time": "date",
        "temperature_2m_max": "t_max",
        "temperature_2m_min": "t_min",
        "precipitation_sum": "precip",
        "relative_humidity_2m_mean": "rh_mean",
    }, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df.insert(0, "region", region)
    return df


def _deduplicate_regions(
    centroids: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Keep only one name per unique (lat, lon) pair to avoid duplicate API calls."""
    seen: dict[tuple[float, float], str] = {}
    unique: dict[str, tuple[float, float]] = {}
    for name, coords in centroids.items():
        if coords not in seen:
            seen[coords] = name
            unique[name] = coords
    return unique


def _fetch_with_retry(
    region: str, lat: float, lon: float, max_retries: int = 5
) -> pd.DataFrame:
    """Fetch with exponential backoff on rate-limit (429) errors."""
    for attempt in range(max_retries):
        try:
            return _fetch_weather(region, lat, lon)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = 10 * (2 ** attempt)
                logger.warning("Rate limited. Waiting %ds before retry %d/%d …", wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed to fetch {region!r} after {max_retries} retries.")


def load_weather(
    processed_dir: Path = PROCESSED_DIR,
    sleep_between: float = 3.0,
) -> pd.DataFrame:
    """
    Fetch daily weather for every PH region and save to
    data/processed/weather_daily.parquet. Resumes automatically —
    regions already present in the parquet file are skipped.
    Returns the complete combined DataFrame.
    """
    processed_dir.mkdir(parents=True, exist_ok=True)
    out = processed_dir / "weather_daily.parquet"

    # Load previously fetched regions to support resume
    existing_regions: set[str] = set()
    existing_frame: pd.DataFrame | None = None
    if out.exists():
        existing_frame = pd.read_parquet(out)
        existing_regions = set(existing_frame["region"].unique())
        logger.info("Resuming — already have data for %d region(s): %s",
                    len(existing_regions), sorted(existing_regions))

    unique_regions = _deduplicate_regions(REGION_CENTROIDS)
    pending = {k: v for k, v in unique_regions.items() if k not in existing_regions}
    logger.info("%d region(s) to fetch.", len(pending))

    frames: list[pd.DataFrame] = []
    for i, (region, (lat, lon)) in enumerate(pending.items(), 1):
        logger.info("[%d/%d] Fetching weather for %s …", i, len(pending), region)
        try:
            df = _fetch_with_retry(region, lat, lon)
            frames.append(df)
            logger.info("  → %d rows", len(df))
        except Exception as exc:
            logger.error("  ✗ Failed for %s: %s", region, exc)
        time.sleep(sleep_between)

    all_frames = []
    if existing_frame is not None:
        all_frames.append(existing_frame)
    all_frames.extend(frames)

    if not all_frames:
        raise RuntimeError("No weather data available.")

    combined = pd.concat(all_frames, ignore_index=True)

    null_count = combined[["t_max", "t_min", "precip", "rh_mean"]].isna().sum()
    logger.info("Null counts per column:\n%s", null_count.to_string())

    combined.to_parquet(out, index=False)
    logger.info("Saved %d rows (%d regions) → %s", len(combined), combined["region"].nunique(), out)
    return combined


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_weather()
    print(df.dtypes)
    print(df.head())
    print(f"\nRegions fetched: {df['region'].nunique()}")
    print(f"Date range: {df['date'].min().date()} – {df['date'].max().date()}")
    print(f"Total rows: {len(df):,}")
