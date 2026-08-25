import numpy as np

from uas_thermal.inspections.models import Confidence
from uas_thermal.thermal.anomaly_detection import DetectionConfig, analyze_temperature
from uas_thermal.thermal.validation import synthetic_cases


def _case(name):
    return next(item for item in synthetic_cases() if item.name == name)


def test_gradient_hotspot_uses_local_reference_without_gradient_false_positive():
    case = _case("gradient_hotspot")
    outcome = analyze_temperature(
        case.temperature_c,
        DetectionConfig(minimum_delta_c=6.0, minimum_area_px=20),
    )
    assert len(outcome.findings) == 1
    finding = outcome.findings[0]
    assert finding.reference_method == "surrounding-ring-median"
    assert finding.delta_temperature_c > 10.0
    assert finding.bbox is not None
    assert finding.hotspot_x is not None
    assert finding.hotspot_y is not None


def test_globally_warm_scene_can_still_detect_local_anomaly():
    case = _case("globally_warm_scene")
    outcome = analyze_temperature(
        case.temperature_c,
        DetectionConfig(minimum_delta_c=8.0, minimum_area_px=20),
    )
    assert len(outcome.findings) == 1
    assert outcome.findings[0].baseline_temperature_c == 55.0


def test_single_pixel_spike_is_suppressed_with_reason():
    case = _case("single_pixel_spike")
    outcome = analyze_temperature(
        case.temperature_c,
        DetectionConfig(minimum_delta_c=8.0, minimum_area_px=5),
    )
    assert outcome.findings == []
    assert any(item.reason == "SINGLE_PIXEL_SPIKE" for item in outcome.suppressions)


def test_two_independent_anomalies_remain_separate():
    case = _case("two_anomalies")
    outcome = analyze_temperature(
        case.temperature_c,
        DetectionConfig(minimum_delta_c=8.0, minimum_area_px=20),
    )
    assert len(outcome.findings) == 2
    assert {item.finding_id for item in outcome.findings} == {"A-001", "A-002"}
    assert all(item.confidence in set(Confidence) for item in outcome.findings)


def test_weak_anomaly_is_not_promoted_to_finding():
    case = _case("weak_anomaly")
    outcome = analyze_temperature(case.temperature_c)
    assert outcome.findings == []
