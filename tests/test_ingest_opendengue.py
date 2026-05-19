"""Tests for the OpenDengue ingestion module."""

from pathlib import Path

import pandas as pd
import pytest

from src.ingest.opendengue import (
    _build_national_weekly,
    _build_provincial_monthly,
    _build_regional_annual,
    _parse_dates_and_epiweek,
    load_opendengue,
)

PROCESSED = Path("data/processed")


# ── Unit tests (work on the already-saved parquet files) ──────────────────────

class TestNationalWeeklyParquet:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "cases_national_weekly.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("week_start", "week_end", "year", "epiweek", "cases"):
            assert col in self.df.columns, f"Missing column: {col}"

    def test_no_null_cases(self) -> None:
        assert self.df["cases"].isna().sum() == 0

    def test_no_negative_cases(self) -> None:
        assert (self.df["cases"] < 0).sum() == 0

    def test_year_range(self) -> None:
        assert int(self.df["year"].min()) >= 2012
        assert int(self.df["year"].max()) <= 2023

    def test_epiweek_range(self) -> None:
        assert self.df["epiweek"].between(1, 53).all()


class TestRegionalAnnualParquet:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "cases_regional_annual.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("region", "year", "cases"):
            assert col in self.df.columns

    def test_has_multiple_regions(self) -> None:
        assert self.df["region"].nunique() > 5

    def test_no_null_cases(self) -> None:
        assert self.df["cases"].isna().sum() == 0


class TestProvincialMonthlyParquet:
    df: pd.DataFrame

    @pytest.fixture(autouse=True)
    def load(self) -> None:
        self.df = pd.read_parquet(PROCESSED / "cases_provincial_monthly.parquet")

    def test_not_empty(self) -> None:
        assert len(self.df) > 0

    def test_required_columns(self) -> None:
        for col in ("region", "province", "year", "cases"):
            assert col in self.df.columns

    def test_has_multiple_provinces(self) -> None:
        assert self.df["province"].nunique() > 10

    def test_no_null_cases(self) -> None:
        assert self.df["cases"].isna().sum() == 0


# ── Integration test (uses cached ZIP, no network) ────────────────────────────

def test_load_opendengue_returns_all_keys(tmp_path: Path) -> None:
    """load_opendengue returns a dict with the three expected resolution keys."""
    result = load_opendengue(
        raw_dir=Path("data/raw"),
        processed_dir=tmp_path,
        force_download=False,
    )
    assert set(result.keys()) == {"national_weekly", "regional_annual", "provincial_monthly"}
    for key, df in result.items():
        assert isinstance(df, pd.DataFrame), f"{key} is not a DataFrame"
        assert len(df) > 0, f"{key} is empty"
