"""Synthetic security telemetry generator.

This module produces a realistic, reproducible synthetic dataset that
contains normal behaviour plus controlled anomalies. It is intended for
hackathon / offline development where real organisational logs are not
available.

Design notes
------------
- Every user has a distinct "working window" (e.g. 08:00-18:00) and a
  set of devices, IPs, services and resources they habitually use.
- Request counts, byte volumes and session durations follow user-specific
  log-normal distributions.
- Anomalies are injected by deliberately violating one or more of these
  habits (off-hours login, unseen device/IP, request spikes, sensitive
  resource access, auth failures, unusual network zones).
- The generator is deterministic given a seed.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Static reference tables (realistic-ish). These are inputs to the generator,
# not fabricated outputs of the AI engine.
# ---------------------------------------------------------------------------

SERVICES = ["web", "ssh", "vpn", "email", "file_share", "db"]
NETWORK_ZONES = ["corp", "dmz", "vpn_pool", "guest", "cloud"]
RESOURCES = {
    "PROJECT_SERVER": 0.3,
    "FILE_SHARE": 0.2,
    "MAIL_SERVER": 0.25,
    "HR_PORTAL": 0.5,
    "FINANCE_DB": 0.9,
    "CUSTOMER_DB": 0.95,
    "LOGS": 0.4,
}
ASSET_CRITICALITY = {
    "D01": 0.4, "D02": 0.4, "D03": 0.6, "D04": 0.5,
    "D05": 0.7, "D06": 0.3, "D07": 0.6, "D08": 0.8,
    "D09": 0.5, "D10": 0.9, "D99": 0.95,
}
COUNTRIES = ["US", "DE", "IN", "BR", "SG", "RU", "CN", "NG"]


@dataclass
class UserProfile:
    user_id: str
    work_start: int          # hour of day
    work_end: int
    devices: List[str]
    ips: List[str]
    services: List[str]
    resources: List[str]
    request_mu: float
    request_sigma: float
    bytes_mu: float
    bytes_sigma: float
    session_mu: float
    session_sigma: float
    home_country: str
    home_zone: str


def _make_profiles(n_users: int, rng: np.random.Generator) -> List[UserProfile]:
    profiles: List[UserProfile] = []
    for i in range(n_users):
        uid = f"U{100 + i}"
        start = int(rng.integers(7, 10))
        end = start + int(rng.integers(7, 10))
        n_dev = int(rng.integers(1, 3))
        n_ip = int(rng.integers(1, 3))
        n_svc = int(rng.integers(2, 4))
        n_res = int(rng.integers(2, 4))
        profiles.append(
            UserProfile(
                user_id=uid,
                work_start=start,
                work_end=end,
                devices=list(rng.choice([f"D{100+i*3+j:02d}" if False else f"D{(i*3+j)%9+1:02d}"
                                          for j in range(n_dev)], size=n_dev, replace=False)),
                ips=[f"10.{i}.{j}.{int(rng.integers(2, 250))}" for j in range(n_ip)],
                services=list(rng.choice(SERVICES, size=n_svc, replace=False)),
                resources=list(rng.choice(list(RESOURCES.keys()), size=n_res, replace=False)),
                request_mu=float(rng.normal(20, 5)),
                request_sigma=float(abs(rng.normal(5, 1)) + 1.0),
                bytes_mu=float(rng.normal(5000, 1000)),
                bytes_sigma=float(abs(rng.normal(1500, 300)) + 1.0),
                session_mu=float(rng.normal(900, 200)),
                session_sigma=float(abs(rng.normal(200, 50)) + 1.0),
                home_country=str(rng.choice(["US", "DE", "IN", "BR", "SG"])),
                home_zone=str(rng.choice(["corp", "vpn_pool", "cloud"])),
            )
        )
    return profiles


def _make_normal_event(profile: UserProfile, rng: np.random.Generator) -> dict:
    hour = int(rng.integers(profile.work_start, profile.work_end))
    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))
    day_offset = int(rng.integers(0, 30))
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=day_offset, hours=hour, minutes=minute, seconds=second
    )
    service = str(rng.choice(profile.services))
    resource = str(rng.choice(profile.resources))
    device = str(rng.choice(profile.devices))
    ip = str(rng.choice(profile.ips))
    req = max(1, int(rng.normal(profile.request_mu, profile.request_sigma)))
    bytes_sent = max(10, int(rng.normal(profile.bytes_mu, profile.bytes_sigma)))
    bytes_recv = max(10, int(rng.normal(profile.bytes_mu * 0.8, profile.bytes_sigma)))
    session = max(1, int(rng.normal(profile.session_mu, profile.session_sigma)))
    auth = "success" if rng.random() > 0.03 else "failure"
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": ts.isoformat(),
        "user_id": profile.user_id,
        "device_id": device,
        "ip_address": ip,
        "event_type": "access",
        "service": service,
        "resource": resource,
        "request_count": req,
        "bytes_sent": bytes_sent,
        "bytes_received": bytes_recv,
        "session_duration": session,
        "authentication_result": auth,
        "asset_criticality": ASSET_CRITICALITY.get(device, 0.5),
        "resource_sensitivity": RESOURCES.get(resource, 0.5),
        "network_zone": profile.home_zone,
        "source_country": profile.home_country,
        "destination": resource,
        "is_anomaly_injected": 0,
    }


def _inject_anomalies(df: pd.DataFrame, profiles: List[UserProfile],
                      rng: np.random.Generator, anomaly_fraction: float) -> pd.DataFrame:
    n = len(df)
    n_anom = int(n * anomaly_fraction)
    idx = rng.choice(n, size=n_anom, replace=False)
    df = df.copy()

    for i in idx:
        profile = next(p for p in profiles if p.user_id == df.at[i, "user_id"])
        kind = int(rng.integers(0, 4))
        ts = datetime.fromisoformat(df.at[i, "timestamp"])
        if kind == 0:
            # off-hours login
            hour = (profile.work_end + int(rng.integers(3, 8))) % 24
            ts = ts.replace(hour=hour)
            df.at[i, "timestamp"] = ts.isoformat()
        elif kind == 1:
            # unseen device
            df.at[i, "device_id"] = "D99"
            df.at[i, "asset_criticality"] = ASSET_CRITICALITY["D99"]
        elif kind == 2:
            # request spike
            df.at[i, "request_count"] = int(df.at[i, "request_count"] * rng.uniform(6, 15))
        elif kind == 3:
            # sensitive resource + new IP + failure
            df.at[i, "resource"] = "CUSTOMER_DB"
            df.at[i, "resource_sensitivity"] = RESOURCES["CUSTOMER_DB"]
            df.at[i, "ip_address"] = f"203.0.113.{int(rng.integers(2, 250))}"
            df.at[i, "source_country"] = str(rng.choice(["RU", "CN", "NG"]))
            df.at[i, "authentication_result"] = "failure"
        df.at[i, "is_anomaly_injected"] = 1
    return df


def generate_dataset(
    n_users: int = 30,
    n_events: int = 3000,
    anomaly_fraction: float = 0.08,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a reproducible synthetic security dataset."""
    rng = np.random.default_rng(seed)
    profiles = _make_profiles(n_users, rng)

    rows = []
    for _ in range(n_events):
        profile = profiles[int(rng.integers(0, len(profiles)))]
        rows.append(_make_normal_event(profile, rng))
    df = pd.DataFrame(rows)
    df = _inject_anomalies(df, profiles, rng, anomaly_fraction)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def save_dataset(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "ai_engine/data/raw/events.csv"
    dataset = generate_dataset()
    save_dataset(dataset, out)
    print(f"Wrote {len(dataset)} events to {out}")