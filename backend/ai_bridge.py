"""
Bridge backend event shape → ARGUS-X AI engine format.
Uses the AI engine's public AnalysisService directly (no HTTP).
"""
import sys, uuid
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.services.model_service import get_model_service  # noqa: E402
from ai_engine.models.anomaly_detector import ModelNotFoundError  # noqa: E402


_service_ready = False
_last_error: Optional[str] = None


def init_ai_engine():
    """Called once on backend startup."""
    global _service_ready, _last_error
    try:
        svc = get_model_service()
        svc.initialize()           # loads model + fits baseline from ai_engine/data/raw/events.csv
        _service_ready = True
        _last_error = None
    except ModelNotFoundError as e:
        _service_ready = False
        _last_error = f"Model not found: {e}. Run: python scripts/train_ai_model.py"
    except Exception as e:         # noqa: BLE001
        _service_ready = False
        _last_error = f"AI engine init failed: {e}"


def ai_status() -> dict:
    return {"ready": _service_ready, "error": _last_error}


# ----------------------------------------------------------------- adapter
def to_ai_event(backend_event: dict) -> dict:
    et = backend_event["event_type"].upper()
    auth = "failure" if ("FAIL" in et or "ANOMALY" in et) else "success"

    resource = backend_event.get("resource", "unknown")
    asset_crit = 0.9 if ("Database" in resource or "Server" in resource) else 0.5

    return {
        "event_id": str(backend_event.get("event_id") or uuid.uuid4()),
        "timestamp": backend_event["timestamp"],
        "user_id": backend_event["user_id"],
        "device_id": backend_event["device_id"],
        "ip_address": backend_event["ip_address"],
        "event_type": "access",
        "service": backend_event.get("service", "unknown"),
        "resource": resource,
        "request_count": 1,
        "bytes_sent": 1000,
        "bytes_received": 2000,
        "authentication_result": auth,
        "asset_criticality": asset_crit,
        "resource_sensitivity": asset_crit,
        "network_zone": "corp",
        "source_country": "US",
        "destination": resource,
        "session_id": str(uuid.uuid4()),
        "session_duration": 300,
    }


def analyze_event(backend_event: dict) -> dict:
    if not _service_ready:
        return {"error": _last_error or "AI engine not ready"}
    ai_event = to_ai_event(backend_event)
    svc = get_model_service()
    try:
        return svc.get().analyze_event(ai_event)
    except Exception as e:            # noqa: BLE001
        return {"error": f"AI analysis failed: {e}"}


def analyze_batch(backend_events: list) -> dict:
    if not _service_ready:
        return {"error": _last_error or "AI engine not ready"}
    ai_events = [to_ai_event(e) for e in backend_events]
    svc = get_model_service()
    try:
        return svc.get().analyze_batch(ai_events)
    except Exception as e:            # noqa: BLE001
        return {"error": f"AI batch analysis failed: {e}"}