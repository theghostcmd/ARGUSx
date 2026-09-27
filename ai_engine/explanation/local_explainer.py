"""Deterministic, data-driven explanation provider.

Generates a human-readable summary from the actual numeric evidence
produced by the feature, baseline, anomaly and risk layers. No text is
hardcoded to a specific example.
"""
from __future__ import annotations

from typing import Any, Dict, List


class LocalExplanationProvider:
    name = "local"

    def explain(
        self,
        event: Dict[str, Any],
        features: Dict[str, float],
        anomaly: Dict[str, Any],
        risk: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence: List[Dict[str, Any]] = []

        hour_dev = features.get("login_hour_deviation", 0.0)
        if abs(hour_dev) > 0.4:
            evidence.append({
                "type": "login_hour",
                "value": features.get("login_hour_raw", hour_dev),
                "deviation": round(hour_dev, 3),
                "message": (
                    f"Login hour deviates from the user's historical pattern "
                    f"(deviation score {hour_dev:.2f})."
                ),
            })

        if features.get("new_device_score", 0) >= 1.0:
            evidence.append({
                "type": "new_device",
                "value": event.get("device_id"),
                "deviation": 1.0,
                "message": f"Device {event.get('device_id')} has not been seen for this user.",
            })
        if features.get("new_ip_score", 0) >= 1.0:
            evidence.append({
                "type": "new_ip",
                "value": event.get("ip_address"),
                "deviation": 1.0,
                "message": f"IP {event.get('ip_address')} has not been seen for this user.",
            })
        if features.get("resource_deviation", 0) >= 1.0:
            evidence.append({
                "type": "resource",
                "value": event.get("resource"),
                "deviation": 1.0,
                "message": f"Resource {event.get('resource')} is not part of the user's normal set.",
            })
        if features.get("service_deviation", 0) >= 1.0:
            evidence.append({
                "type": "service",
                "value": event.get("service"),
                "deviation": 1.0,
                "message": f"Service {event.get('service')} is not part of the user's normal set.",
            })
        if features.get("network_deviation", 0) >= 1.0:
            evidence.append({
                "type": "network",
                "value": event.get("network_zone"),
                "deviation": 1.0,
                "message": f"Network zone {event.get('network_zone')} is not part of the user's normal zones.",
            })
        if features.get("request_frequency_deviation", 0.0) > 0.5:
            evidence.append({
                "type": "request_rate",
                "value": event.get("request_count"),
                "deviation": round(features["request_frequency_deviation"], 3),
                "message": (
                    f"Request count {event.get('request_count')} deviates from the user's baseline "
                    f"(deviation score {features['request_frequency_deviation']:.2f})."
                ),
            })
        if features.get("authentication_failure_rate", 0.0) > 0.5:
            evidence.append({
                "type": "authentication",
                "value": event.get("authentication_result"),
                "deviation": round(features["authentication_failure_rate"], 3),
                "message": "Authentication result indicates a failure.",
            })

        parts = [
            f"Event {event.get('event_id')} from user {event.get('user_id')} "
            f"on device {event.get('device_id')} at {event.get('timestamp')}."
        ]
        if evidence:
            parts.append(
                f"The engine identified {len(evidence)} contributing deviation(s)."
            )
        parts.append(
            f"Anomaly score {anomaly.get('score', 0.0):.2f} "
            f"(label={anomaly.get('label')})."
        )
        parts.append(
            f"Risk score {risk.get('score', 0.0):.2f} classified as '{risk.get('level')}'."
        )

        limitations = (
            "This explanation is derived from statistical deviation, not from "
            "confirmed malicious activity. An anomaly is not a threat. "
            "False positives are expected; validate with additional context "
            "before acting."
        )
        return {
            "provider": self.name,
            "summary": " ".join(parts),
            "evidence": evidence,
            "limitations": limitations,
        }