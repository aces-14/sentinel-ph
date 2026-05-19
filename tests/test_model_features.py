"""Tests for the risk model feature engineering pipeline."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path


DATA_AVAILABLE = (
    Path("data/processed/cases_national_weekly.parquet").exists()
    and Path("data/processed/weather_daily.parquet").exists()
    and Path("data/processed/trends_weekly.parquet").exists()
    and Path("data/processed/news.parquet").exists()
)


@pytest.fixture(scope="module")
def feature_df():
    if not DATA_AVAILABLE:
        pytest.skip("Processed data not available")
    from src.model.features import build_features
    return build_features()


class TestFeatureMatrix:
    def test_builds_without_error(self, feature_df):
        assert feature_df is not None

    def test_has_expected_columns(self, feature_df):
        from src.model.features import get_feature_columns
        feat_cols = get_feature_columns(feature_df)
        required = [
            "cases_lag1", "cases_lag2", "cases_lag4", "cases_lag8", "cases_roll4",
            "weather_t_max_lag1", "weather_precip_lag1", "weather_rh_lag1",
            "trend_dengue", "news_count",
            "epiweek", "month", "is_rainy_season",
        ]
        for col in required:
            assert col in feat_cols, f"Missing feature column: {col}"

    def test_no_nan_values(self, feature_df):
        assert not feature_df.isnull().any().any(), "Feature matrix contains NaN values"

    def test_target_column_present(self, feature_df):
        assert "target_log_cases" in feature_df.columns

    def test_target_is_log_scaled(self, feature_df):
        # log1p(cases) should be positive and not unreasonably large
        assert feature_df["target_log_cases"].min() >= 0
        assert feature_df["target_log_cases"].max() < 15  # log1p(3M) ~ 14.9

    def test_week_start_is_datetime(self, feature_df):
        assert pd.api.types.is_datetime64_any_dtype(feature_df["week_start"])

    def test_date_range_plausible(self, feature_df):
        assert feature_df["week_start"].min().year >= 2012
        assert feature_df["week_start"].max().year <= 2023

    def test_no_future_leakage_in_case_lags(self, feature_df):
        # cases_lag1 should equal the previous row's log_cases equivalent
        # Verify by checking lag1 < current target (lag1 is from LAST week)
        # Simple check: lag1 != target (they should differ for most rows)
        different = (feature_df["cases_lag1"] != feature_df["target_log_cases"]).mean()
        assert different > 0.5, "cases_lag1 looks suspiciously identical to target"

    def test_is_rainy_season_binary(self, feature_df):
        assert set(feature_df["is_rainy_season"].unique()).issubset({0, 1})

    def test_epiweek_range(self, feature_df):
        assert feature_df["epiweek"].between(1, 53).all()

    def test_news_count_non_negative(self, feature_df):
        assert (feature_df["news_count"] >= 0).all()

    def test_sufficient_rows(self, feature_df):
        # With 544 total weeks and 9 dropped for lags/target, expect ~500+
        assert len(feature_df) >= 500

    def test_get_feature_columns_excludes_metadata(self, feature_df):
        from src.model.features import get_feature_columns
        feat_cols = get_feature_columns(feature_df)
        assert "week_start" not in feat_cols
        assert "target_log_cases" not in feat_cols
