from uas_thermal.sensors.generic import GenericGeoTiffAdapter, _radiometric_classification


def test_uncalibrated_multiband_uint8_is_not_radiometric() -> None:
    result = _radiometric_classification(
        tags={"isCalibrated": "False", "name": "Radiometric_Thermal"},
        count=4,
        dtype="uint8",
        pixel_count=96_150 * 45_272,
    )

    assert result["radiometric_candidate"] is False
    assert result["is_calibrated"] is False
    assert result["requires_tiled_processing"] is True
    assert "isCalibrated=False" in result["radiometric_reasons"][0]


def test_untagged_single_band_uint8_is_rejected_as_ambiguous() -> None:
    result = _radiometric_classification(
        tags={},
        count=1,
        dtype="uint8",
        pixel_count=640 * 512,
    )

    assert result["radiometric_candidate"] is False
    assert any("8-bit scalar raster" in reason for reason in result["radiometric_reasons"])


def test_explicitly_encoded_single_band_uint8_can_be_radiometric() -> None:
    result = _radiometric_classification(
        tags={"THERMAL_UNIT": "celsius"},
        count=1,
        dtype="uint8",
        pixel_count=640 * 512,
    )

    assert result["radiometric_candidate"] is True


def test_explicit_adapter_configuration_can_authorize_untagged_uint8() -> None:
    adapter = GenericGeoTiffAdapter(unit="celsius")
    result = _radiometric_classification(
        tags={},
        count=1,
        dtype="uint8",
        pixel_count=640 * 512,
        configured_radiometry=adapter.has_configured_radiometry,
    )

    assert adapter.has_configured_radiometry is True
    assert result["radiometric_candidate"] is True


def test_large_single_band_temperature_raster_requires_tiling() -> None:
    result = _radiometric_classification(
        tags={"THERMAL_UNIT": "kelvin", "isCalibrated": "True"},
        count=1,
        dtype="uint16",
        pixel_count=100_000_000,
    )

    assert result["radiometric_candidate"] is True
    assert result["requires_tiled_processing"] is True


def test_small_single_band_raster_can_use_full_frame_path() -> None:
    result = _radiometric_classification(
        tags={"THERMAL_UNIT": "celsius"},
        count=1,
        dtype="float32",
        pixel_count=640 * 512,
    )

    assert result["radiometric_candidate"] is True
    assert result["requires_tiled_processing"] is False
