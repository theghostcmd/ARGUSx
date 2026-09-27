"""Behavioural baseline engine.

For every user and every device we compute robust statistics
(median + MAD-based scale) plus the sets of habits observed in the
historical slice. All statistics are derived from data — none are
hardcoded.

Baseline poisoning note
-----------------------
If an attacker can influence the historical slice used to fit the
baseline, they can shift the "normal" distribution. Production
deployments should fit baselines on vetted historical windows and
re-fit periodically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _mad_scale(series: pd.Series) -> float:
    """1.4826 * MAD — a robust estimate of standard deviation."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return 1.0
    med = s.median()
    mad = (s - med).abs().median()
    return float(max(1.4826 * mad, 1e-6))


@dataclass
class UserBaseline:
    user_id: str
    login_hours: List[int] = field(default_factory=list)
    login_hour_median: float = 0.0
    login_hour_mad: float = 1.0
    devices: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    network_zones: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=list)
    request_count_median: float = 1.0
    request_count_mad: float = 1.0
    bytes_sent_median: float = 1.0
    bytes_sent_mad: float = 1.0
    bytes_received_median: float = 1.0
    bytes_received_mad: float = 1.0
    session_duration_median: float = 1.0
    session_duration_mad: float = 1.0
    events_per_hour_median: float = 1.0
    events_per_hour_mad: float = 1.0
    auth_failure_rate: float = 0.0
    event_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class DeviceBaseline:
    device_id: str
    users: List[str] = field(default_factory=list)
    asset_criticality: float = 0.5
    event_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class BaselineNotFoundError(KeyError):
    """Raised when a baseline is requested for an unknown entity."""


class BaselineEngine:
    def __init__(self) -> None:
        self.user_baselines: Dict[str, UserBaseline] = {}
        self.device_baselines: Dict[str, DeviceBaseline] = {}
        self._fitted = False

    # ------------------------------------------------------------------ fit
    def fit(self, events: pd.DataFrame) -> "BaselineEngine":
        if events.empty:
            raise ValueError("Cannot fit baseline on empty events")

        df = events.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["login_hour"] = df["timestamp"].dt.hour

        for uid, grp in df.groupby("user_id"):
            self.user_baselines[uid] = self._build_user_baseline(uid, grp)
        for did, grp in df.groupby("device_id"):
            self.device_baselines[did] = DeviceBaseline(
                device_id=did,
                users=sorted(grp["user_id"].unique().tolist()),
                asset_criticality=float(grp["asset_criticality"].median()),
                event_count=int(len(grp)),
            )
        self._fitted = True
        return self

    @staticmethod
    def _build_user_baseline(user_id: str, grp: pd.DataFrame) -> UserBaseline:
        hours = grp["login_hour"].tolist()
        hour_median = float(np.median(hours)) if hours else 0.0
        hour_mad = _mad_scale(pd.Series(hours))

        # events per hour
        grp = grp.copy()
        grp["hour_bucket"] = grp["timestamp"].dt.floor("h")
        per_hour = grp.groupby("hour_bucket").size()
        events_per_hour_median = float(per_hour.median()) if not per_hour.empty else 1.0
        events_per_hour_mad = _mad_scale(per_hour) if len(per_hour) > 1 else 1.0

        auth_failures = (grp["authentication_result"] == "failure").sum()
        auth_failure_rate = float(auth_failures / max(len(grp), 1))

        return UserBaseline(
            user_id=user_id,
            login_hours=hours,
            login_hour_median=hour_median,
            login_hour_mad=hour_mad,
            devices=sorted(grp["device_id"].unique().tolist()),
            ips=sorted(grp["ip_address"].unique().tolist()),
            services=sorted(grp["service"].unique().tolist()),
            resources=sorted(grp["resource"].unique().tolist()),
            network_zones=sorted(grp["network_zone"].unique().tolist()),
            countries=sorted(grp["source_country"].unique().tolist()),
            request_count_median=float(grp["request_count"].median()),
            request_count_mad=_mad_scale(grp["request_count"]),
            bytes_sent_median=float(grp["bytes_sent"].median()),
            bytes_sent_mad=_mad_scale(grp["bytes_sent"]),
            bytes_received_median=float(grp["bytes_received"].median()),
            bytes_received_mad=_mad_scale(grp["bytes_received"]),
            session_duration_median=float(grp.get("session_duration", pd.Series([1.0])).median()),
            session_duration_mad=_mad_scale(grp.get("session_duration", pd.Series([1.0]))),
            events_per_hour_median=events_per_hour_median,
            events_per_hour_mad=events_per_hour_mad,
            auth_failure_rate=auth_failure_rate,
            event_count=int(len(grp)),
        )

    # --------------------------------------------------------------- access
    def get_user_baseline(self, user_id: str) -> Dict[str, Any]:
        if not self._fitted:
            raise BaselineNotFoundError("BaselineEngine has not been fitted")
        if user_id not in self.user_baselines:
            # Unknown user: return a neutral baseline rather than crashing
            # the pipeline. The feature layer will emit maximum deviation
            # signals (new_device_score=1, new_ip_score=1, etc.).
            return {
                "login_hours": [],
                "login_hour_mad": 1.0,
                "devices": [],
                "ips": [],
                "services": [],
                "resources": [],
                "network_zones": [],
                "countries": [],
                "request_count_median": 1.0,
                "request_count_mad": 1.0,
                "bytes_sent_median": 1.0,
                "bytes_sent_mad": 1.0,
                "bytes_received_median": 1.0,
                "bytes_received_mad": 1.0,
                "session_duration_median": 1.0,
                "session_duration_mad": 1.0,
                "events_per_hour_median": 1.0,
                "events_per_hour_mad": 1.0,
                "auth_failure_rate": 0.0,
                "event_count": 0,
            }
        return self.user_baselines[user_id].to_dict()

    def get_device_baseline(self, device_id: str) -> Dict[str, Any]:
        if not self._fitted:
            raise BaselineNotFoundError("BaselineEngine has not been fitted")
        if device_id not in self.device_baselines:
            return {"asset_criticality": 0.5, "users": [], "event_count": 0}
        return self.device_baselines[device_id].to_dict()

    def calculate_deviation(self, event: Dict[str, Any]) -> Dict[str, float]:
        """Return a small dict of raw deviations for a single event.

        This is a lightweight, non-ML helper used by the explanation layer
        and by tests. The full feature matrix is built by
        `features.engineering.compute_features`.
        """
        u = self.get_user_baseline(event["user_id"])
        ts = pd.to_datetime(event["timestamp"], utc=True)
        hour = int(ts.hour)
        typical = u.get("login_hours", [])
        if typical:
            diff = (hour - float(np.median(typical)) + 12) % 24 - 12
            hour_dev = abs(diff)
        else:
            hour_dev = 0.0
        return {
            "hour_deviation": float(hour_dev),
            "new_device": 0.0 if event["device_id"] in u.get("devices", []) else 1.0,
            "new_ip": 0.0 if event["ip_address"] in u.get("ips", []) else 1.0,
            "resource_deviation": 0.0 if event["resource"] in u.get("resources", []) else 1.0,
            "service_deviation": 0.0 if event["service"] in u.get("services", []) else 1.0,
        }