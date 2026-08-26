from pathlib import Path

import numpy as np

from uas_thermal.application.orchestrator import AutonomousInspectionOrchestrator, ProcessingStage
from uas_thermal.application.projects import Project
from uas_thermal.application.workflows import AnalysisWorkflow
from uas_thermal.sensors.base import ThermalFrame, ThermalSensorAdapter
from uas_thermal.sensors.registry import AdapterRegistry
from uas_thermal.thermal.calibration import ThermalCalibration


class FakeAdapter(ThermalSensorAdapter):
    name = "fake"

    def can_read(self, path: Path) -> bool:
        return True

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        if "bad" in path.name:
            raise RuntimeError("synthetic decode failure")
        values = np.full((48, 48), 25.0, dtype=np.float32)
        values[18:28, 19:29] = 45.0
        return ThermalFrame(
            values,
            path,
            metadata={"capture_time": "2026-08-25T12:00:00+00:00"},
            crs="EPSG:4326",
            transform=(0.00001, 0.0, -82.0, 0.0, -0.00001, 28.0),
        )


def test_orchestrator_isolates_failed_source_and_returns_canonical_findings():
    workflow = AnalysisWorkflow(AdapterRegistry([FakeAdapter()]))
    orchestrator = AutonomousInspectionOrchestrator(workflow)
    project = Project(name="Demo", inspection_id="I-001")
    run = orchestrator.analyze_inspection(project, ["good.tif", "bad.tif"])
    assert len(run.artifacts) == 1
    assert len(run.failures) == 1
    assert len(run.canonical_findings) == 1
    assert run.canonical_findings[0].finding_id == "A-001"
    assert run.summary.images_discovered == 2
    assert run.summary.images_rejected == 1
    assert run.events[-1].stage is ProcessingStage.COMPLETE


def test_orchestrator_fails_when_every_source_is_rejected():
    workflow = AnalysisWorkflow(AdapterRegistry([FakeAdapter()]))
    orchestrator = AutonomousInspectionOrchestrator(workflow)
    run = orchestrator.analyze_inspection(
        Project(name="Rejected", inspection_id="I-FAIL"),
        ["bad-1.tif", "bad-2.tif"],
    )

    assert not run.artifacts
    assert len(run.failures) == 2
    assert run.summary.images_rejected == 2
    assert run.status is ProcessingStage.FAILED
    assert run.events[-1].stage is ProcessingStage.FAILED
    assert "all 2 source(s) were rejected" in run.events[-1].message
