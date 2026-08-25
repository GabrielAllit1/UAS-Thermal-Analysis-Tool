from pathlib import Path

import numpy as np
import pytest

from uas_thermal.application.projects import Project
from uas_thermal.application.workflows import AnalysisWorkflow
from uas_thermal.sensors.generic import GenericGeoTiffAdapter
from uas_thermal.sensors.geotiff_tiles import TiledGeoTiffReader
from uas_thermal.thermal.calibration import ThermalCalibration

rasterio = pytest.importorskip("rasterio")
from_origin = pytest.importorskip("rasterio.transform").from_origin


def _write_thermal(path: Path, values: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:32617",
        transform=from_origin(500000, 3000000, 0.1, 0.1),
    ) as dataset:
        dataset.write(values.astype(np.float32), 1)
        dataset.update_tags(THERMAL_UNIT="celsius", isCalibrated="true")


def test_tiled_reader_core_pixels_cover_source_once(tmp_path):
    path = tmp_path / "thermal.tif"
    values = np.arange(70 * 90, dtype=np.float32).reshape(70, 90) / 100.0 + 20.0
    _write_thermal(path, values)

    reader = TiledGeoTiffReader(GenericGeoTiffAdapter(unit="auto"), tile_size=32, overlap=8)
    tiles = list(reader.iter_tiles(path, ThermalCalibration()))

    coverage = np.zeros(values.shape, dtype=np.int16)
    reconstructed = np.zeros(values.shape, dtype=np.float32)
    for tile in tiles:
        core = tile.core_temperature()
        bounds = tile.bounds
        y0, y1 = bounds.core_row_off, bounds.core_row_off + bounds.core_height
        x0, x1 = bounds.core_col_off, bounds.core_col_off + bounds.core_width
        coverage[y0:y1, x0:x1] += 1
        reconstructed[y0:y1, x0:x1] = core

    assert np.all(coverage == 1)
    assert np.allclose(reconstructed, values)


def test_tiled_reader_preview_and_exact_pixel_probe(tmp_path):
    path = tmp_path / "thermal.tif"
    values = np.full((80, 120), 25.0, dtype=np.float32)
    values[41, 73] = 82.5
    _write_thermal(path, values)

    reader = TiledGeoTiffReader(GenericGeoTiffAdapter(), tile_size=32, overlap=8)
    preview = reader.preview_frame(path, ThermalCalibration(), max_edge=60)

    assert max(preview.temperature_c.shape) <= 60
    assert preview.metadata["preview_only"] is True
    assert reader.temperature_at(path, 73, 41) == pytest.approx(82.5)


def test_analysis_workflow_routes_oversized_radiometry_through_tiles(tmp_path, monkeypatch):
    import uas_thermal.sensors.generic as generic

    path = tmp_path / "thermal-large-route.tif"
    values = np.full((96, 128), 25.0, dtype=np.float32)
    values[35:55, 50:75] = 48.0
    _write_thermal(path, values)
    monkeypatch.setattr(generic, "_MAX_IN_MEMORY_PIXELS", 1)

    artifact = AnalysisWorkflow.default().analyze_artifact(
        path,
        calibration=ThermalCalibration(),
        adapter_name="generic-geotiff",
        project=Project(name="Tiled route"),
    )

    assert artifact.result.metadata["tiled_analysis"] is True
    assert artifact.result.metadata["full_raster_statistics"] is True
    assert artifact.frame.metadata["preview_only"] is True
    assert artifact.result.statistics.valid_pixels == values.size
    assert artifact.result.findings
    assert max(item.max_temperature_c for item in artifact.result.findings) == pytest.approx(48.0)
