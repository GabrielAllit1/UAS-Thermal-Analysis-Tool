import numpy as np
import pytest

from uas_thermal.application.viewer import (
    blend_rgb,
    render_temperature,
    roi_statistics,
    swipe_rgb,
    temperature_at,
)


def test_temperature_cursor_and_roi_statistics():
    values = np.arange(100, dtype=np.float32).reshape(10, 10)
    assert temperature_at(values, 3, 4) == 43.0
    stats = roi_statistics(values, 2, 2, 4, 4)
    assert stats.valid_pixels == 9
    assert stats.minimum_c == 22.0
    assert stats.maximum_c == 44.0
    assert stats.mean_c == pytest.approx(33.0)


def test_palette_render_and_isotherm_are_deterministic():
    values = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32)
    rgb, limits = render_temperature(
        values,
        palette="iron",
        minimum_c=0.0,
        maximum_c=30.0,
        isotherm_min_c=20.0,
    )
    assert rgb.shape == (2, 2, 3)
    assert rgb.dtype == np.uint8
    assert limits == (0.0, 30.0)
    assert np.array_equal(rgb[1, 0], np.array([255, 255, 0], dtype=np.uint8))


def test_blend_and_swipe_align_different_image_sizes():
    left = np.zeros((4, 6, 3), dtype=np.uint8)
    right = np.full((6, 4, 3), 200, dtype=np.uint8)
    blended = blend_rgb(left, right, opacity=0.25)
    swiped = swipe_rgb(left, right, fraction=0.5)
    assert blended.shape == (4, 4, 3)
    assert np.all(blended == 50)
    assert swiped.shape == (4, 4, 3)
    assert np.all(swiped[:, :2] == 0)
    assert np.all(swiped[:, 2:] == 200)
