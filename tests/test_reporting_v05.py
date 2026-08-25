import json
from pathlib import Path

import numpy as np

from uas_thermal.inspections.models import Confidence, Finding, Severity
from uas_thermal.reporting.annotations import write_finding_evidence
from uas_thermal.reporting.geojson_report import write_geojson
from uas_thermal.reporting.json_report import write_findings_json
from uas_thermal.sensors.base import ThermalFrame


def _finding():
    return Finding(
        20,
        20,
        100,
        55.0,
        50.0,
        25.0,
        30.0,
        Severity.CRITICAL,
        finding_id="A-001",
        classification="Thermal anomaly",
        confidence=Confidence.HIGH,
        bbox=(15, 15, 24, 24),
        hotspot_x=20,
        hotspot_y=20,
        reference_temperature_c=25.0,
        reference_method="surrounding-ring-median",
        latitude=28.0,
        longitude=-82.0,
        evidence=["strong local contrast"],
        recommendation="Prioritize field verification.",
    )


def test_annotation_renderer_writes_overview_crop_and_plate(tmp_path):
    values = np.full((40, 40), 25.0, dtype=np.float32)
    values[15:25, 15:25] = 55.0
    frame = ThermalFrame(values, Path("thermal.tif"))
    finding = _finding()
    artifacts = write_finding_evidence(frame, finding, tmp_path)
    assert set(artifacts) == {"annotated", "crop", "plate"}
    assert all(path.is_file() and path.stat().st_size > 0 for path in artifacts.values())
    assert finding.annotated_image_path.endswith("annotated_thermal.png")


def test_json_and_geojson_share_canonical_finding_id(tmp_path):
    finding = _finding()
    json_path = write_findings_json([finding], tmp_path / "findings.json")
    geojson_path = write_geojson([finding], tmp_path / "findings.geojson")
    assert geojson_path is not None
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    geo = json.loads(geojson_path.read_text(encoding="utf-8"))
    assert payload["findings"][0]["finding_id"] == "A-001"
    assert geo["features"][0]["id"] == "A-001"
