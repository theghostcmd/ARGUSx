"""FastAPI application for the ARGUS-X AI engine."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from ai_engine.api.schemas import (
    AnalyzeResponse,
    BatchAnalyzeResponse,
    HealthResponse,
    ModelInfoResponse,
    SecurityEventIn,
)
from ai_engine.models.anomaly_detector import ModelNotFoundError
from ai_engine.services.analysis_service import (
    FeatureEngineeringError,
    InvalidEventError as ServiceInvalidEventError,
)
from ai_engine.services.model_service import get_model_service
from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = get_model_service()
    try:
        service.initialize()
    except ModelNotFoundError:
        logger.warning("Model not found at startup; /analyze will return 503 until trained.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Startup initialization failed: %s", exc)
    yield


app = FastAPI(
    title="ARGUS-X AI Engine",
    version="1.0.0",
    description=(
        "AI/ML subsystem of the ARGUS-X cybersecurity digital twin. "
        "Detects behavioural anomalies and contextualises them into risk. "
        "An anomaly is not a confirmed threat."
    ),
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    service = get_model_service()
    loaded = service.analysis_service is not None
    version = None
    if loaded:
        try:
            version = service.registry.metadata().get("model_version")
        except Exception:  # noqa: BLE001
            version = None
    return HealthResponse(status="ok", model_loaded=loaded, model_version=version)


@app.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    service = get_model_service()
    try:
        meta = service.registry.metadata()
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ModelInfoResponse(
        model_version=meta.get("model_version", "unknown"),
        metadata=meta,
    )


@app.post("/reload-model", response_model=ModelInfoResponse)
def reload_model() -> ModelInfoResponse:
    service = get_model_service()
    try:
        service.reload()
        meta = service.registry.metadata()
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ModelInfoResponse(
        model_version=meta.get("model_version", "unknown"),
        metadata=meta,
    )


@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    service = get_model_service()
    meta = service.registry.metadata() if service.analysis_service else {}
    return {
        "model_loaded": service.analysis_service is not None,
        "model_version": meta.get("model_version"),
        "training_sample_count": meta.get("training_sample_count"),
        "algorithm": meta.get("algorithm"),
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(event: SecurityEventIn) -> AnalyzeResponse:
    service = get_model_service()
    try:
        analysis = service.get()
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payload = event.model_dump()
    payload["timestamp"] = payload["timestamp"].isoformat()
    try:
        result = analysis.analyze_event(payload)
    except ServiceInvalidEventError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FeatureEngineeringError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AnalyzeResponse(**result)


@app.post("/analyze/batch", response_model=BatchAnalyzeResponse)
def analyze_batch(events: List[SecurityEventIn]) -> BatchAnalyzeResponse:
    service = get_model_service()
    try:
        analysis = service.get()
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payloads = []
    for ev in events:
        p = ev.model_dump()
        p["timestamp"] = p["timestamp"].isoformat()
        payloads.append(p)

    try:
        result = analysis.analyze_batch(payloads)
    except ServiceInvalidEventError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FeatureEngineeringError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return BatchAnalyzeResponse(**result)


@app.exception_handler(ModelNotFoundError)
def _model_not_found(_request, exc):  # noqa: ANN001
    return JSONResponse(status_code=503, content={"detail": str(exc)})