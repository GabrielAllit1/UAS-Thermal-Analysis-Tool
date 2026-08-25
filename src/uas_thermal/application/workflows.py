from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..inspections.models import InspectionResult
from ..sensors.registry import AdapterRegistry, default_registry
from ..thermal.anomaly_detection import DetectionConfig, detect_anomalies
from ..thermal.calibration import ThermalCalibration
from ..thermal.statistics import summarize_temperature


@dataclass(slots=True)
class AnalysisWorkflow:
    registry: AdapterRegistry
    detection: DetectionConfig = DetectionConfig()

    @classmethod
    def default(cls) -> "AnalysisWorkflow":
        return cls(default_registry())

    def analyze(
        self,
        source: str | Path,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
    ) -> InspectionResult:
        source_path = Path(source)
        adapter = self.registry.select(source_path, preferred=adapter_name)
        frame = adapter.read(source_path, calibration or ThermalCalibration())
        stats = summarize_temperature(frame.temperature_c)
        findings = detect_anomalies(frame.temperature_c, config=self.detection)
        return InspectionResult(
            source=str(source_path),
            adapter=adapter.name,
            statistics=stats,
            findings=findings,
            metadata=frame.metadata,
        )
