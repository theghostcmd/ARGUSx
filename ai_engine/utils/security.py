"""Input validation and secret redaction helpers."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any, Dict

REQUIRED_FIELDS = [
    "event_id",
    "timestamp",
    "user_id",
    "device_id",
    "ip_address",
    "event_type",
    "service",
    "resource",
    "request_count",
    "bytes_sent",
    "bytes_received",
    "authentication_result",
    "asset_criticality",
    "resource_sensitivity",
    "network_zone",
    "source_country",
    "destination",
    "session_id",
]

SENSITIVE_KEYS = {"password", "token", "api_key", "secret", "authorization"}


class InvalidEventError(ValueError):
    pass


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidEventError(f"Invalid timestamp: {value!r}") from exc
    else:
        raise InvalidEventError(f"Invalid timestamp type: {type(value)!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a single event in place (returns a copy)."""
    if not isinstance(event, dict):
        raise InvalidEventError("Event must be a dict")

    missing = [f for f in REQUIRED_FIELDS if f not in event]
    if missing:
        raise InvalidEventError(f"Missing required fields: {missing}")

    ev = dict(event)

    dt = _parse_timestamp(ev["timestamp"])
    ev["timestamp"] = dt.isoformat()

    for int_field in ("request_count", "bytes_sent", "bytes_received"):
        try:
            val = int(ev[int_field])
        except (TypeError, ValueError) as exc:
            raise InvalidEventError(f"{int_field} must be an integer") from exc
        if val < 0:
            raise InvalidEventError(f"{int_field} must be non-negative")
        ev[int_field] = val

    for float_field in ("asset_criticality", "resource_sensitivity"):
        try:
            val = float(ev[float_field])
        except (TypeError, ValueError) as exc:
            raise InvalidEventError(f"{float_field} must be a number") from exc
        if not (0.0 <= val <= 1.0):
            raise InvalidEventError(f"{float_field} must be in [0, 1]")
        ev[float_field] = val

    try:
        ipaddress.ip_address(str(ev["ip_address"]))
    except ValueError as exc:
        raise InvalidEventError(f"Invalid IP address: {ev['ip_address']!r}") from exc

    if ev["authentication_result"] not in {"success", "failure"}:
        raise InvalidEventError("authentication_result must be 'success' or 'failure'")

    return ev


def redact_secrets(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in payload.items():
        if k.lower() in SENSITIVE_KEYS:
            out[k] = "***redacted***"
        elif isinstance(v, dict):
            out[k] = redact_secrets(v)
        else:
            out[k] = v
    return out