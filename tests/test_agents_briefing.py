"""Tests for the multi-agent briefing workflow."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

DB_AVAILABLE    = Path("data/sentinel.db").exists()
MODEL_AVAILABLE = Path("models/xgb_dengue_risk.joblib").exists()


# ── Context builder ───────────────────────────────────────────────────────────

class TestBuildContext:
    @pytest.fixture(autouse=True)
    def skip_if_no_db(self):
        if not DB_AVAILABLE:
            pytest.skip("sentinel.db not available")

    def test_returns_expected_keys(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2023-10-01")
        required = [
            "as_of_date", "latest_cases", "four_week_trend",
            "weather_latest_week", "google_trends_dengue_index",
            "news_articles_last_4_weeks", "is_rainy_season", "month_name", "year",
        ]
        for key in required:
            assert key in ctx, f"Missing context key: {key}"

    def test_latest_cases_has_correct_fields(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2023-10-01")
        lc = ctx["latest_cases"]
        assert "cases" in lc
        assert "wow_change_pct" in lc
        assert "week_start" in lc
        assert lc["cases"] > 0

    def test_four_week_trend_direction_valid(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2023-10-01")
        assert ctx["four_week_trend"]["direction"] in {"rising", "falling", "stable"}
        assert len(ctx["four_week_trend"]["weekly_cases"]) == 4

    def test_weather_present_and_reasonable(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2023-10-01")
        wx = ctx["weather_latest_week"]
        assert wx is not None
        assert 15 <= wx["avg_t_max_c"] <= 45
        assert wx["total_precip_mm"] >= 0
        assert 0 <= wx["avg_humidity_pct"] <= 100

    def test_is_rainy_season_october(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2023-10-01")
        assert ctx["is_rainy_season"] is True

    def test_is_rainy_season_february(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2022-02-01")
        assert ctx["is_rainy_season"] is False

    def test_news_count_non_negative(self):
        from src.agents.briefing import _build_context
        ctx = _build_context("2023-10-01")
        assert ctx["news_articles_last_4_weeks"] >= 0

    def test_raises_on_date_before_data(self):
        from src.agents.briefing import _build_context
        with pytest.raises(ValueError):
            _build_context("2000-01-01")


# ── Agent state and routing ───────────────────────────────────────────────────

class TestAgentRouting:
    def test_should_retry_when_valid(self):
        from src.agents.briefing import _should_retry, AgentState
        state: AgentState = {
            "as_of_date": "2023-10-01", "context": {}, "risk": {},
            "briefing": "ok", "attempts": 1, "valid": True, "feedback": "",
        }
        assert _should_retry(state) == "end"

    def test_should_retry_when_retries_exhausted(self):
        from src.agents.briefing import _should_retry, MAX_RETRIES, AgentState
        state: AgentState = {
            "as_of_date": "2023-10-01", "context": {}, "risk": {},
            "briefing": "bad", "attempts": MAX_RETRIES, "valid": False, "feedback": "x",
        }
        assert _should_retry(state) == "end"

    def test_should_retry_when_invalid_and_retries_remain(self):
        from src.agents.briefing import _should_retry, AgentState
        state: AgentState = {
            "as_of_date": "2023-10-01", "context": {}, "risk": {},
            "briefing": "bad", "attempts": 1, "valid": False, "feedback": "issue",
        }
        assert _should_retry(state) == "generate"

    def test_graph_builds(self):
        from src.agents.briefing import build_graph
        graph = build_graph()
        assert graph is not None


# ── Mocked end-to-end run ─────────────────────────────────────────────────────

class TestRunMocked:
    @patch("src.agents.briefing._get_llm")
    @patch("src.agents.briefing._get_scorer")
    @patch("src.agents.briefing._build_context")
    def test_run_returns_expected_keys(self, mock_ctx, mock_scorer, mock_llm):
        from src.agents.briefing import run
        import src.agents.briefing as bmod

        mock_ctx.return_value = {
            "as_of_date": "2023-10-01",
            "latest_cases": {"week_start": "2023-10-01", "epiweek": 39, "cases": 3142,
                             "wow_change_pct": -1.2, "yoy_change_pct": -18.7},
            "four_week_trend": {"weekly_cases": [3356, 3393, 3179, 3142], "direction": "falling"},
            "weather_latest_week": {"avg_t_max_c": 28.9, "avg_t_min_c": 23.0,
                                    "total_precip_mm": 654.6, "avg_humidity_pct": 84.5},
            "google_trends_dengue_index": 43,
            "news_articles_last_4_weeks": 29,
            "is_rainy_season": True,
            "month_name": "October",
            "year": 2023,
        }

        mock_risk = MagicMock()
        mock_risk.predict.return_value = {
            "as_of_date": "2023-10-01", "forecast_week": "2023-10-08",
            "predicted_cases": 3675, "log_pred": 8.21,
            "risk_level": "MEDIUM", "top_drivers": [],
        }
        mock_scorer.return_value = mock_risk

        llm_mock = MagicMock()
        briefing_resp = MagicMock()
        briefing_resp.content = "Surveillance data indicates 3,142 cases this week [MEDIUM risk]."
        validator_resp = MagicMock()
        validator_resp.content = "PASS"
        llm_mock.invoke.side_effect = [briefing_resp, validator_resp]
        mock_llm.return_value = llm_mock

        bmod._graph = None  # reset singleton
        result = run("2023-10-01")

        assert "briefing" in result
        assert "risk" in result
        assert "context" in result
        assert "valid" in result
        assert result["attempts"] == 1
        assert result["valid"] is True

    @patch("src.agents.briefing._get_llm")
    @patch("src.agents.briefing._get_scorer")
    @patch("src.agents.briefing._build_context")
    def test_run_retries_on_evaluator_fail(self, mock_ctx, mock_scorer, mock_llm):
        from src.agents.briefing import run
        import src.agents.briefing as bmod

        mock_ctx.return_value = {
            "as_of_date": "2023-10-01",
            "latest_cases": {"week_start": "2023-10-01", "epiweek": 39,
                             "cases": 3142, "wow_change_pct": -1.2, "yoy_change_pct": -18.7},
            "four_week_trend": {"weekly_cases": [3356, 3393, 3179, 3142], "direction": "falling"},
            "weather_latest_week": None,
            "google_trends_dengue_index": 43,
            "news_articles_last_4_weeks": 5,
            "is_rainy_season": True,
            "month_name": "October",
            "year": 2023,
        }
        mock_risk = MagicMock()
        mock_risk.predict.return_value = {
            "as_of_date": "2023-10-01", "forecast_week": "2023-10-08",
            "predicted_cases": 3675, "log_pred": 8.21,
            "risk_level": "MEDIUM", "top_drivers": [],
        }
        mock_scorer.return_value = mock_risk

        llm_mock = MagicMock()
        r1 = MagicMock(); r1.content = "Bad briefing."
        v1 = MagicMock(); v1.content = "FAIL_UNCERTAINTY: overly confident"
        r2 = MagicMock(); r2.content = "Surveillance data suggests 3,142 cases [MEDIUM]."
        v2 = MagicMock(); v2.content = "PASS"
        llm_mock.invoke.side_effect = [r1, v1, r2, v2]
        mock_llm.return_value = llm_mock

        bmod._graph = None
        result = run("2023-10-01")

        assert result["attempts"] == 2
        assert result["valid"] is True


# ── Save output ───────────────────────────────────────────────────────────────

class TestSaveOutput:
    def test_saves_json_file(self, tmp_path):
        from src.agents.weekly_run import save_output
        result = {
            "as_of_date": "2023-10-01",
            "context": {"latest_cases": {"cases": 3142}},
            "risk": {"risk_level": "MEDIUM"},
            "briefing": "Test briefing.",
            "attempts": 1,
            "valid": True,
        }
        path = save_output(result, out_dir=tmp_path)
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["briefing"] == "Test briefing."
        assert data["as_of_date"] == "2023-10-01"
        assert "generated_at" in data
