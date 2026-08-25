import numpy as np

from uas_thermal.sensors.generic import masked_band_to_float, thermal_preview


def test_masked_integer_band_converts_nodata_to_nan() -> None:
    values = np.ma.array(
        np.array([[2500, 2600], [0, 2700]], dtype=np.uint16),
        mask=[[False, False], [True, False]],
    )

    result = masked_band_to_float(values)

    assert result.dtype == np.float32
    assert np.isnan(result[1, 0])
    assert result[0, 0] == 2500.0


def test_thermal_preview_handles_nonfinite_pixels() -> None:
    values = np.array([[20.0, np.nan], [30.0, np.inf]])

    preview = thermal_preview(values)

    assert preview.dtype == np.uint8
    assert preview.shape == (2, 2, 3)
