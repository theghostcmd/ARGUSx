"""Training entry point.

Run with:
    python -m ai_engine.training.train

The script:
1. Loads (or generates) the synthetic dataset.
2. Splits it chronologically into a historical slice (for the baseline)
   and a training slice (for the Isolation Forest). This prevents the
   baseline from peeking at future events when scoring earlier ones.
3. Fits the BaselineEngine on the historical slice.
4. Computes features on the training slice using that baseline.
5. Fits the IsolationForest pipeline.
6. Persists the model, metadata and preprocessing pipeline.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from ai_engine.baseline.baseline_engine import BaselineEngine
from ai_engine.config.settings import get_settings
from ai_engine.data.generator import generate_dataset, save_dataset
from ai_engine.features.engineering import compute_features
from ai_engine.models.anomaly_detector import AnomalyDetector
from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


def _dataset_hash(df: pd.DataFrame) -> str:
    payload = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    return hashlib.sha256(payload).hexdigest()


def train(
    dataset_path: str | None = None,
    historical_fraction: float = 0.6,
) -> AnomalyDetector:
    settings = get_settings()
    path = Path(dataset_path) if dataset_path else Path("ai_engine/data/raw/events.csv")

    if path.exists():
        df = pd.read_csv(path)
        logger.info("Loaded dataset from %s (%d rows)", path, len(df))
    else:
        logger.info("No dataset at %s; generating a synthetic one.", path)
        df = generate_dataset()
        path.parent.mkdir(parents=True, exist_ok=True)
        save_dataset(df, str(path))

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    split_idx = int(len(df) * historical_fraction)
    historical = df.iloc[:split_idx].reset_index(drop=True)
    training = df.iloc[split_idx:].reset_index(drop=True)

    baseline = BaselineEngine().fit(historical)
    features = compute_features(training, baseline)

    detector = AnomalyDetector(
        model_version=settings.model_version,
        contamination=0.05,
        random_state=42,
    )
    detector.fit(features)
    detector.save(settings.model_path)
    detector.write_metadata(
        settings.model_metadata_path,
        dataset_hash=_dataset_hash(df),
        n_samples=len(training),
    )
    logger.info(
        "Trained model version=%s on %d samples; saved to %s",
        detector.model_version,
        len(training),
        settings.model_path,
    )
    return detector


if __name__ == "__main__":
    train()