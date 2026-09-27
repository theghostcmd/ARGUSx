"""Transparent, configurable risk model.

Risk is deliberately distinct from anomaly:

- Anomaly  = "this event deviates from learned normal behaviour".
- Risk     = "given the deviation and the surrounding context, how much
              potential impact could this represent?"

The risk model is a weighted sum of normalised inputs plus an optional
set of deterministic escalation rules. All weights, thresholds and rules
are read from `risk_config.yaml`. The engine validates that weights sum
to 1.0 and that all weights are non-negative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

from ai_engine.config.settings import get_settings


class RiskConfigError(ValueError):
    pass


@dataclass
class RiskResult:
    risk_score: float
    risk_level: str
    risk_factors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
        }


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


class RiskEngine:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.weights: Dict[str, float] = dict(config["weights"])
        self.thresholds: Dict[str, float] = dict(config["thresholds"])
        self.rules: Dict[str, Any] = dict(config.get("deterministic_rules", {}))

        if any(w < 0 for w in self.weights.values()):
            raise RiskConfigError("Risk weights must be non-negative")
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise RiskConfigError(f"Risk weights must sum to 1.0, got {total}")

    # ------------------------------------------------------------- loading
    @classmethod
    def from_yaml(cls, path: Path) -> "RiskEngine":
        path = Path(path)
        if not path.exists():
            raise RiskConfigError(f"Risk config not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        return cls(config)

    # --------------------------------------------------------------- level
    def _level_for(self, score: float) -> str:
        level = "low"
        for name, lower in sorted(self.thresholds.items(), key=lambda kv: kv[1]):
            if score >= lower:
                level = name
        return level

    # ---------------------------------------------------------- deterministic
    def _apply_rules(
        self,
        anomaly_score: float,
        context: Dict[str, float],
        base_score: float,
        base_level: str,
    ) -> tuple[float, str, List[str]]:
        applied: List[str] = []
        score = base_score
        level = base_level
        for name, rule in self.rules.items():
            if not rule.get("enabled", False):
                continue
            conds = rule.get("conditions", {})
            ok = True
            for key, expected in conds.items():
                actual = context.get(key)
                if actual is None:
                    ok = False
                    break
                if isinstance(expected, bool):
                    if bool(actual) != expected:
                        ok = False
                        break
                elif key.endswith("_min"):
                    if float(actual) < float(expected):
                        ok = False
                        break
                else:
                    if actual != expected:
                        ok = False
                        break
            if ok:
                applied.append(name)
                floor = float(rule.get("set_risk_floor", score))
                score = max(score, floor)
                level = rule.get("set_risk_level", level)
        return _clip01(score), level, applied

    # -------------------------------------------------------------- scoring
    def score(
        self,
        anomaly_score: float,
        asset_criticality: float,
        resource_sensitivity: float,
        correlation_score: float,
        network_deviation: float,
        context: Dict[str, Any] | None = None,
    ) -> RiskResult:
        anomaly_score = _clip01(anomaly_score)
        asset_criticality = _clip01(asset_criticality)
        resource_sensitivity = _clip01(resource_sensitivity)
        correlation_score = _clip01(correlation_score)
        network_deviation = _clip01(network_deviation)

        components = {
            "anomaly_score": anomaly_score,
            "asset_criticality": asset_criticality,
            "resource_sensitivity": resource_sensitivity,
            "correlation": correlation_score,
            "network_deviation": network_deviation,
        }
        raw = sum(self.weights[k] * components[k] for k in self.weights)
        base_score = _clip01(raw)
        base_level = self._level_for(base_score)

        ctx = dict(context or {})
        ctx.update({
            "anomaly_score": anomaly_score,
            "asset_criticality": asset_criticality,
            "resource_sensitivity": resource_sensitivity,
            "network_deviation": network_deviation,
        })
        final_score, final_level, applied = self._apply_rules(
            anomaly_score, ctx, base_score, base_level
        )

        factors: List[Dict[str, Any]] = []
        for k, v in components.items():
            factors.append({
                "factor": k,
                "value": round(v, 4),
                "weight": self.weights[k],
                "contribution": round(self.weights[k] * v, 4),
            })
        for name in applied:
            factors.append({
                "factor": f"deterministic_rule:{name}",
                "value": 1.0,
                "weight": 0.0,
                "contribution": 0.0,
            })

        return RiskResult(
            risk_score=final_score,
            risk_level=final_level,
            risk_factors=factors,
        )


def load_risk_engine(settings=None) -> RiskEngine:
    settings = settings or get_settings()
    return RiskEngine.from_yaml(settings.risk_config_path)