"""Preprocessing pipeline persisted alongside the Isolation Forest model.

The same ColumnTransformer used at training time is reused at inference.
Numeric columns are passed through (they are already bounded by tanh or
in [0, 1]); categorical columns are one-hot encoded with
handle_unknown='ignore' so unseen categories at inference do not crash.
"""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ai_engine.features.engineering import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def build_pipeline(estimator) -> Pipeline:
    return Pipeline([("preprocessor", build_preprocessor()), ("model", estimator)])