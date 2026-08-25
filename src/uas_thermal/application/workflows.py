from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .. import __version__
from ..geospatial.transforms import pixel_to_map, transform_point
from ..inspections.models import InspectionResult, InspectionSummary
from ..inspections.profiles import InspectionProfile, get_profile
from ..inspections.recommendations import maintenance_recommendation
from ..sensors.base import AdapterUnavailableError, ThermalFrame
from ..sensors.registry import AdapterRegistry, default_registry
from ..thermal.anomaly_detection import DetectionConfig, analyze_temperature
from ..thermal.calibration import ThermalCalibration
from ..thermal.quality import evaluate_radiometric_quality
from ..thermal.statistics import summarize_temperature
from .projects import Project


@dataclass(slots=True)
class AnalysisArtifact:
    result: InspectionResult
    frame: ThermalFrame


@dataclass(slots=True)
class AnalysisWorkflow:
    registry: AdapterRegistry
    detection: DetectionConfig = field(default_factory=DetectionConfig)

    @classmethod
    def default(cls) -> AnalysisWorkflow:
        return cls(default_registry())

    def analyze_artifact(
        self,
        source: str | Path,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
        profile: InspectionProfile | None = None,
    ) -> AnalysisArtifact:
        source_path = Path(source)
        calibration = calibration or ThermalCalibration()
        active_profile = profile or get_profile(project.profile_id if project else None)
        adapter = self.registry.select(source_path, preferred=adapter_name)
        frame = adapter.read(source_path, calibration)
        quality = evaluate_radiometric_quality(frame, calibration)
        if not quality.accepted:
            raise AdapterUnavailableError(
                "Radiometric quality gate rejected source: " + "; ".join(quality.reasons)
            )

        stats = summarize_temperature(frame.temperature_c)
        config = DetectionConfig.from_profile(active_profile)
        # Preserve explicit workflow overrides used by existing integrations/tests.
        if self.detection != DetectionConfig():
            config = self.detection
        outcome = analyze_temperature(
            frame.temperature_c,
            config=config,
            profile=active_profile,
        )
        findings = outcome.findings
        metadata = dict(frame.metadata)
        metadata["analysis_engine_version"] = __version__
        metadata["detection"] = outcome.diagnostics
        self._georeference(findings, frame, metadata)

        project_metadata = project.report_metadata() if project else {}
        inspection_id = project.inspection_id if project else ""
        project_id = project.project_id if project else ""
        source_id = source_path.name
        for finding in findings:
            finding.inspection_id = inspection_id
            finding.project_id = project_id
            finding.source_image_id = source_id
            finding.source_path = str(source_path)
            finding.source_sensor = " ".join(
                filter(None, [project.sensor_vendor, project.sensor_model])
            ) if project else str(frame.metadata.get("sensor", ""))
            finding.radiometric_provenance = {
                "adapter": adapter.name,
                "quality_status": quality.status.value,
                "calibration": {
                    "emissivity": calibration.emissivity,
                    "distance_m": calibration.distance_m,
                    "relative_humidity": calibration.relative_humidity,
                    "reflected_temperature_c": calibration.reflected_temperature_c,
                },
            }
            finding.quality_status = quality.status
            finding.analysis_engine_version = __version__
            finding.recommendation = maintenance_recommendation(finding, active_profile)

        summary = InspectionSummary(
            images_discovered=1,
            images_accepted=1,
            images_warned=int(bool(quality.warnings)),
            observations=len(findings),
            canonical_findings=len(findings),
            critical=sum(item.severity.value == "critical" for item in findings),
            moderate=sum(item.severity.value == "moderate" for item in findings),
            minor=sum(item.severity.value == "minor" for item in findings),
            highest_temperature_c=max((item.max_temperature_c for item in findings), default=stats.maximum_c),
            highest_delta_c=max((item.delta_temperature_c for item in findings), default=None),
        )
        result = InspectionResult(
            source=str(source_path),
            adapter=adapter.name,
            statistics=stats,
            findings=findings,
            metadata=metadata,
            project=project_metadata,
            suppressions=outcome.suppressions,
            quality=quality.as_dict(),
            profile=active_profile.as_dict(),
            summary=summary,
        )
        return AnalysisArtifact(result=result, frame=frame)

    def analyze(
        self,
        source: str | Path,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
        profile: InspectionProfile | None = None,
    ) -> InspectionResult:
        return self.analyze_artifact(source, calibration, adapter_name, project, profile).result

    def analyze_many(
        self,
        sources: Iterable[str | Path],
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
        profile: InspectionProfile | None = None,
    ) -> list[AnalysisArtifact]:
        return [
            self.analyze_artifact(source, calibration, adapter_name, project, profile)
            for source in sources
        ]

    @staticmethod
    def _georeference(findings, frame: ThermalFrame, metadata: dict) -> None:
        if not findings or frame.transform is None or not frame.crs:
            return
        assigned = 0
        try:
            for finding in findings:
                map_x, map_y = pixel_to_map(
                    finding.center_x,
                    finding.center_y,
                    frame.transform,
                )
                lon, lat = transform_point(map_x, map_y, frame.crs)
                finding.longitude = float(lon)
                finding.latitude = float(lat)
                assigned += 1
        except (RuntimeError, ValueError) as exc:
            metadata.setdefault("warnings", []).append(str(exc))
            metadata["georeferencing_status"] = "not_authoritative"
            return
        metadata["georeferenced_findings"] = assigned
        metadata["georeferencing_status"] = "assigned"
