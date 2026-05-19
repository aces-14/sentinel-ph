"""
Download Philippines region boundaries (GeoJSON) from GADM 4.1 and
compute region centroids for weather/map use.

GADM level 1 = regions (17 official + historical variants).
Source: https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_PHL_1.json.zip
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

GADM_URL = (
    "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_PHL_1.json.zip"
)

RAW_GEO_DIR = Path("data/raw/geo")
PROCESSED_DIR = Path("data/processed")


def _download_geojson(url: str) -> dict:
    logger.info("Downloading %s …", url)
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        json_names = [n for n in zf.namelist() if n.endswith(".json") or n.endswith(".geojson")]
        if not json_names:
            raise ValueError("No JSON file found in ZIP.")
        logger.info("Reading %s from ZIP", json_names[0])
        with zf.open(json_names[0]) as f:
            return json.load(f)


def _centroid(coordinates: list) -> tuple[float, float]:
    """Naïve centroid: average of all polygon vertex coordinates."""
    lons, lats = [], []

    def _walk(coords: list) -> None:
        if isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for c in coords:
                _walk(c)

    _walk(coordinates)
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def load_geo(
    raw_dir: Path = RAW_GEO_DIR,
    processed_dir: Path = PROCESSED_DIR,
    force_download: bool = False,
) -> tuple[dict, pd.DataFrame]:
    """
    Download Philippines region boundaries and compute centroids.
    Saves:
      - data/raw/geo/ph_regions.geojson
      - data/processed/region_centroids.parquet  [region, lat, lon]
    Returns (geojson_dict, centroids_df).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    geojson_path = raw_dir / "ph_regions.geojson"

    if not geojson_path.exists() or force_download:
        geojson = _download_geojson(GADM_URL)
        geojson_path.write_text(json.dumps(geojson), encoding="utf-8")
        logger.info("Saved GeoJSON → %s", geojson_path)
    else:
        logger.info("Using cached GeoJSON at %s", geojson_path)
        with open(geojson_path, encoding="utf-8") as f:
            geojson = json.load(f)

    features = geojson.get("features", [])
    logger.info("Loaded %d region features", len(features))

    rows = []
    for feat in features:
        props = feat.get("properties", {})
        name = props.get("NAME_1", props.get("name", "Unknown"))
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords:
            lat, lon = _centroid(coords)
            rows.append({"region_gadm": name, "lat": round(lat, 6), "lon": round(lon, 6)})

    centroids_df = pd.DataFrame(rows)
    out = processed_dir / "region_centroids.parquet"
    centroids_df.to_parquet(out, index=False)
    logger.info("Saved %d region centroids → %s", len(centroids_df), out)

    return geojson, centroids_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    geojson, centroids = load_geo()
    print(f"Features in GeoJSON: {len(geojson['features'])}")
    print(centroids.to_string())
