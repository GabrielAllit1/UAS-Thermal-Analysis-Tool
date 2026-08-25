import numpy as np
import pytest

from uas_thermal.thermal.measurements import (
    circle_statistics,
    ellipse_statistics,
    line_statistics,
    polygon_statistics,
    rectangle_statistics,
    spot_delta,
    spot_statistics,
)
from uas_thermal.thermal.presentation import ThermalStyle, batch_render, render_with_style


def test_spot_uses_four_by_four_average_by_default():
    values = np.arange(100, dtype=np.float32).reshape(10, 10)
    stats = spot_statistics(values, 5, 5)

    assert stats.valid_pixels == 16
    assert stats.mean_c == pytest.approx(float(np.mean(values[4:8, 4:8])))


def test_spot_delta_is_second_minus_first():
    values = np.full((12, 12), 20.0, dtype=np.float32)
    values[7:11, 7:11] = 31.0

    assert spot_delta(values, (2, 2), (8, 8)) == pytest.approx(11.0)


def test_area_measurements_return_quantitative_statistics():
    values = np.arange(25 * 25, dtype=np.float32).reshape(25, 25) / 10.0

    rectangle = rectangle_statistics(values, 3, 4, 10, 12)
    circle = circle_statistics(values, 12, 12, 5)
    ellipse = ellipse_statistics(values, 12, 12, 7, 3)
    line = line_statistics(values, 2, 2, 20, 20, width_px=2)
    polygon = polygon_statistics(values, [(4, 4), (18, 4), (18, 18), (4, 18)])

    for stats in (rectangle, circle, ellipse, line, polygon):
        assert stats.valid_pixels > 0
        assert stats.minimum_c <= stats.mean_c <= stats.maximum_c
        assert stats.p95_c <= stats.maximum_c


def test_span_level_and_palette_are_visual_only():
    values = np.linspace(10.0, 80.0, 100, dtype=np.float32).reshape(10, 10)
    original = values.copy()
    style = ThermalStyle(palette="rainbow-hc", span_c=20.0, level_c=40.0)

    rgb, limits = render_with_style(values, style)

    assert limits == pytest.approx((30.0, 50.0))
    assert rgb.shape == (10, 10, 3)
    assert np.array_equal(values, original)


def test_batch_style_does_not_modify_temperature_inputs():
    first = np.arange(36, dtype=np.float32).reshape(6, 6) + 10.0
    second = first + 5.0
    originals = [first.copy(), second.copy()]

    rendered = batch_render([first, second], ThermalStyle(palette="blackhot", span_c=12, level_c=30))

    assert len(rendered) == 2
    assert all(item.shape == (6, 6, 3) for item in rendered)
    assert np.array_equal(first, originals[0])
    assert np.array_equal(second, originals[1])
