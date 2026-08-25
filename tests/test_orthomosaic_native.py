from pathlib import Path

import numpy as np
import pytest

from uas_thermal.orthomosaic import NativeGeoTiffMosaicBackend, OrthomosaicRequest

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
        transform=from_origin(x_origin, 3000000, 1.0, 1.0),
        nodata=np.nan,
    ) as dataset:
        dataset.write(values.astype(np.float32), 1)
        dataset.update_tags(THERMAL_UNIT="celsius", isCalibrated="true")


def test_native_mosaic_preserves_quantitative_celsius_values(tmp_path):
    left = tmp_path / "left.tif"
    right = tmp_path / "right.tif"
    _write_tile(left, np.full((8, 10), 20.0, dtype=np.float32), 500000)
    _write_tile(right, np.full((8, 10), 35.0, dtype=np.float32), 500010)

    result = NativeGeoTiffMosaicBackend(mem_limit_mb=64).process(
        OrthomosaicRequest(
            sources=(left, right),
            output_dir=tmp_path / "out",
            project_name="test",
        )
    )

    assert result.quantitative is True
    assert result.temperature_unit == "celsius"
    with rasterio.open(result.orthomosaic) as dataset:
        values = dataset.read(1)
        assert values.shape == (8, 20)
        assert np.allclose(values[:, :10], 20.0)
        assert np.allclose(values[:, 10:], 35.0)
        assert dataset.tags()["THERMAL_UNIT"] == "celsius"
        assert dataset.tags()["isCalibrated"] == "true"
