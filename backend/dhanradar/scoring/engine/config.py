"""
DhanRadar — Rating engine config loader.

Loads the versioned, declarative ``ranking_configs_v1.json`` (data, not logic) and
validates the structural invariants the engine relies on:

  * composite axis weights sum to 1.0 ± tolerance (spec §3),
  * no sub-factor appears in two axes (double-counting guard, spec / config note),
  * confidence weights sum to 1.0.

The engine reads weights/thresholds from here — it never hardcodes them — so a
new model_version is a config change, validated at load.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dhanradar.scoring.engine.schemas import Axis

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "ranking_configs_v1.json"


class ConfigError(ValueError):
    """The ranking config violates a structural invariant."""


@dataclass(frozen=True)
class EngineConfig:
    model_version: str
    activated: bool
    axis_weights: dict[Axis, float]
    weight_sum_tolerance: float
    axis_subfactors: dict[Axis, list[str]]
    confidence_weights: dict[str, float]
    low_coverage_threshold_pct: float
    confidence_floor: float

    def validate(self) -> None:
        # Every axis must carry a weight, else the engine KeyErrors under traffic
        # when that axis is present. Catch it at load, not at first score().
        missing_axes = set(Axis) - set(self.axis_weights)
        if missing_axes:
            raise ConfigError(f"axis_weights missing axes: {sorted(a.value for a in missing_axes)}")
        total = sum(self.axis_weights.values())
        if abs(total - 1.0) > self.weight_sum_tolerance:
            raise ConfigError(
                f"composite axis weights must sum to 1.0 ± {self.weight_sum_tolerance}; got {total}"
            )
        # Confidence formula reads these keys by name — fail at load on a typo.
        expected_conf = {
            "freshness", "coverage", "factor_agreement", "retrieval_relevance", "model_signal",
        }
        missing_conf = expected_conf - set(self.confidence_weights)
        if missing_conf:
            raise ConfigError(f"confidence_weights missing keys: {sorted(missing_conf)}")
        # Double-counting guard: a sub-factor may live in exactly one axis.
        seen: dict[str, Axis] = {}
        for axis, subs in self.axis_subfactors.items():
            for s in subs:
                if s in seen:
                    raise ConfigError(
                        f"sub-factor {s!r} appears in both {seen[s].value!r} and {axis.value!r}"
                    )
                seen[s] = axis
        c_total = sum(self.confidence_weights.values())
        if abs(c_total - 1.0) > 0.001:
            raise ConfigError(f"confidence weights must sum to 1.0; got {c_total}")


def load_config(path: Path | None = None) -> EngineConfig:
    raw = json.loads((path or _CONFIG_PATH).read_text(encoding="utf-8"))
    composite = raw["composite"]
    cfg = EngineConfig(
        model_version=raw["model_version"],
        activated=bool(raw.get("activated", False)),
        axis_weights={Axis(k): float(v) for k, v in composite["weights"].items()},
        weight_sum_tolerance=float(composite.get("weight_sum_tolerance", 0.001)),
        axis_subfactors={Axis(k): list(v) for k, v in raw["axes"].items()},
        confidence_weights={k: float(v) for k, v in raw["confidence"]["weights"].items()},
        low_coverage_threshold_pct=float(raw["missing_data"]["axis_low_coverage_threshold_pct"]),
        confidence_floor=float(raw["confidence"]["floor"]["below"]),
    )
    cfg.validate()
    return cfg


@lru_cache(maxsize=1)
def get_config() -> EngineConfig:
    """Cached canonical config (validated at first load)."""
    return load_config()
