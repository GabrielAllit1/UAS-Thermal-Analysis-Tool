from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..geospatial.transforms import pixel_to_map, transform_point
from ..inspections.models import InspectionResult
from ..sensors.base import ThermalFrame
from ..sensors.registry import AdapterRegistry, default_registry
from ..thermal.anomaly_detection import DetectionConfig, detect_anomalies
from ..thermal.calibration import ThermalCalibration
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
    ) -> AnalysisArtifact:
        source_path = Path(source)
        adapter = self.registry.select(source_path, preferred=adapter_name)
        frame = adapter.read(source_path, calibration or ThermalCalibration())
        stats = summarize_temperature(frame.temperature_c)
        findings = detect_anomalies(frame.temperature_c, config=self.detection)
        metadata = dict(frame.metadata)
        self._georeference(findings, frame, metadata)
        result = InspectionResult(
            source=str(source_path),
            adapter=adapter.name,
            statistics=stats,
            findings=findings,
            metadata=metadata,
            project=project.report_metadata() if project else {},
        )
        return AnalysisArtifact(result=result, frame=frame)

    def analyze(
        self,
        source: str | Path,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
    ) -> InspectionResult:
        return self.analyze_artifact(source, calibration, adapter_name, project).result

    def analyze_many(
        self,
        sources: Iterable[str | Path],
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
    ) -> list[AnalysisArtifact]:
        return [
            self.analyze_artifact(source, calibration, adapter_name, project)
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
        except RuntimeError as exc:
            metadata.setdefault("warnings", []).append(str(exc))
            return
        metadata["georeferenced_findings"] = assigned
