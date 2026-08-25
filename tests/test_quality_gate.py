from pathlib import Path

import numpy as np

from uas_thermal.inspections.models import QualityStatus
from uas_thermal.sensors.base import ThermalFrame
from uas_thermal.thermal.calibration import ThermalCalibration
from uas_thermal.thermal.quality import evaluate_radiometric_quality


def test_quality_gate_accepts_finite_radiometric_frame_with_warnings():
    frame = ThermalFrame(np.full((20, 20), 30.0), Path("thermal.tif"))
    result = evaluate_radiometric_quality(frame, ThermalCalibration())
    assert result.accepted
    assert result.status is QualityStatus.PASS_WITH_WARNINGS
    assert result.metrics["valid_pixels"] == 400


def test_quality_gate_rejects_display_only_source_metadata():
    frame = ThermalFrame(
        np.full((20, 20), 30.0),
        Path("rendered.tif"),
        metadata={"tags": {"isCalibrated": "False"}, "radiometric_candidate": False},
    )
    result = evaluate_radiometric_quality(frame, ThermalCalibration())
    assert result.status is QualityStatus.REJECTED
    assert not result.accepted
    assert any("uncalibrated" in reason for reason in result.reasons)


def test_quality_gate_rejects_mostly_invalid_temperature_data():
    values = np.full((20, 20), np.nan)
    values[:3, :] = 25.0
    frame = ThermalFrame(values, Path("bad.tif"))
    result = evaluate_radiometric_quality(frame, ThermalCalibration())
    assert result.status is QualityStatus.REJECTED
    assert result.metrics["valid_fraction"] < 0.70
