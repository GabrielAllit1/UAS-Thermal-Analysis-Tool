from types import SimpleNamespace

import numpy as np
import pytest

from uas_thermal.reporting.evidence_cube import band_manifest, write_frame_evidence_cube
from uas_thermal.sensors.base import ThermalFrame

rasterio = pytest.importorskip("rasterio")


def test_evidence_cube_marks_temperature_as_only_radiometric_authority(tmp_path):
    values = np.full((64, 64), 24.0, dtype=np.float32)
    values[22:34, 24:36] = 48.0
    frame = ThermalFrame(
        temperature_c=values,
        source=tmp_path / "source.tif",
        crs="EPSG:4326",
        transform=(0.0001, 0.0, -82.0, 0.0, -0.0001, 28.0),
    )
    finding = SimpleNamespace(bbox=(24, 22, 35, 33), center_x=30, center_y=28)
    output = tmp_path / "thermal_evidence.tif"

    result = write_frame_evidence_cube(frame, [finding], output)

    assert result.path == output
    assert result.georeferenced is True
    assert result.tiled is False
    with rasterio.open(output) as dataset:
        assert dataset.count == 9
        assert dataset.tags()["TEMPERATURE_AUTHORITY_BAND"] == "1"
        assert dataset.tags(1)["AUTHORITY"] == "radiometric"
        for band in range(2, 10):
            assert dataset.tags(band)["AUTHORITY"] == "derived"
        assert float(np.max(dataset.read(1))) == 48.0
        assert float(np.max(dataset.read(3))) > 8.0
        assert int(np.sum(dataset.read(7))) == 144

    manifest = band_manifest()
    assert manifest[0]["name"] == "temperature_c"
    assert manifest[0]["authority"] == "radiometric"
    assert manifest[7]["experimental"] is True
    assert manifest[8]["experimental"] is True
