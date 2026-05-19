"""Tests for the GDELT news ingestion module."""

from pathlib import Path

import pandas as pd
import pytest

PROCESSED = Path("data/processed")


class TestNewsParquet:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "news.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("url", "title", "seen_date"):
            assert col in self.df.columns

    def test_no_duplicate_urls(self) -> None:
        assert self.df["url"].duplicated().sum() == 0

    def test_seen_date_is_datetime(self) -> None:
        assert pd.api.types.is_datetime64_any_dtype(self.df["seen_date"])

    def test_minimum_article_count(self) -> None:
        # Given GDELT instability, we accept anything above 500 as partial success
        assert len(self.df) >= 500, f"Only {len(self.df)} articles — expected at least 500"
