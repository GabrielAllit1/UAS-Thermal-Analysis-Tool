import pytest

from uas_thermal.thermal.calibration import ThermalCalibration


def test_default_calibration_is_valid():
    calibration = ThermalCalibration()
    assert calibration.emissivity == 0.95
    assert calibration.ambient_temperature_c is None


def test_ambient_temperature_is_recorded_when_known():
    calibration = ThermalCalibration(ambient_temperature_c=32.0)
    assert calibration.ambient_temperature_c == 32.0


def test_invalid_emissivity_rejected():
    with pytest.raises(ValueError):
        ThermalCalibration(emissivity=1.2)


def test_invalid_ambient_temperature_rejected():
    with pytest.raises(ValueError):
        ThermalCalibration(ambient_temperature_c=2000.0)
