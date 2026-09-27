"""Explanation service with graceful LLM fallback."""
from __future__ import annotations

from typing import Any, Dict

from ai_engine.config.settings import get_settings
from ai_engine.explanation.llm_explainer import LLMExplanationProvider
from ai_engine.explanation.local_explainer import LocalExplanationProvider
from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


class ExplanationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.local = LocalExplanationProvider()
        self.llm = None
        if self.settings.enable_llm_explanation:
            try:
                self.llm = LLMExplanationProvider(
                    api_key=self.settings.llm_api_key,
                    base_url=self.settings.llm_base_url,
                    model=self.settings.llm_model,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM provider disabled: %s", exc)
                self.llm = None

    def explain(
        self,
        event: Dict[str, Any],
        features: Dict[str, float],
        anomaly: Dict[str, Any],
        risk: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.llm is not None:
            try:
                return self.llm.explain(event, features, anomaly, risk, baseline)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM explanation failed, falling back to local: %s", exc)
        return self.local.explain(event, features, anomaly, risk, baseline)