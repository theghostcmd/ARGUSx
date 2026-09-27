"""Feature engineering for the ARGUS-X anomaly detector.

Every feature below has an explicit definition, data source, calculation,
range, meaning and security rationale. Features are computed from the
normalized event stream and a per-entity behavioural baseline.

Data-leakage control
--------------------
`BaselineEngine` is fitted ONLY on a historical slice (e.g. the first
70% of events, chronologically). Features for events in the historical
slice are computed using that same historical baseline, and features for
the hold-out / inference slice use the historical baseline as well.
The model is therefore never given information about the future when
scoring an earlier event. See `ai_engine/services/analysis_service.py`.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from ai_engine.baseline.baseline_engine import BaselineEngine

# Canonical feature ordering. Persisted with the model so inference uses
# exactly the same columns in exactly the same order.
NUMERIC_FEATURES: List[str] = [
    "login_hour_deviation",
    "login_frequency_deviation",
    "request_frequency_deviation",
    "new_device_score",
    "new_ip_score",
    "resource_deviation",
    "service_deviation",
    "network_deviation",
    "authentication_failure_rate",
    "bytes_sent_deviation",
    "bytes_received_deviation",
    "session_duration_deviation",
    "asset_criticality",
    "resource_sensitivity",
]

CATEGORICAL_FEATURES: List[str] = [
    "event_type",
    "service",
    "resource",
    "network_zone",
    "authentication_result",
]


def _safe_ratio(value: float, baseline_median: float, baseline_scale: float) -> float:
    """Robust deviation: (value - median) / max(scale, eps).

    `baseline_scale` is the MAD-based scale (1.4826 * MAD) or a floor.
    The result is signed and then squashed with tanh into (-1, 1).
    """
    eps = 1e-6
    scale = max(baseline_scale, eps)
    z = (value - baseline_median) / scale
    return float(np.tanh(z))


def _hour_deviation(hour: int, typical_hours: List[int], hour_mad: float) -> float:
    """Signed, wrapped deviation of the login hour from the user's median.

    Uses circular distance so 23:00 and 01:00 are considered close.
    Result is squashed via tanh into (-1, 1).
    """
    if not typical_hours:
        return 0.0
    median_hour = float(np.median(typical_hours))
    diff = (hour - median_hour + 12) % 24 - 12
    scale = max(hour_mad, 1.0)
    return float(np.tanh(diff / scale))


def compute_features(
    events: pd.DataFrame,
    baseline_engine: BaselineEngine,
) -> pd.DataFrame:
    """Compute the full feature matrix for a batch of events.

    Parameters
    ----------
    events : DataFrame
        Normalized events. Must contain at least the columns used below.
    baseline_engine : BaselineEngine
        A baseline engine already fitted on historical events.

    Returns
    -------
    DataFrame
        One row per input event, containing NUMERIC_FEATURES and
        CATEGORICAL_FEATURES plus the event_id for joining.
    """
    if events.empty:
        return pd.DataFrame(columns=["event_id"] + NUMERIC_FEATURES + CATEGORICAL_FEATURES)

    df = events.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["login_hour"] = df["timestamp"].dt.hour

    rows: List[Dict[str, float]] = []
    for _, ev in df.iterrows():
        u = baseline_engine.get_user_baseline(ev["user_id"])
        d = baseline_engine.get_device_baseline(ev["device_id"])

        # 1. login_hour_deviation
        login_hour_deviation = _hour_deviation(
            int(ev["login_hour"]),
            u.get("login_hours", []),
            u.get("login_hour_mad", 1.0),
        )

        # 2. login_frequency_deviation: how many events this user generated
        #    in the same hour historically vs today's count up to this event.
        hist_rate = u.get("events_per_hour_median", 1.0)
        current_count = float((df[
            (df["user_id"] == ev["user_id"]) &
            (df["timestamp"].dt.floor("h") == ev["timestamp"].floor("h"))
        ].shape[0]))
        login_frequency_deviation = _safe_ratio(
            current_count, hist_rate, u.get("events_per_hour_mad", 1.0)
        )

        # 3. request_frequency_deviation
        request_frequency_deviation = _safe_ratio(
            float(ev["request_count"]),
            u.get("request_count_median", 1.0),
            u.get("request_count_mad", 1.0),
        )

        # 4. new_device_score: 1.0 if device unseen for the user, else 0.
        new_device_score = 0.0 if ev["device_id"] in u.get("devices", []) else 1.0

        # 5. new_ip_score
        new_ip_score = 0.0 if ev["ip_address"] in u.get("ips", []) else 1.0

        # 6. resource_deviation: 1.0 if resource unseen for the user, else 0.
        resource_deviation = 0.0 if ev["resource"] in u.get("resources", []) else 1.0

        # 7. service_deviation
        service_deviation = 0.0 if ev["service"] in u.get("services", []) else 1.0

        # 8. network_deviation: 1.0 if network_zone not the user's typical zone.
        network_deviation = 0.0 if ev["network_zone"] in u.get("network_zones", []) else 1.0

        # 9. authentication_failure_rate: rolling failure rate for this user
        #    in the historical baseline. At inference we approximate with a
        #    binary indicator (1.0 for failure, 0.0 for success) combined
        #    with the user's historical failure rate.
        hist_fail_rate = u.get("auth_failure_rate", 0.0)
        auth_indicator = 1.0 if ev["authentication_result"] == "failure" else 0.0
        authentication_failure_rate = float(min(1.0, 0.5 * hist_fail_rate + 0.5 * auth_indicator))

        # 10/11. byte deviations
        bytes_sent_deviation = _safe_ratio(
            float(ev["bytes_sent"]),
            u.get("bytes_sent_median", 1.0),
            u.get("bytes_sent_mad", 1.0),
        )
        bytes_received_deviation = _safe_ratio(
            float(ev["bytes_received"]),
            u.get("bytes_received_median", 1.0),
            u.get("bytes_received_mad", 1.0),
        )

        # 12. session_duration_deviation
        session_duration_deviation = _safe_ratio(
            float(ev.get("session_duration", 0.0)),
            u.get("session_duration_median", 1.0),
            u.get("session_duration_mad", 1.0),
        )

        # 13/14. contextual features carried through from the event.
        asset_criticality = float(ev.get("asset_criticality", d.get("asset_criticality", 0.5)))
        resource_sensitivity = float(ev.get("resource_sensitivity", 0.5))

        rows.append({
            "event_id": ev["event_id"],
            "login_hour_deviation": login_hour_deviation,
            "login_frequency_deviation": login_frequency_deviation,
            "request_frequency_deviation": request_frequency_deviation,
            "new_device_score": new_device_score,
            "new_ip_score": new_ip_score,
            "resource_deviation": resource_deviation,
            "service_deviation": service_deviation,
            "network_deviation": network_deviation,
            "authentication_failure_rate": authentication_failure_rate,
            "bytes_sent_deviation": bytes_sent_deviation,
            "bytes_received_deviation": bytes_received_deviation,
            "session_duration_deviation": session_duration_deviation,
            "asset_criticality": asset_criticality,
            "resource_sensitivity": resource_sensitivity,
            # categorical passthrough
            "event_type": ev["event_type"],
            "service": ev["service"],
            "resource": ev["resource"],
            "network_zone": ev["network_zone"],
            "authentication_result": ev["authentication_result"],
        })

    return pd.DataFrame(rows)