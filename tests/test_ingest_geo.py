"""Tests for the geographic data ingestion module."""

import json
from pathlib import Path

import pandas as pd
import pytest

RAW_GEO = Path("data/raw/geo")
PROCESSED = Path("data/processed")


class TestGeoJSON:
    def test_file_exists(self) -> None:
        assert (RAW_GEO / "ph_regions.geojson").exists()

    def test_is_valid_geojson(self) -> None:
        with open(RAW_GEO / "ph_regions.geojson", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("type") == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

    def test_has_name_property(self) -> None:
        with open(RAW_GEO / "ph_regions.geojson", encoding="utf-8") as f:
            data = json.load(f)
        for feat in data["features"][:5]:
            props = feat.get("properties", {})
            assert "NAME_1" in props or "name" in props


class TestRegionCentroids:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "region_centroids.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("region_gadm", "lat", "lon"):
            assert col in self.df.columns

    def test_coordinates_within_philippines(self) -> None:
        # Philippines bounding box: lat 4–22, lon 116–128
        assert (self.df["lat"].between(4, 22)).all(), "lat outside Philippines range"
        assert (self.df["lon"].between(116, 128)).all(), "lon outside Philippines range"

    def test_sufficient_coverage(self) -> None:
        # GADM level 1 for Philippines gives 81 provinces
        assert len(self.df) >= 17, "Expected at least 17 geographic units"
