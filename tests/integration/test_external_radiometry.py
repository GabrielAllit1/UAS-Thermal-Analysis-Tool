from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from uas_thermal.thermal.calibration import ThermalCalibration


def _fixture(name: str) -> Path:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not configured")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        pytest.fail(f"{name} does not point to a file: {path}")
    return path


def test_external_dji_rjpeg_decodes_to_finite_celsius_matrix():
    path = _fixture("UAS_THERMAL_DJI_RJPEG")
    from uas_thermal.sensors.dji import DjiDirpAdapter

    frame = DjiDirpAdapter().read(path, ThermalCalibration())
    finite = frame.temperature_c[np.isfinite(frame.temperature_c)]
    assert finite.size > 0
    assert frame.temperature_c.ndim == 2
    assert frame.temperature_c.shape[0] >= 256
    assert frame.temperature_c.shape[1] >= 256
    assert float(np.min(finite)) > -100.0
    assert float(np.max(finite)) < 1000.0


def test_external_kanderfirn_radiometric_geotiff_is_quantitative():
    pytest.importorskip("rasterio")
    path = _fixture("UAS_THERMAL_KANDERFIRN_TIFF")
    from uas_thermal.sensors.generic import GenericGeoTiffAdapter

    adapter = GenericGeoTiffAdapter(unit="celsius")
    diagnostics = adapter.source_diagnostics(path)
    assert diagnostics["radiometric_candidate"] is True
    sample, encoding = adapter.sample_temperature(path)
    finite = sample[np.isfinite(sample)]
    assert finite.size > 0
    assert encoding["input_unit"] == "celsius"
    assert float(np.min(finite)) > -100.0
    assert float(np.max(finite)) < 100.0
