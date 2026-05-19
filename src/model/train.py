"""
Phase 3 Step 2 — Risk Model Training

Trains an XGBoost model to predict next-week national dengue cases (log-scaled).
Evaluates against a naive seasonal baseline and an ARIMA baseline.
Saves the trained model and metadata to models/.

Temporal split (no data leakage):
  Train : 2012-12-30 to 2020-12-31
  Val   : 2021-01-01 to 2021-12-31  (used for early stopping)
  Test  : 2022-01-01 to 2023-12-31

Usage:
    python -m src.model.train
    python -m src.model.train --force   # rebuild even if artifact exists
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from src.model.features import build_features, get_feature_columns

logger = logging.getLogger(__name__)

MODELS_DIR   = Path("models")
MODEL_PATH   = MODELS_DIR / "xgb_dengue_risk.joblib"
META_PATH    = MODELS_DIR / "model_meta.json"

TRAIN_END = "2020-12-31"
VAL_END   = "2021-12-31"


# ── Temporal split ────────────────────────────────────────────────────────────

def temporal_split(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split feature matrix into train / val / test by date (no shuffle)."""
    train = df[df["week_start"] <= TRAIN_END].copy()
    val   = df[(df["week_start"] > TRAIN_END) & (df["week_start"] <= VAL_END)].copy()
    test  = df[df["week_start"] > VAL_END].copy()
    logger.info(
        "Split: train=%d val=%d test=%d",
        len(train), len(val), len(test),
    )
    return train, val, test


# ── Metrics ───────────────────────────────────────────────────────────────────

def _metrics(y_true: np.ndarray, y_pred: np.ndarray, label: str) -> dict:
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae  = mean_absolute_error(y_true, y_pred)
    # Back-transform to case counts for interpretability
    cases_true = np.expm1(y_true)
    cases_pred = np.expm1(np.clip(y_pred, 0, None))
    rmse_cases = np.sqrt(mean_squared_error(cases_true, cases_pred))
    mae_cases  = mean_absolute_error(cases_true, cases_pred)
    result = {
        "label":      label,
        "rmse_log":   round(rmse, 4),
        "mae_log":    round(mae, 4),
        "rmse_cases": round(rmse_cases, 1),
        "mae_cases":  round(mae_cases, 1),
    }
    logger.info(
        "[%s] RMSE=%.4f MAE=%.4f (log) | RMSE=%.1f MAE=%.1f (cases)",
        label, rmse, mae, rmse_cases, mae_cases,
    )
    return result


# ── Naive seasonal baseline ───────────────────────────────────────────────────

def naive_seasonal_predict(train: pd.DataFrame, eval_df: pd.DataFrame) -> np.ndarray:
    """
    Predict using the same epiweek's mean from the training set.
    (Last-year-same-week baseline — standard for seasonal disease forecasting.)
    """
    week_mean = (
        train.groupby("epiweek")["target_log_cases"].mean().to_dict()
    )
    preds = eval_df["epiweek"].map(week_mean).values
    # Fill any unseen epiweeks with the global training mean
    global_mean = train["target_log_cases"].mean()
    preds = np.where(np.isnan(preds), global_mean, preds)
    return preds


# ── ARIMA baseline ────────────────────────────────────────────────────────────

def arima_predict(train: pd.DataFrame, eval_df: pd.DataFrame) -> np.ndarray:
    """One-step-ahead ARIMA forecast on the log-cases series."""
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ImportError:
        logger.warning("statsmodels not available; skipping ARIMA baseline")
        return np.full(len(eval_df), np.nan)

    series = train["target_log_cases"].values
    preds  = []
    history = list(series)

    for _ in range(len(eval_df)):
        try:
            model = ARIMA(history, order=(2, 1, 2))
            fit   = model.fit()
            pred  = fit.forecast(steps=1)[0]
        except Exception:
            pred = np.mean(history[-4:])  # fallback: 4-week mean
        preds.append(pred)
        # In a real rolling forecast we'd append the true value; here we append
        # the prediction to keep it fully forward-looking (no test leakage)
        history.append(pred)

    return np.array(preds)


# ── XGBoost training ──────────────────────────────────────────────────────────

def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> XGBRegressor:
    model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        early_stopping_rounds=50,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    logger.info("XGBoost trained. Best iteration: %d", model.best_iteration)
    return model


# ── Feature importance ────────────────────────────────────────────────────────

def top_features(model: XGBRegressor, feature_names: list[str], n: int = 10) -> list[dict]:
    importances = model.feature_importances_
    ranked = sorted(
        zip(feature_names, importances),
        key=lambda x: x[1],
        reverse=True,
    )
    return [{"feature": f, "importance": round(float(i), 4)} for f, i in ranked[:n]]


# ── Risk thresholds ───────────────────────────────────────────────────────────

def compute_thresholds(train_preds: np.ndarray) -> dict:
    """
    Define LOW / MEDIUM / HIGH thresholds from training-set predictions.
    Thresholds are the 33rd and 67th percentiles (tertiles).
    """
    p33 = float(np.percentile(train_preds, 33))
    p67 = float(np.percentile(train_preds, 67))
    return {"low_max": round(p33, 4), "medium_max": round(p67, 4)}


# ── Main ──────────────────────────────────────────────────────────────────────

def run_training(force: bool = False) -> dict:
    """
    Full training pipeline. Returns a results summary dict.
    Saves model + metadata to models/ if training completes successfully.
    """
    MODELS_DIR.mkdir(exist_ok=True)

    if MODEL_PATH.exists() and not force:
        logger.info("Model already exists at %s. Pass --force to retrain.", MODEL_PATH)
        with open(META_PATH) as f:
            return json.load(f)

    logger.info("Building feature matrix…")
    df = build_features()
    feat_cols = get_feature_columns(df)

    train_df, val_df, test_df = temporal_split(df)

    X_train = train_df[feat_cols]
    y_train = train_df["target_log_cases"]
    X_val   = val_df[feat_cols]
    y_val   = val_df["target_log_cases"]
    X_test  = test_df[feat_cols]
    y_test  = test_df["target_log_cases"]

    # ── Train XGBoost ────────────────────────────────────────────────────────
    logger.info("Training XGBoost…")
    model = train_xgboost(X_train, y_train, X_val, y_val)

    # ── Evaluate ─────────────────────────────────────────────────────────────
    xgb_val_metrics  = _metrics(y_val.values,  model.predict(X_val),  "XGB-val")
    xgb_test_metrics = _metrics(y_test.values, model.predict(X_test), "XGB-test")

    naive_val  = naive_seasonal_predict(train_df, val_df)
    naive_test = naive_seasonal_predict(train_df, test_df)
    naive_val_metrics  = _metrics(y_val.values,  naive_val,  "Naive-val")
    naive_test_metrics = _metrics(y_test.values, naive_test, "Naive-test")

    logger.info("Fitting ARIMA baseline (this may take a minute)…")
    arima_test = arima_predict(train_df, test_df)
    arima_test_metrics = _metrics(y_test.values, arima_test, "ARIMA-test")

    # ── Risk thresholds (from training-set predictions) ──────────────────────
    train_preds = model.predict(X_train)
    thresholds  = compute_thresholds(train_preds)

    # ── Save ─────────────────────────────────────────────────────────────────
    joblib.dump(model, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)

    meta = {
        "feature_columns": feat_cols,
        "train_date_range": [
            str(train_df["week_start"].min().date()),
            str(train_df["week_start"].max().date()),
        ],
        "val_date_range": [
            str(val_df["week_start"].min().date()),
            str(val_df["week_start"].max().date()),
        ],
        "test_date_range": [
            str(test_df["week_start"].min().date()),
            str(test_df["week_start"].max().date()),
        ],
        "risk_thresholds": thresholds,
        "top_features": top_features(model, feat_cols),
        "metrics": {
            "xgb_val":    xgb_val_metrics,
            "xgb_test":   xgb_test_metrics,
            "naive_val":  naive_val_metrics,
            "naive_test": naive_test_metrics,
            "arima_test": arima_test_metrics,
        },
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Metadata saved to %s", META_PATH)

    return meta


def print_report(meta: dict) -> None:
    print("\n" + "=" * 60)
    print("Dengue Risk Model — Training Report")
    print("=" * 60)

    metrics = meta["metrics"]
    rows = [
        ("XGBoost",       metrics["xgb_test"]),
        ("Naive seasonal",metrics["naive_test"]),
        ("ARIMA",         metrics["arima_test"]),
    ]
    print(f"\n{'Model':<20} {'RMSE (log)':<14} {'MAE (log)':<13} {'RMSE (cases)':<16} {'MAE (cases)'}")
    print("-" * 72)
    for name, m in rows:
        print(
            f"{name:<20} {m['rmse_log']:<14} {m['mae_log']:<13}"
            f" {m['rmse_cases']:<16} {m['mae_cases']}"
        )

    print("\nTop features by importance:")
    for item in meta["top_features"]:
        bar = "#" * int(item["importance"] * 100)
        print(f"  {item['feature']:<30} {bar} {item['importance']:.4f}")

    print(f"\nRisk thresholds (log scale):")
    print(f"  LOW    : predicted <= {meta['risk_thresholds']['low_max']}")
    print(f"  MEDIUM : predicted <= {meta['risk_thresholds']['medium_max']}")
    print(f"  HIGH   : predicted >  {meta['risk_thresholds']['medium_max']}")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Retrain even if model exists")
    args = parser.parse_args()

    meta = run_training(force=args.force)
    print_report(meta)
