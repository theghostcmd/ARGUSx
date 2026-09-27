"""Evaluation entry point.

Because anomaly detection is typically unsupervised, accuracy is a
misleading metric. We therefore report:

- If `is_anomaly_injected` is present (synthetic labels): precision,
  recall, F1, confusion matrix, ROC-AUC and PR-AUC.
- If labels are absent: anomaly rate, score distribution statistics and
  baseline deviation statistics.

Limitations of unsupervised evaluation:
- Labels (when present) may be incomplete or noisy.
- A model with high recall can still be operationally useless if the
  anomaly rate is very low and precision is poor.
- Concept drift means today's evaluation is not tomorrow's.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ai_engine.baseline.baseline_engine import BaselineEngine
from ai_engine.config.settings import get_settings
from ai_engine.features.engineering import compute_features
from ai_engine.models.anomaly_detector import AnomalyDetector
from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


def evaluate(
    dataset_path: str = "ai_engine/data/raw/events.csv",
    historical_fraction: float = 0.6,
    report_dir: str = "reports",
) -> dict:
    settings = get_settings()
    df = pd.read_csv(dataset_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    split_idx = int(len(df) * historical_fraction)
    historical = df.iloc[:split_idx].reset_index(drop=True)
    evaluation = df.iloc[split_idx:].reset_index(drop=True)

    baseline = BaselineEngine().fit(historical)
    features = compute_features(evaluation, baseline)

    detector = AnomalyDetector.load(settings.model_path)
    scores = detector.score(features)
    labels = detector.predict(features)

    report: dict = {
        "model_version": detector.model_version,
        "evaluated_events": int(len(evaluation)),
        "anomaly_rate": float(labels.mean()),
        "score_mean": float(np.mean(scores)),
        "score_std": float(np.std(scores)),
        "score_min": float(np.min(scores)),
        "score_max": float(np.max(scores)),
    }

    if "is_anomaly_injected" in evaluation.columns:
        y_true = evaluation["is_anomaly_injected"].astype(int).values
        y_pred = labels.astype(int)
        report.update({
            "labeled": True,
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        })
        if len(np.unique(y_true)) > 1:
            report["roc_auc"] = float(roc_auc_score(y_true, scores))
            report["pr_auc"] = float(average_precision_score(y_true, scores))
    else:
        report["labeled"] = False
        report["note"] = (
            "No labels available; only unsupervised diagnostics reported. "
            "Precision/recall cannot be computed without labels."
        )

    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation.json").write_text(json.dumps(report, indent=2))

    # Score distribution plot
    plt.figure(figsize=(7, 4))
    sns.histplot(scores, bins=30, kde=True)
    plt.title("Anomaly score distribution")
    plt.xlabel("anomaly_score")
    plt.tight_layout()
    plt.savefig(out_dir / "score_distribution.png")
    plt.close()

    logger.info("Evaluation report written to %s", out_dir / "evaluation.json")
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))