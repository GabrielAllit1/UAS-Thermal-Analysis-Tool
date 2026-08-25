import json
from pathlib import Path

import numpy as np

from uas_thermal.application.orchestrator import AutonomousInspectionOrchestrator
from uas_thermal.application.projects import Project
from uas_thermal.application.workflows import AnalysisWorkflow
from uas_thermal.sensors.base import ThermalFrame, ThermalSensorAdapter
from uas_thermal.sensors.registry import AdapterRegistry
from uas_thermal.thermal.calibration import ThermalCalibration


class PackageAdapter(ThermalSensorAdapter):
    name = "package-fake"

    def can_read(self, path: Path) -> bool:
        return True

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        values = np.full((64, 64), 24.0, dtype=np.float32)
        values[22:34, 24:36] = 48.0
        display = np.repeat(np.full((64, 64, 1), 80, dtype=np.uint8), 3, axis=2)
        return ThermalFrame(
            values,
            path,
            display_rgb=display,
            metadata={"capture_time": "2026-08-25T12:00:00+00:00"},
        )


def test_orchestrator_writes_traceable_inspection_package(tmp_path):
    workflow = AnalysisWorkflow(AdapterRegistry([PackageAdapter()]))
    run = AutonomousInspectionOrchestrator(workflow).analyze_inspection(
        Project(name="Package Proof", inspection_id="I-900"),
        ["proof.tif"],
        output_dir=tmp_path,
    )
    root = tmp_path / "I-900"
    assert run.package_dir == root
    assert (root / "report" / "inspection_report.pdf").is_file()
    assert (root / "data" / "findings.csv").is_file()
    assert (root / "data" / "findings.json").is_file()
    assert (root / "findings" / "A-001" / "annotated_thermal.png").is_file()
    assert (root / "findings" / "A-001" / "thermal_crop.png").is_file()
    assert (root / "findings" / "A-001" / "finding_plate.png").is_file()
    manifest = json.loads((root / "inspection_manifest.json").read_text(encoding="utf-8"))
    assert "report/inspection_report.pdf" in manifest["files"]
    assert manifest["summary"]["canonical_findings"] == 1
    assert "not thermographer certification" in manifest["claim_boundary"]
