from pathlib import Path

import numpy as np

from uas_thermal.application.projects import Project
from uas_thermal.application.workflows import AnalysisWorkflow
from uas_thermal.sensors.base import ThermalFrame, ThermalSensorAdapter
from uas_thermal.sensors.registry import AdapterRegistry
from uas_thermal.thermal.anomaly_detection import DetectionConfig
from uas_thermal.thermal.calibration import ThermalCalibration


class FakeAdapter(ThermalSensorAdapter):
    name = "fake"

    def can_read(self, path: Path) -> bool:
        return True

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        data = np.full((10, 10), 20.0)
        data[4:7, 4:7] = 45.0
        return ThermalFrame(
            data,
            path,
            crs="EPSG:4326",
            transform=(0.01, 0.0, -82.0, 0.0, -0.01, 28.0),
        )


def test_workflow_attaches_project_and_georeferences_findings():
    workflow = AnalysisWorkflow(
        AdapterRegistry([FakeAdapter()]),
        DetectionConfig(minimum_delta_c=8.0, minimum_area_px=4),
    )
    result = workflow.analyze("sample.tif", project=Project(name="Demo"))
    assert result.project["name"] == "Demo"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.longitude is not None
    assert finding.latitude is not None
    assert -82.0 < finding.longitude < -81.8
    assert 27.8 < finding.latitude < 28.0
