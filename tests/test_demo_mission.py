from collections import Counter
from pathlib import Path

import pytest

from uas_thermal.application.mission_intake import scan_mission_folder
from uas_thermal.application.projects import Project
from uas_thermal.application.universal_pipeline import UniversalProcessingPlan, UniversalThermalProcessor
from uas_thermal.sensors.generic import GenericGeoTiffAdapter
from uas_thermal.validation.demo_mission import bundled_demo_blueprint, materialize_demo_mission

rasterio = pytest.importorskip("rasterio")


def test_demo_materializes_as_quantitative_photovoltaic_mission(tmp_path):
    root = materialize_demo_mission(tmp_path)
    intake = scan_mission_folder(root)

    assert intake.ready
    assert intake.profile_id == "photovoltaic"
    assert len(intake.analysis_sources) == 4
    assert all(path.suffix.lower() == ".tif" for path in intake.analysis_sources)
    assert any(path.suffix.lower() == ".png" for path in intake.context_files)
    assert any(path.suffix.lower() == ".geojson" for path in intake.context_files)

    adapter = GenericGeoTiffAdapter()
    for source in intake.analysis_sources:
        diagnostics = adapter.source_diagnostics(source)
        assert diagnostics["radiometric_candidate"] is True
        assert diagnostics["is_calibrated"] is True
        assert diagnostics["count"] == 1
        assert diagnostics["dtype"] == "float32"
        assert diagnostics["crs"] is not None
        assert "UAS Thermal Demo Grid" in diagnostics["crs"]


def test_demo_does_not_require_epsg_authority_lookup(tmp_path, monkeypatch):
    def forbidden_epsg(*_args, **_kwargs):
        raise AssertionError("guided demo must not query EPSG authority database")

    monkeypatch.setattr(rasterio.crs.CRS, "from_epsg", forbidden_epsg)
    root = materialize_demo_mission(tmp_path / "authority-independent")
    intake = scan_mission_folder(root)

    assert intake.ready
    assert len(intake.analysis_sources) == 4


def test_demo_runs_deterministic_stitch_analysis_and_deliverable(tmp_path):
    mission_root = materialize_demo_mission(tmp_path / "mission")
    intake = scan_mission_folder(mission_root)
    project = Project(
        name=intake.project_name,
        site="Synthetic Solar Farm Demo",
        profile_id=intake.profile_id,
        metadata={"synthetic_demo": True},
    )
    processor = UniversalThermalProcessor()
    result = processor.process(
        project,
        list(intake.analysis_sources),
        tmp_path / "deliverables",
        plan=UniversalProcessingPlan(
            stitch_mode="on",
            orthomosaic_backend="native-geotiff",
            ai_mode="off",
        ),
    )

    expected = bundled_demo_blueprint()
    assert result.orthomosaic is not None
    assert result.orthomosaic.quantitative is True
    assert result.orthomosaic.orthomosaic.is_file()
    assert result.ai_enriched_findings == 0
    assert len(result.run.canonical_findings) == expected["expected_canonical_findings"]
    counts = Counter(finding.severity.value for finding in result.run.canonical_findings)
    assert dict(counts) == expected["expected_severity_counts"]

    root = result.deliverable_dir
    required = (
        "report/inspection_report.pdf",
        "data/findings.csv",
        "data/findings.json",
        "maps/annotated_thermal_overview.png",
        "maps/thermal_orthomosaic.tif",
        "viewer/index.html",
        "report/processing_report.json",
        "inspection_manifest.json",
    )
    assert all((root / Path(relative)).is_file() for relative in required)
