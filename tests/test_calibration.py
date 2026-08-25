import pytest

from uas_thermal.thermal.calibration import ThermalCalibration


def test_default_calibration_is_valid():
    calibration = ThermalCalibration()
    assert calibration.emissivity == 0.95


def test_invalid_emissivity_rejected():
    with pytest.raises(ValueError):
        ThermalCalibration(emissivity=1.2)
