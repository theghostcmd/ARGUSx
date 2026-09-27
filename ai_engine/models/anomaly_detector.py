"""Isolation Forest anomaly detector wrapper.

Score transformation
--------------------
IsolationForest exposes two relevant outputs:

- `decision_function(X)` -> values roughly in [-0.5, 0.5] where positive
  means "more normal" and negative means "more anomalous". The exact range
  depends on the contamination parameter and the fitted trees.
- `score_samples(X)` -> the raw anomaly score before thresholding.

We use `score_samples` and convert it to a calibrated [0, 1] score via a
monotone, data-driven transformation:

    raw = score_samples(X)                      # higher = more normal
    mu  = raw.mean()   (computed on training data, persisted)
    sd  = raw.std()    (computed on training data, persisted)
    z   = (mu - raw) / max(sd, eps)             # higher = more anomalous
    score = sigmoid(z)                          # maps R -> (0, 1)

The sigmoid is a smooth, strictly monotone squashing function, so the
ordering of anomalies is preserved while the output is bounded in (0,1).
The mean/std are persisted with the model so training and inference use
identical calibration. The 0/1 label comes from the model's own
`predict()` (which uses the fitted threshold), not from the sigmoid.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ai_engine.config.settings import get_settings
from ai_engine.features.engineering import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from ai_engine.features.preprocessing import build_pipeline


class ModelNotFoundError(FileNotFoundError):
    """Raised when a model artifact cannot be located or loaded."""


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class AnomalyDetector:
    def __init__(
        self,
        model_version: str = "1.0.0",
        contamination: float = 0.05,
        random_state: int = 42,
    ) -> None:
        self.model_version = model_version
        self.contamination = contamination
        self.random_state = random_state
        self.pipeline: Optional[Any] = None
        self._score_mu: float = 0.0
        self._score_sd: float = 1.0
        self._fitted = False

    # ------------------------------------------------------------------ fit
    def fit(self, X: pd.DataFrame) -> "AnomalyDetector":
        if X.empty:
            raise ValueError("Cannot fit anomaly detector on empty data")
        iso = IsolationForest(
            n_estimators=200,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.pipeline = build_pipeline(iso)
        self.pipeline.fit(X[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        raw = self.pipeline.named_steps["model"].score_samples(
            self.pipeline.named_steps["preprocessor"].transform(
                X[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
            )
        )
        self._score_mu = float(np.mean(raw))
        self._score_sd = float(max(np.std(raw), 1e-6))
        self._fitted = True
        return self

    # ------------------------------------------------------------- scoring
    def _raw_to_score(self, raw: np.ndarray) -> np.ndarray:
        z = (self._score_mu - raw) / self._score_sd
        return _sigmoid(z)

    def score(self, X: pd.DataFrame) -> np.ndarray:
        if not self._fitted or self.pipeline is None:
            raise ModelNotFoundError("AnomalyDetector has not been fitted")
        Xf = X[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        raw = self.pipeline.named_steps["model"].score_samples(
            self.pipeline.named_steps["preprocessor"].transform(Xf)
        )
        return self._raw_to_score(raw)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return boolean anomaly labels from the model's own threshold."""
        if not self._fitted or self.pipeline is None:
            raise ModelNotFoundError("AnomalyDetector has not been fitted")
        Xf = X[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        preds = self.pipeline.named_steps["model"].predict(
            self.pipeline.named_steps["preprocessor"].transform(Xf)
        )
        return preds == -1  # sklearn: -1 = outlier, 1 = inlier

    def score_batch(self, X: pd.DataFrame) -> List[Dict[str, Any]]:
        if X.empty:
            return []
        scores = self.score(X)
        labels = self.predict(X)
        out: List[Dict[str, Any]] = []
        for eid, s, l in zip(X["event_id"].tolist(), scores.tolist(), labels.tolist()):
            out.append({
                "event_id": eid,
                "anomaly_score": float(s),
                "anomaly_label": bool(l),
                "model_version": self.model_version,
            })
        return out

    # --------------------------------------------------------------- io
    def save(self, path: Path) -> None:
        if not self._fitted:
            raise ModelNotFoundError("Cannot save an unfitted model")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "model_version": self.model_version,
                "contamination": self.contamination,
                "random_state": self.random_state,
                "score_mu": self._score_mu,
                "score_sd": self._score_sd,
                "numeric_features": NUMERIC_FEATURES,
                "categorical_features": CATEGORICAL_FEATURES,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "AnomalyDetector":
        path = Path(path)
        if not path.exists():
            raise ModelNotFoundError(f"Model artifact not found: {path}")
        bundle = joblib.load(path)
        det = cls(
            model_version=bundle.get("model_version", "1.0.0"),
            contamination=bundle.get("contamination", 0.05),
            random_state=bundle.get("random_state", 42),
        )
        det.pipeline = bundle["pipeline"]
        det._score_mu = float(bundle["score_mu"])
        det._score_sd = float(bundle["score_sd"])
        det._fitted = True
        return det

    # ------------------------------------------------------------- metadata
    def write_metadata(self, path: Path, dataset_hash: str, n_samples: int) -> None:
        from datetime import datetime, timezone
        meta = {
            "model_version": self.model_version,
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "training_dataset_hash": dataset_hash,
            "feature_version": "1.0.0",
            "algorithm": "IsolationForest",
            "contamination": self.contamination,
            "random_state": self.random_state,
            "training_sample_count": int(n_samples),
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
            "score_mu": self._score_mu,
            "score_sd": self._score_sd,
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, indent=2))


def load_model(settings=None) -> AnomalyDetector:
    settings = settings or get_settings()
    return AnomalyDetector.load(settings.model_path)