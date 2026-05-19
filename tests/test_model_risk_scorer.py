"""Tests for the RiskScorer wrapper."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np


MODEL_AVAILABLE = (
    Path("models/xgb_dengue_risk.joblib").exists()
    and Path("models/model_meta.json").exists()
)


@pytest.fixture(scope="module")
def scorer():
    if not MODEL_AVAILABLE:
        pytest.skip("Model not trained yet — run src.model.train first")
    from src.model.risk_scorer import RiskScorer
    return RiskScorer.load()


class TestRiskScorer:
    def test_loads_without_error(self, scorer):
        assert scorer is not None

    def test_has_feature_columns(self, scorer):
        assert len(scorer.feature_columns) > 0

    def test_has_thresholds(self, scorer):
        assert "low_max" in scorer.thresholds
        assert "medium_max" in scorer.thresholds
        assert scorer.thresholds["low_max"] < scorer.thresholds["medium_max"]

    def test_predict_returns_expected_keys(self, scorer):
        result = scorer.predict("2023-06-01")
        expected = {"as_of_date", "forecast_week", "predicted_cases", "log_pred", "risk_level", "top_drivers"}
        assert set(result.keys()) == expected

    def test_predict_risk_level_valid(self, scorer):
        result = scorer.predict("2023-06-01")
        assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH"}

    def test_predict_cases_positive(self, scorer):
        result = scorer.predict("2023-06-01")
        assert result["predicted_cases"] >= 0

    def test_predict_log_pred_reasonable(self, scorer):
        result = scorer.predict("2023-06-01")
        # log1p(100) ~ 4.6, log1p(1M) ~ 13.8
        assert 0 <= result["log_pred"] <= 15

    def test_predict_forecast_week_is_7_days_later(self, scorer):
        from datetime import date, timedelta
        result = scorer.predict("2023-10-01")
        as_of  = date.fromisoformat(result["as_of_date"])
        fcst   = date.fromisoformat(result["forecast_week"])
        assert fcst == as_of + timedelta(days=7)

    def test_predict_accepts_string_date(self, scorer):
        result = scorer.predict("2022-01-01")
        assert result["as_of_date"] is not None

    def test_predict_accepts_date_object(self, scorer):
        from datetime import date
        result = scorer.predict(date(2022, 1, 1))
        assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH"}

    def test_top_drivers_has_five_items(self, scorer):
        result = scorer.predict("2023-06-01")
        assert len(result["top_drivers"]) == 5

    def test_top_drivers_have_correct_keys(self, scorer):
        result = scorer.predict("2023-06-01")
        for driver in result["top_drivers"]:
            assert "feature" in driver
            assert "value" in driver
            assert "importance" in driver

    def test_predict_out_of_range_raises(self, scorer):
        with pytest.raises(ValueError):
            scorer.predict("1990-01-01")

    def test_load_raises_without_model(self):
        from src.model.risk_scorer import RiskScorer
        with pytest.raises(FileNotFoundError):
            RiskScorer.load(model_path=Path("models/__nonexistent__.joblib"))

    def test_predict_range_returns_list(self, scorer):
        results = scorer.predict_range("2023-01-01", "2023-03-31")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all("risk_level" in r for r in results)
