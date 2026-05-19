"""Tests for the weather ingestion module."""

from pathlib import Path

import pandas as pd
import pytest

PROCESSED = Path("data/processed")


class TestWeatherParquet:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "weather_daily.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("region", "date", "t_max", "t_min", "precip", "rh_mean"):
            assert col in self.df.columns

    def test_no_null_values(self) -> None:
        for col in ("t_max", "t_min", "precip", "rh_mean"):
            assert self.df[col].isna().sum() == 0, f"Nulls in {col}"

    def test_temperature_range(self) -> None:
        # CAR (Cordillera) highlands can have t_max below 15°C — lower bound is 5°C
        assert (self.df["t_max"] > 5).all(), "t_max below 5°C — outside any PH region range"
        assert (self.df["t_max"] < 45).all(), "t_max above 45°C — unlikely for Philippines"

    def test_precipitation_non_negative(self) -> None:
        assert (self.df["precip"] >= 0).all()

    def test_humidity_range(self) -> None:
        assert (self.df["rh_mean"] >= 0).all()
        assert (self.df["rh_mean"] <= 100).all()

    def test_date_range(self) -> None:
        assert self.df["date"].min() >= pd.Timestamp("2012-01-01")
        assert self.df["date"].max() <= pd.Timestamp("2023-12-31")

    def test_multiple_regions(self) -> None:
        assert self.df["region"].nunique() >= 10
