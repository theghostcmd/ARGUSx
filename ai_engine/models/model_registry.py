"""Thin model registry used by the API layer.

Loads the model once at startup; `reload()` re-reads from disk on demand.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ai_engine.config.settings import get_settings
from ai_engine.models.anomaly_detector import AnomalyDetector, ModelNotFoundError
from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._model: Optional[AnomalyDetector] = None
        self._metadata: Dict[str, Any] = {}

    def load(self) -> AnomalyDetector:
        self._model = AnomalyDetector.load(self._settings.model_path)
        meta_path: Path = self._settings.model_metadata_path
        if meta_path.exists():
            self._metadata = json.loads(meta_path.read_text())
        else:
            self._metadata = {"model_version": self._model.model_version}
        logger.info(
            "Loaded model version=%s from %s",
            self._model.model_version,
            self._settings.model_path,
        )
        return self._model

    def get(self) -> AnomalyDetector:
        if self._model is None:
            return self.load()
        return self._model

    def metadata(self) -> Dict[str, Any]:
        if not self._metadata:
            self.get()
        return self._metadata

    def reload(self) -> AnomalyDetector:
        logger.info("Reloading model from %s", self._settings.model_path)
        return self.load()


_registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    return _registry