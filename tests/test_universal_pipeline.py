from pathlib import Path

import numpy as np
import pytest

from uas_thermal.application.projects import Project
from uas_thermal.application.universal_pipeline import (
    UniversalProcessingPlan,
    UniversalThermalProcessor,
)
from uas_thermal.thermal.presentation import ThermalStyle

rasterio = pytest.importorskip("rasterio")
from_origin = pytest.importorskip("rasterio.transform").from_origin


def _write_tile(path: Path, values: np.ndarray, x_origin: float) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:32617",
        transform=from_origin(x_origin, 3000000, 0.2, 0.2),
        nodata=np.nan,
    ) as dataset:
        dataset.write(values.astype(np.float32), 1)
        dataset.update_tags(THERMAL_UNIT="celsius", isCalibrated="true")


def test_universal_pipeline_stitches_analyzes_and_builds_shareable_deliverable(tmp_path):
    left = np.full((64, 64), 25.0, dtype=np.float32)
    right = np.full((64, 64), 25.0, dtype=np.float32)
    right[24:36, 20:32] = 55.0
    left_path = tmp_path / "left.tif"
    right_path = tmp_path / "right.tif"
    _write_tile(left_path, left, 500000.0)
    _write_tile(right_path, right, 500012.8)

    project = Project(name="Universal test", site="Synthetic", profile_id="generic-thermal")
    result = UniversalThermalProcessor().process(
        project,
        [left_path, right_path],
        tmp_path / "deliverables",
        plan=UniversalProcessingPlan(
            stitch_mode="on",
            orthomosaic_backend="native-geotiff",
            ai_mode="off",
            thermal_style=ThermalStyle(palette="ironbow", span_c=40.0, level_c=35.0),
        ),
    )

    assert result.orthomosaic is not None
    assert result.orthomosaic.quantitative is True
    assert result.run.artifacts
    assert result.deliverable_dir.is_dir()
    assert (result.deliverable_dir / "maps" / "thermal_orthomosaic.tif").is_file()
    assert (result.deliverable_dir / "maps" / "annotated_thermal_overview.png").is_file()
    assert (result.deliverable_dir / "report" / "inspection_report.pdf").is_file()
    assert (result.deliverable_dir / "report" / "processing_report.json").is_file()
    assert (result.deliverable_dir / "viewer" / "index.html").is_file()
    assert (result.deliverable_dir / "inspection_manifest.json").is_file()
