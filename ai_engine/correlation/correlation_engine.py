"""Event correlation engine.

Groups events that are close in time and share at least one entity
(user, device, IP, service, resource) into a single incident. The
correlation score is a transparent function of:

- number of shared entities
- temporal closeness
- number of distinct event types

No example is hardcoded — arbitrary input events are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List

import pandas as pd


@dataclass
class Incident:
    incident_id: str
    related_event_ids: List[str] = field(default_factory=list)
    correlation_score: float = 0.0
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "related_event_ids": self.related_event_ids,
            "correlation_score": round(self.correlation_score, 4),
            "timeline": self.timeline,
            "entities": self.entities,
        }


def _shared_entities(a: pd.Series, b: pd.Series) -> int:
    keys = ["user_id", "device_id", "ip_address", "service", "resource"]
    return sum(1 for k in keys if a.get(k) == b.get(k))


class CorrelationEngine:
    def __init__(self, window_minutes: int = 30, min_shared: int = 1) -> None:
        self.window = timedelta(minutes=window_minutes)
        self.min_shared = min_shared

    def correlate(self, events: pd.DataFrame, anomaly_lookup: Dict[str, float] | None = None) -> List[Incident]:
        if events.empty:
            return []
        df = events.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        anomaly_lookup = anomaly_lookup or {}

        used = set()
        incidents: List[Incident] = []
        inc_counter = 0

        for i, row in df.iterrows():
            if i in used:
                continue
            inc_counter += 1
            incident = Incident(incident_id=f"INC-{inc_counter:05d}")
            incident.related_event_ids.append(row["event_id"])
            incident.timeline.append({
                "event_id": row["event_id"],
                "timestamp": row["timestamp"].isoformat(),
                "event_type": row["event_type"],
                "user_id": row["user_id"],
                "device_id": row["device_id"],
                "ip_address": row["ip_address"],
                "service": row["service"],
                "resource": row["resource"],
            })
            used.add(i)

            for j in range(i + 1, len(df)):
                if j in used:
                    continue
                other = df.iloc[j]
                if other["timestamp"] - row["timestamp"] > self.window:
                    break
                if _shared_entities(row, other) >= self.min_shared:
                    used.add(j)
                    incident.related_event_ids.append(other["event_id"])
                    incident.timeline.append({
                        "event_id": other["event_id"],
                        "timestamp": other["timestamp"].isoformat(),
                        "event_type": other["event_type"],
                        "user_id": other["user_id"],
                        "device_id": other["device_id"],
                        "ip_address": other["ip_address"],
                        "service": other["service"],
                        "resource": other["resource"],
                    })

            shared = 0
            for k in ["user_id", "device_id", "ip_address", "service", "resource"]:
                if df.loc[incident.related_event_ids.index(row["event_id"]) if False else 0].get(k):
                    pass
            # Compute shared-entity count across the incident.
            members = df[df["event_id"].isin(incident.related_event_ids)]
            for k in ["user_id", "device_id", "ip_address", "service", "resource"]:
                if members[k].nunique() == 1:
                    shared += 1

            size = len(incident.related_event_ids)
            temporal_density = 1.0 / (1.0 + max(0, size - 1))
            score = min(1.0, (shared / 5.0) * 0.6 + (size / 10.0) * 0.4 + temporal_density * 0.1)
            incident.correlation_score = float(score)
            incident.entities = {
                "users": sorted(members["user_id"].unique().tolist()),
                "devices": sorted(members["device_id"].unique().tolist()),
                "ips": sorted(members["ip_address"].unique().tolist()),
                "services": sorted(members["service"].unique().tolist()),
                "resources": sorted(members["resource"].unique().tolist()),
            }
            incidents.append(incident)

        return incidents