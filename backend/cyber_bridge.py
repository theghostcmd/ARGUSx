"""
Bridge backend event shape → cyber.cyber_module.
Member 1 ka module as-is import hota hai.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CYBER_DIR = PROJECT_ROOT / "cyber"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cyber.cyber_module import SecurityEvent, ArgusXCyberModule  # noqa: E402

# Singleton — cyber module is stateful (keeps incident history)
_cyber = ArgusXCyberModule()


EVENT_TYPE_MAP = {
    "LOGIN_SUCCESS":     "LOGIN_SUCCESS",
    "LOGIN_FAILED":      "LOGIN_FAILURE",
    "AUTH_ANOMALY":      "UNAUTHORIZED_ACCESS",
    "NEW_DEVICE":        "CONFIG_CHANGE",
    "NETWORK_ANOMALY":   "PORT_SCAN",
    "RESOURCE_ACCESS":   "DATA_EXFILTRATION",
}

DEFAULT_SEVERITY = {
    "LOGIN_SUCCESS":     "LOW",
    "LOGIN_FAILED":      "MEDIUM",
    "AUTH_ANOMALY":      "HIGH",
    "NEW_DEVICE":        "MEDIUM",
    "NETWORK_ANOMALY":   "HIGH",
    "RESOURCE_ACCESS":   "HIGH",
}


def get_cyber_module() -> ArgusXCyberModule:
    return _cyber


def to_security_event(backend_event: dict) -> SecurityEvent:
    et = backend_event["event_type"].upper()
    cyber_type = EVENT_TYPE_MAP.get(et, "LOGIN_FAILURE")
    severity = DEFAULT_SEVERITY.get(et, "MEDIUM")

    resource = backend_event.get("resource", "")
    if "Database" in resource or "Server" in resource:
        severity = "CRITICAL"

    return SecurityEvent(
        event_type = cyber_type,
        source     = backend_event.get("ip_address", "unknown"),
        asset_id   = backend_event["device_id"],
        severity   = severity,
        user       = backend_event.get("user_id", "unknown"),
        timestamp  = backend_event.get("timestamp"),
        details    = {
            "event_id": backend_event.get("event_id"),
            "device_id": backend_event["device_id"],
            "ip_address": backend_event.get("ip_address"),
            "service": backend_event.get("service"),
            "resource": backend_event.get("resource"),
            "original_event_type": et,
        },
    )


def analyze_event(backend_event: dict) -> dict:
    sec_event = to_security_event(backend_event)
    result = _cyber.process_event(sec_event)
    if result.get("incident") is not None:
        inc = result["incident"]
        result["incident"] = {
            "incident_id": inc.incident_id,
            "title":       inc.title,
            "severity":    inc.severity,
            "risk_score":  inc.risk_score,
            "asset_id":    inc.asset_id,
            "status":      inc.status,
            "reason":      inc.reason,
            "events": [
                {
                    "event_type": e.event_type,
                    "asset_id":   e.asset_id,
                    "severity":   e.severity,
                    "user":       e.user,
                    "timestamp":  e.timestamp,
                }
                for e in inc.events
            ],
        }
    return result