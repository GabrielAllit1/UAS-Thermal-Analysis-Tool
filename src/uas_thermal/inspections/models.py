from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..thermal.statistics import TemperatureStatistics


class Severity(StrEnum):
    CRITICAL = "critical"
    MODERATE = "moderate"
    MINOR = "minor"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QualityStatus(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    REJECTED = "rejected"


class FindingStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    ACTION_REQUIRED = "action_required"
    MONITOR = "monitor"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass(slots=True)
class SuppressionRecord:
    reason: str
    area_px: int
    center_x: int | None = None
    center_y: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Finding:
    """Canonical quantitative finding shared by UI, map, exports and reports.

    The first fields intentionally preserve the pre-v0.5 positional constructor contract.
    Extended evidence fields use explicit defaults so legacy callers remain compatible.
    AI enrichment is supplemental narrative evidence and may never replace quantitative fields.
    """

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

    finding_id: str = ""
    inspection_id: str = ""
    project_id: str = ""
    source_image_id: str = ""
    source_dataset_id: str = ""
    source_path: str = ""
    classification: str = "Thermal anomaly"
    classification_rationale: str = ""
    severity_rationale: str = ""
    confidence: Confidence = Confidence.MEDIUM
    confidence_components: dict[str, float | str | bool] = field(default_factory=dict)
    bbox: tuple[int, int, int, int] | None = None
    polygon: list[tuple[int, int]] = field(default_factory=list)
    hotspot_x: int | None = None
    hotspot_y: int | None = None
    min_temperature_c: float | None = None
    reference_temperature_c: float | None = None
    reference_method: str = ""
    area_physical: float | None = None
    percentage_asset_affected: float | None = None
    morphology: dict[str, float | int | str | bool] = field(default_factory=dict)
    altitude: float | None = None
    source_sensor: str = ""
    capture_time: str = ""
    radiometric_provenance: dict[str, Any] = field(default_factory=dict)
    quality_status: QualityStatus = QualityStatus.PASS
    evidence: list[str] = field(default_factory=list)
    suppression_checks: list[str] = field(default_factory=list)
    recommendation: str = ""
    ai_enrichment: dict[str, Any] = field(default_factory=dict)
    annotated_image_path: str = ""
    crop_path: str = ""
    visible_image_path: str = ""
    duplicate_cluster_id: str = ""
    canonical_finding_id: str = ""
    supporting_observations: list[str] = field(default_factory=list)
    profile_id: str = "generic-thermal"
    profile_version: str = "1.0"
    analysis_engine_version: str = ""
    lifecycle_status: FindingStatus = FindingStatus.NEW
    created_at: str = ""
    updated_at: str = ""
    audit_trail: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class InspectionSummary:
    images_discovered: int = 0
    images_accepted: int = 0
    images_warned: int = 0
    images_rejected: int = 0
    observations: int = 0
    canonical_findings: int = 0
    critical: int = 0
    moderate: int = 0
    minor: int = 0
    highest_temperature_c: float | None = None
    highest_delta_c: float | None = None


@dataclass(slots=True)
class InspectionResult:
    source: str
    adapter: str
    statistics: TemperatureStatistics
    findings: list[Finding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    project: dict[str, Any] = field(default_factory=dict)
    suppressions: list[SuppressionRecord] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    summary: InspectionSummary | None = None
