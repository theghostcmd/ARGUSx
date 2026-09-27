"""High-level analysis service.

This is the Python-facing contract that the ARGUS-X backend can call
directly (without HTTP) as well as the engine used by the FastAPI layer.

Pipeline per event:
    validate -> clean -> features -> anomaly -> correlation (batch) ->
    risk -> explanation
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

from ai_engine.baseline.baseline_engine import BaselineEngine
from ai_engine.correlation.correlation_engine import CorrelationEngine
from ai_engine.explanation.explanation_service import ExplanationService
from ai_engine.features.engineering import NUMERIC_FEATURES, compute_features
from ai_engine.models.anomaly_detector import AnomalyDetector
from ai_engine.risk.risk_engine import RiskEngine
from ai_engine.utils.security import validate_event


class InvalidEventError(ValueError):
    pass


class FeatureEngineeringError(RuntimeError):
    pass


class AnalysisService:
    def __init__(
        self,
        baseline_engine: BaselineEngine,
        detector: AnomalyDetector,
        risk_engine: RiskEngine,
        explanation_service: ExplanationService | None = None,
        correlation_engine: CorrelationEngine | None = None,
    ) -> None:
        self.baseline_engine = baseline_engine
        self.detector = detector
        self.risk_engine = risk_engine
        self.explanation = explanation_service or ExplanationService()
        self.correlation = correlation_engine or CorrelationEngine()

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _to_frame(event: Dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame([event])

    def _analyze_single(
        self,
        event: Dict[str, Any],
        correlation_score: float,
    ) -> Dict[str, Any]:
        df = self._to_frame(event)
        try:
            features_df = compute_features(df, self.baseline_engine)
        except Exception as exc:  # noqa: BLE001
            raise FeatureEngineeringError(f"Feature engineering failed: {exc}") from exc
        if features_df.empty:
            raise FeatureEngineeringError("Feature engineering produced no rows")

        scores = self.detector.score(features_df)
        labels = self.detector.predict(features_df)
        anomaly_score = float(scores[0])
        anomaly_label = bool(labels[0])

        features = features_df.iloc[0].to_dict()
        baseline = self.baseline_engine.get_user_baseline(event["user_id"])

        risk_result = self.risk_engine.score(
            anomaly_score=anomaly_score,
            asset_criticality=float(features.get("asset_criticality", 0.5)),
            resource_sensitivity=float(features.get("resource_sensitivity", 0.5)),
            correlation_score=correlation_score,
            network_deviation=float(features.get("network_deviation", 0.0)),
            context={
                "new_device": features.get("new_device_score", 0.0) >= 1.0,
                "new_ip": features.get("new_ip_score", 0.0) >= 1.0,
                "resource_sensitivity": features.get("resource_sensitivity", 0.0),
                "authentication_failure": features.get("authentication_failure_rate", 0.0),
            },
        )

        anomaly_payload = {
            "score": anomaly_score,
            "label": anomaly_label,
            "model_version": self.detector.model_version,
        }
        risk_payload = risk_result.to_dict()
        baseline_payload = {
            "median_login_hour": baseline.get("login_hour_median"),
            "typical_devices": baseline.get("devices", []),
            "typical_ips": baseline.get("ips", []),
            "typical_services": baseline.get("services", []),
            "typical_resources": baseline.get("resources", []),
            "auth_failure_rate": baseline.get("auth_failure_rate"),
        }

        explanation = self.explanation.explain(
            event=event,
            features=features,
            anomaly=anomaly_payload,
            risk=risk_payload,
            baseline=baseline_payload,
        )

        return {
            "event_id": event["event_id"],
            "event": event,
            "features": {k: features[k] for k in NUMERIC_FEATURES if k in features},
            "anomaly": anomaly_payload,
            "risk": risk_payload,
            "explanation": explanation,
            "model": {"version": self.detector.model_version},
        }

    # ---------------------------------------------------------------- public
    def analyze_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        validate_event(event)
        return self._analyze_single(event, correlation_score=0.0)

    def analyze_batch(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        for ev in events:
            validate_event(ev)
        if not events:
            return {"events": [], "incidents": []}
        df = pd.DataFrame(events)
        try:
            features_df = compute_features(df, self.baseline_engine)
        except Exception as exc:  # noqa: BLE001
            raise FeatureEngineeringError(f"Feature engineering failed: {exc}") from exc

        scores = self.detector.score(features_df)
        labels = self.detector.predict(features_df)

        anomalies = {
            eid: float(s)
            for eid, s in zip(features_df["event_id"].tolist(), scores.tolist())
        }
        incidents = self.correlation.correlate(df, anomalies)
        # Map each event to its incident's correlation score.
        event_to_incident: Dict[str, Any] = {}
        for inc in incidents:
            for eid in inc.related_event_ids:
                event_to_incident[eid] = inc

        results = []
        for i, ev in enumerate(events):
            inc = event_to_incident.get(ev["event_id"])
            corr_score = inc.correlation_score if inc else 0.0
            results.append(self._analyze_single(ev, correlation_score=corr_score))

        return {
            "events": results,
            "incidents": [inc.to_dict() for inc in incidents],
        }