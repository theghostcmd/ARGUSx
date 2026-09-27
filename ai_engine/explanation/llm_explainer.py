"""Optional LLM-backed explanation provider.

Only structured evidence (no secrets, no credentials) is sent to the
configured provider. If the call fails for any reason, the caller falls
back to the local provider.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import httpx

from ai_engine.utils.logging import get_logger

logger = get_logger(__name__)


class LLMExplanationProvider:
    name = "llm"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.model = model or os.getenv("LLM_MODEL")
        self.timeout = timeout
        if not (self.api_key and self.base_url and self.model):
            raise ValueError("LLM provider requires LLM_API_KEY, LLM_BASE_URL and LLM_MODEL")

    def explain(
        self,
        event: Dict[str, Any],
        features: Dict[str, float],
        anomaly: Dict[str, Any],
        risk: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a defensive cybersecurity analyst. Explain the "
                        "evidence in neutral language. Never claim an attack is "
                        "confirmed unless a deterministic rule explicitly says so."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "event": {k: v for k, v in event.items() if k not in {"password"}},
                            "features": features,
                            "anomaly": anomaly,
                            "risk": risk,
                        },
                        default=str,
                    ),
                },
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return {
            "provider": self.name,
            "summary": text,
            "evidence": [],
            "limitations": (
                "LLM-generated narrative. It is a paraphrase of structured "
                "evidence, not a source of truth. An anomaly is not a threat."
            ),
        }