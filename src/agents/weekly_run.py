"""
Phase 3 Step 6 — Weekly Run CLI

Runs the full multi-agent briefing workflow for a given date
and optionally saves the output as JSON.

Usage:
    python -m src.agents.weekly_run                        # latest available date
    python -m src.agents.weekly_run --date 2023-10-01      # specific date
    python -m src.agents.weekly_run --date 2023-10-01 --save
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sqlite3
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("data/processed/weekly_briefings")
DB_PATH    = Path("data/sentinel.db")


def _latest_available_date() -> str:
    """Return the most recent week_start in the database as a date string."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT MAX(week_start) FROM cases_national_weekly"
    ).fetchone()
    conn.close()
    raw = row[0]  # "YYYY-MM-DD HH:MM:SS"
    return raw[:10]  # "YYYY-MM-DD"


def save_output(result: dict, out_dir: Path = OUTPUT_DIR) -> Path:
    date_str = result["as_of_date"]
    folder   = out_dir / date_str
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "briefing.json"

    payload = {
        "generated_at": datetime.datetime.now().isoformat(),
        **result,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def print_result(result: dict) -> None:
    risk   = result["risk"]
    ctx    = result["context"]
    latest = ctx["latest_cases"]

    print("\n" + "=" * 70)
    print(f"SentinelPH Weekly Briefing  |  As of {result['as_of_date']}")
    print("=" * 70)
    print(f"Cases (latest week) : {latest['cases']:,}  "
          f"(WoW: {latest['wow_change_pct']:+.1f}%)")
    print(f"4-week trend        : {ctx['four_week_trend']['direction'].upper()}")
    print(f"Risk level (next wk): {risk.get('risk_level','N/A')}  "
          f"| est. {risk.get('predicted_cases', 0):,} cases")
    print(f"Validator           : {'PASS' if result['valid'] else 'WARN'}  "
          f"| attempts={result['attempts']}")
    print("-" * 70)
    print(result["briefing"])
    print("=" * 70)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="SentinelPH weekly dengue briefing")
    parser.add_argument("--date", default=None, help="As-of date (YYYY-MM-DD). Defaults to latest in DB.")
    parser.add_argument("--save", action="store_true", help="Save output to data/processed/weekly_briefings/")
    args = parser.parse_args()

    as_of_date = args.date or _latest_available_date()
    print(f"Running briefing for: {as_of_date} …")

    from src.agents.briefing import run
    result = run(as_of_date)

    print_result(result)

    if args.save:
        path = save_output(result)
        print(f"\nSaved to: {path}")


if __name__ == "__main__":
    main()
