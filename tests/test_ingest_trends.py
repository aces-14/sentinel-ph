"""Tests for the Google Trends ingestion module."""

from pathlib import Path

import pandas as pd
import pytest

PROCESSED = Path("data/processed")


class TestTrendsParquet:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "trends_weekly.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("keyword", "date", "interest"):
            assert col in self.df.columns

    def test_has_dengue_keyword(self) -> None:
        assert "dengue" in self.df["keyword"].values

    def test_interest_range(self) -> None:
        assert (self.df["interest"] >= 0).all()
        assert (self.df["interest"] <= 100).all()

    def test_date_is_datetime(self) -> None:
        assert pd.api.types.is_datetime64_any_dtype(self.df["date"])

    def test_multiple_keywords(self) -> None:
        assert self.df["keyword"].nunique() >= 2
