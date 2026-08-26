import json
from pathlib import Path

import numpy as np
import pytest

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


def _orchestrator() -> AutonomousInspectionOrchestrator:
    return AutonomousInspectionOrchestrator(AnalysisWorkflow(AdapterRegistry([PackageAdapter()])))


def test_orchestrator_writes_traceable_inspection_package(tmp_path):
    run = _orchestrator().analyze_inspection(
        Project(name="Package Proof", inspection_id="I-900"),
        ["proof.tif"],
        output_dir=tmp_path,
    )
    root = tmp_path / "I-900"
    assert run.package_dir == root
    assert (root / "report" / "inspection_report.pdf").is_file()
    assert (root / "report" / "engineering_evidence_appendix.json").is_file()
    assert (root / "report" / "engineering_evidence_appendix.md").is_file()
    assert (root / "data" / "findings.csv").is_file()
    assert (root / "data" / "findings.json").is_file()
    assert (root / "findings" / "A-001" / "annotated_thermal.png").is_file()
    assert (root / "findings" / "A-001" / "thermal_crop.png").is_file()
    assert (root / "findings" / "A-001" / "finding_plate.png").is_file()
    manifest = json.loads((root / "inspection_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.1"
    assert "report/inspection_report.pdf" in manifest["files"]
    assert "report/engineering_evidence_appendix.json" in manifest["files"]
    assert manifest["summary"]["canonical_findings"] == 1
    assert manifest["thermal_evidence"]["bands"][0]["authority"] == "radiometric"
    assert manifest["thermal_evidence"]["bands"][1]["authority"] == "derived"
    assert "not thermographer certification" in manifest["claim_boundary"]


def test_package_path_is_sanitized_without_mutating_inspection_metadata(tmp_path):
    inspection_id = "../CON:client?*"
    run = _orchestrator().analyze_inspection(
        Project(name="Unsafe ID", inspection_id=inspection_id),
        ["proof.tif"],
        output_dir=tmp_path,
    )

    assert run.package_dir is not None
    assert run.package_dir.parent == tmp_path
    assert run.package_dir.is_dir()
    assert ".." not in run.package_dir.name
    assert not any(char in run.package_dir.name for char in '<>:"/\\|?*')
    manifest = json.loads((run.package_dir / "inspection_manifest.json").read_text(encoding="utf-8"))
    assert manifest["project"]["inspection_id"] == inspection_id


def test_rerun_replaces_package_instead_of_retaining_stale_files(tmp_path):
    project = Project(name="Rerun", inspection_id="I-RERUN")
    first = _orchestrator().analyze_inspection(project, ["proof.tif"], output_dir=tmp_path)
    assert first.package_dir is not None
    stale = first.package_dir / "stale-from-previous-run.txt"
    stale.write_text("old", encoding="utf-8")

    second = _orchestrator().analyze_inspection(project, ["proof.tif"], output_dir=tmp_path)

    assert second.package_dir == first.package_dir
    assert not stale.exists()
    assert not list(tmp_path.glob(".I-RERUN.staging-*"))
    assert not list(tmp_path.glob(".I-RERUN.previous-*"))


def test_failed_rerun_preserves_last_complete_package(tmp_path, monkeypatch):
    project = Project(name="Rollback", inspection_id="I-ROLLBACK")
    first = _orchestrator().analyze_inspection(project, ["proof.tif"], output_dir=tmp_path)
    assert first.package_dir is not None
    marker = first.package_dir / "known-good.txt"
    marker.write_text("keep", encoding="utf-8")

    import uas_thermal.reporting.package as package_module

    def fail_pdf(*args, **kwargs):
        raise RuntimeError("synthetic report failure")

    monkeypatch.setattr(package_module, "write_pdf", fail_pdf)
    with pytest.raises(RuntimeError, match="synthetic report failure"):
        _orchestrator().analyze_inspection(project, ["proof.tif"], output_dir=tmp_path)

    assert marker.read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".I-ROLLBACK.staging-*"))
