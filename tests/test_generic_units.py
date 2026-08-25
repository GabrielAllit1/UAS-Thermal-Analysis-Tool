import numpy as np
import pytest

from uas_thermal.sensors.generic import temperature_to_celsius


def test_kelvin_conversion():
    result = temperature_to_celsius(np.array([[273.15, 300.15]]), "kelvin")
    assert result[0, 0] == pytest.approx(0.0)
    assert result[0, 1] == pytest.approx(27.0)


def test_decikelvin_auto_conversion():
    result = temperature_to_celsius(np.array([[2900.0, 3000.0]]), "auto")
    assert result[0, 0] == pytest.approx(16.85)
    assert result[0, 1] == pytest.approx(26.85)


def test_auto_rejects_ambiguous_raw_counts():
    with pytest.raises(ValueError, match="Unable to infer"):
        temperature_to_celsius(np.array([[8000.0, 9000.0]]), "auto")
