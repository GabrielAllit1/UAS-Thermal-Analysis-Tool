from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..thermal.statistics import TemperatureStatistics


class Severity(str, Enum):
    CRITICAL = "critical"
    MODERATE = "moderate"
    MINOR = "minor"


@dataclass(slots=True)
class Finding:
    center_x: int
    center_y: int
    area_px: int
    max_temperature_c: float
    mean_temperature_c: float
    baseline_temperature_c: float
    delta_temperature_c: float
    severity: Severity
    finding_type: str = "Thermal anomaly"
    latitude: float | None = None
    longitude: float | None = None
    notes: str = ""


@dataclass(slots=True)
class InspectionResult:
    source: str
    adapter: str
    statistics: TemperatureStatistics
    findings: list[Finding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
