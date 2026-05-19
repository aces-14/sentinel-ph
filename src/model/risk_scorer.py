"""
Phase 3 Step 3 — Risk Scorer

Loads the trained XGBoost model and provides a clean predict() API
for use by the multi-agent workflow and the dashboard.

Usage:
    from src.model.risk_scorer import RiskScorer
    scorer = RiskScorer.load()
    result = scorer.predict(as_of_date="2023-10-01")
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.model.features import build_features, get_feature_columns

logger = logging.getLogger(__name__)

MODEL_PATH = Path("models/xgb_dengue_risk.joblib")
META_PATH  = Path("models/model_meta.json")

RISK_LABELS = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}


class RiskScorer:
    """
    Wrapper around the trained XGBoost dengue risk model.

    Attributes
    ----------
    model          : fitted XGBRegressor
    feature_columns: list of feature names in training order
    thresholds     : {"low_max": float, "medium_max": float}
    top_features   : list of {feature, importance} dicts
    """

    def __init__(self, model, feature_columns: list[str], meta: dict) -> None:
        self.model          = model
        self.feature_columns = feature_columns
        self.thresholds     = meta["risk_thresholds"]
        self.top_features   = meta["top_features"]
        self._feature_df: pd.DataFrame | None = None  # cached feature matrix

    @classmethod
    def load(
        cls,
        model_path: Path = MODEL_PATH,
        meta_path: Path = META_PATH,
    ) -> "RiskScorer":
        """Load model and metadata from disk. Raises FileNotFoundError if not yet trained."""
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. Run `python -m src.model.train` first."
            )
        model = joblib.load(model_path)
        with open(meta_path) as f:
            meta = json.load(f)
        logger.debug("RiskScorer loaded from %s", model_path)
        return cls(model, meta["feature_columns"], meta)

    def _get_features(self) -> pd.DataFrame:
        """Build (or return cached) feature matrix."""
        if self._feature_df is None:
            self._feature_df = build_features()
        return self._feature_df

    def _risk_level(self, log_pred: float) -> str:
        if log_pred <= self.thresholds["low_max"]:
            return "LOW"
        if log_pred <= self.thresholds["medium_max"]:
            return "MEDIUM"
        return "HIGH"

    def predict(self, as_of_date: str | date) -> dict:
        """
        Predict dengue risk for the week FOLLOWING as_of_date.

        Parameters
        ----------
        as_of_date : str | date
            The last date for which surveillance data is available,
            e.g. "2023-10-01" or date(2023, 10, 1).

        Returns
        -------
        dict with keys:
            as_of_date     : str  — the input date
            forecast_week  : str  — the week being forecast (as_of_date + 7 days)
            predicted_cases: int  — back-transformed case count estimate
            log_pred       : float — raw log-scale prediction
            risk_level     : str  — "LOW" | "MEDIUM" | "HIGH"
            top_drivers    : list[dict] — top 5 features with their values and importances
        """
        if isinstance(as_of_date, str):
            as_of_date = pd.to_datetime(as_of_date).date()

        df = self._get_features()

        # Find the row whose week_start is the most recent week at or before as_of_date
        mask = df["week_start"].dt.date <= as_of_date
        if not mask.any():
            raise ValueError(f"No feature data available for or before {as_of_date}")

        row = df[mask].iloc[-1]
        X   = row[self.feature_columns].values.reshape(1, -1)

        log_pred = float(self.model.predict(X)[0])
        predicted_cases = int(np.expm1(max(log_pred, 0)))
        risk_level = self._risk_level(log_pred)

        # Top 5 drivers: feature importance weighted by feature value
        importance_map = {d["feature"]: d["importance"] for d in self.top_features}
        drivers = []
        for feat in self.feature_columns:
            imp = importance_map.get(feat, 0.0)
            val = float(row[feat])
            drivers.append({"feature": feat, "value": round(val, 4), "importance": imp})
        drivers = sorted(drivers, key=lambda d: d["importance"], reverse=True)[:5]

        forecast_week = as_of_date + timedelta(days=7)

        return {
            "as_of_date":      str(as_of_date),
            "forecast_week":   str(forecast_week),
            "predicted_cases": predicted_cases,
            "log_pred":        round(log_pred, 4),
            "risk_level":      risk_level,
            "top_drivers":     drivers,
        }

    def predict_range(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """
        Predict risk for every available week between start_date and end_date.
        Useful for back-testing and dashboard trend lines.
        """
        df = self._get_features()
        start = pd.to_datetime(start_date)
        end   = pd.to_datetime(end_date)
        weeks = df[(df["week_start"] >= start) & (df["week_start"] <= end)]["week_start"]
        return [self.predict(w.date()) for w in weeks]


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    scorer = RiskScorer.load()
    result = scorer.predict("2023-10-01")

    print("\nRisk Prediction")
    print(f"  As of        : {result['as_of_date']}")
    print(f"  Forecast week: {result['forecast_week']}")
    print(f"  Cases (est.) : {result['predicted_cases']:,}")
    print(f"  Risk level   : {result['risk_level']}")
    print("  Top drivers  :")
    for d in result["top_drivers"]:
        print(f"    {d['feature']:<30} value={d['value']:.3f}  importance={d['importance']:.4f}")
