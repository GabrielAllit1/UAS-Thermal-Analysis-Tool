import numpy as np

from uas_thermal.geospatial.display import DisplayRaster, _display_channel, _preview_shape


def test_preview_shape_bounds_large_raster() -> None:
    height, width = _preview_shape(96150, 45272, 1600)

    assert width == 1600
    assert height < 1600
    assert height > 0


def test_uint8_display_channel_preserves_values_and_masks() -> None:
    values = np.ma.array(
        np.array([[10, 20], [30, 40]], dtype=np.uint8),
        mask=[[False, True], [False, False]],
    )

    result = _display_channel(values)

    assert result.dtype == np.uint8
    assert result[0, 0] == 10
    assert result[0, 1] == 0


def test_display_raster_rejects_non_rgb_shape(tmp_path) -> None:
    try:
        DisplayRaster(source=tmp_path / "x.tif", rgb=np.zeros((10, 10), dtype=np.uint8))
    except ValueError as exc:
        assert "HxWx3" in str(exc)
    else:
        raise AssertionError("DisplayRaster accepted a non-RGB array")
