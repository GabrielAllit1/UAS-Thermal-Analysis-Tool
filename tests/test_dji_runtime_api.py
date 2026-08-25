from ctypes import c_int32

import pytest

from uas_thermal.sensors.dji import DjiDirpAdapter
from uas_thermal.thermal.calibration import ThermalCalibration


class FakeFunction:
    def __init__(self):
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return 0


class FakeDirpRuntime:
    def __init__(self):
        self.dirp_create_from_rjpeg = FakeFunction()
        self.dirp_destroy = FakeFunction()
        self.dirp_get_rjpeg_resolution = FakeFunction()
        self.dirp_set_measurement_params = FakeFunction()
        self.dirp_set_pseudo_color = FakeFunction()
        self.dirp_measure_ex = FakeFunction()
        self.dirp_process = FakeFunction()


def test_dji_runtime_binds_actual_rjpeg_api_symbols():
    adapter = DjiDirpAdapter()
    runtime = FakeDirpRuntime()

    functions = adapter._bind_runtime(runtime)

    assert "dirp_create_from_rjpeg" in functions
    assert "dirp_create" not in functions
    assert runtime.dirp_create_from_rjpeg.restype is c_int32
    assert runtime.dirp_measure_ex.restype is c_int32


def test_dji_measurement_params_convert_humidity_fraction_to_percent():
    params = DjiDirpAdapter._measurement_params(
        ThermalCalibration(
            emissivity=0.95,
            distance_m=5.0,
            relative_humidity=0.50,
            reflected_temperature_c=20.0,
        )
    )

    assert params.distance == pytest.approx(5.0)
    assert params.humidity == pytest.approx(50.0)
    assert params.emissivity == pytest.approx(0.95)
    assert params.reflection == pytest.approx(20.0)


def test_dji_palette_values_match_sdk_enum():
    assert DjiDirpAdapter("WHITEHOT")._palette_code() == 0
    assert DjiDirpAdapter("IRONRED")._palette_code() == 2
    assert DjiDirpAdapter("BLACKHOT")._palette_code() == 9


def test_dji_rejects_sdk_out_of_range_humidity():
    with pytest.raises(ValueError, match="humidity"):
        DjiDirpAdapter._measurement_params(
            ThermalCalibration(relative_humidity=0.10)
        )


def test_dji_source_diagnostics_flags_exported_jpeg(tmp_path):
    source = tmp_path / "thermal_export_example.jpg"
    source.write_bytes(b"\xff\xd8payload\xff\xd9")

    diagnostics = DjiDirpAdapter.source_diagnostics(source)

    assert diagnostics["file_size_bytes"] == len(b"\xff\xd8payload\xff\xd9")
    assert diagnostics["jpeg_signature"] is True
    assert diagnostics["export_like_filename"] is True
