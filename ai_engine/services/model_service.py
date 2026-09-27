"""Model service: loads model, baseline and risk engine once at startup."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from ai_engine.baseline.baseline_engine import BaselineEngine
from ai_engine.models.model_registry import get_registry
from ai_engine.risk.risk_engine import RiskEngine, load_risk_engine
from ai_engine.services.analysis_service import AnalysisService
from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


class ModelService:
    def __init__(self) -> None:
        self.registry = get_registry()
        self.baseline_engine: Optional[BaselineEngine] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.analysis_service: Optional[AnalysisService] = None

    def initialize(self, historical_events: pd.DataFrame | None = None) -> AnalysisService:
        detector = self.registry.get()
        self.risk_engine = load_risk_engine()

        if historical_events is None:
            # Load a default historical slice if present, otherwise an
            # empty baseline is used and all events look "new".
            try:
                historical_events = pd.read_csv("ai_engine/data/raw/events.csv")
            except FileNotFoundError:
                logger.warning("No historical events file found; baseline will be empty.")
                historical_events = pd.DataFrame()

        self.baseline_engine = BaselineEngine()
        if not historical_events.empty:
            self.baseline_engine.fit(historical_events)
            logger.info(
                "Baseline fitted on %d events across %d users.",
                len(historical_events),
                len(self.baseline_engine.user_baselines),
            )
        else:
            self.baseline_engine._fitted = True

        self.analysis_service = AnalysisService(
            baseline_engine=self.baseline_engine,
            detector=detector,
            risk_engine=self.risk_engine,
        )
        return self.analysis_service

    def reload(self) -> AnalysisService:
        self.registry.reload()
        return self.initialize()

    def get(self) -> AnalysisService:
        if self.analysis_service is None:
            return self.initialize()
        return self.analysis_service


_service = ModelService()


def get_model_service() -> ModelService:
    return _service