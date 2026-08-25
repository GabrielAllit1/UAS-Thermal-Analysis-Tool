import numpy as np

from uas_thermal.thermal.statistics import summarize_temperature


def test_temperature_statistics_ignore_nan():
    stats = summarize_temperature(np.array([[10.0, 20.0], [30.0, np.nan]]))
    assert stats.minimum_c == 10.0
    assert stats.maximum_c == 30.0
    assert stats.valid_pixels == 3
