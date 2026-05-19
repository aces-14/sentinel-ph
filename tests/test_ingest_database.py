"""Tests for the SQLite database builder."""

import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path("data/sentinel.db")

EXPECTED_TABLES = [
    "cases_national_weekly",
    "cases_regional_annual",
    "cases_provincial_monthly",
    "weather_daily",
    "news",
    "region_centroids",
]


class TestSentinelDB:
    @pytest.fixture(autouse=True)
    def check_db(self) -> None:
        if not DB_PATH.exists():
            pytest.skip("sentinel.db not yet built — run src.ingest.database first")

    def _query(self, sql: str) -> list:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def test_db_exists(self) -> None:
        assert DB_PATH.exists()

    def test_expected_tables_present(self) -> None:
        rows = self._query("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in rows}
        for expected in EXPECTED_TABLES:
            assert expected in tables, f"Missing table: {expected}"

    def test_cases_national_weekly_not_empty(self) -> None:
        rows = self._query("SELECT COUNT(*) FROM cases_national_weekly")
        assert rows[0][0] > 0

    def test_weather_daily_not_empty(self) -> None:
        rows = self._query("SELECT COUNT(*) FROM weather_daily")
        assert rows[0][0] > 0

    def test_news_not_empty(self) -> None:
        rows = self._query("SELECT COUNT(*) FROM news")
        assert rows[0][0] > 0

    def test_region_centroids_not_empty(self) -> None:
        rows = self._query("SELECT COUNT(*) FROM region_centroids")
        assert rows[0][0] > 0
