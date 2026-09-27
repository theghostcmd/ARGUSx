"""Pydantic request/response schemas for the FastAPI layer."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

import ipaddress


class SecurityEventIn(BaseModel):
    event_id: str
    timestamp: datetime
    user_id: str
    device_id: str
    ip_address: str
    event_type: str
    service: str
    resource: str
    request_count: int = Field(ge=0)
    bytes_sent: int = Field(ge=0)
    bytes_received: int = Field(ge=0)
    authentication_result: str
    asset_criticality: float = Field(ge=0.0, le=1.0)
    resource_sensitivity: float = Field(ge=0.0, le=1.0)
    network_zone: str
    source_country: str
    destination: str
    session_id: str
    session_duration: Optional[int] = Field(default=0, ge=0)

    @field_validator("ip_address")
    @classmethod
    def _validate_ip(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError as exc:
            raise ValueError(f"Invalid IP address: {v}") from exc
        return v

    @field_validator("authentication_result")
    @classmethod
    def _validate_auth(cls, v: str) -> str:
        if v not in {"success", "failure"}:
            raise ValueError("authentication_result must be 'success' or 'failure'")
        return v


class AnomalyOut(BaseModel):
    score: float
    label: bool
    model_version: str


class RiskOut(BaseModel):
    risk_score: float
    risk_level: str
    risk_factors: List[Dict[str, Any]]


class ExplanationOut(BaseModel):
    provider: str
    summary: str
    evidence: List[Dict[str, Any]]
    limitations: str


class AnalyzeResponse(BaseModel):
    event_id: str
    event: Dict[str, Any]
    features: Dict[str, float]
    anomaly: AnomalyOut
    risk: RiskOut
    explanation: ExplanationOut
    model: Dict[str, str]


class BatchAnalyzeResponse(BaseModel):
    events: List[AnalyzeResponse]
    incidents: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: Optional[str] = None


class ModelInfoResponse(BaseModel):
    model_version: str
    metadata: Dict[str, Any]