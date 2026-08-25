import numpy as np

from uas_thermal.inspections.models import Severity
from uas_thermal.thermal.anomaly_detection import DetectionConfig, detect_anomalies


def test_detects_connected_hot_region_from_background_delta():
    data = np.full((20, 20), 25.0)
    data[5:10, 6:11] = 45.0
    findings = detect_anomalies(data, DetectionConfig(minimum_delta_c=8.0, minimum_area_px=10))
    assert len(findings) == 1
    assert findings[0].area_px == 25
    assert findings[0].severity is Severity.MODERATE


def test_small_regions_are_filtered():
    data = np.full((10, 10), 20.0)
    data[2:4, 2:4] = 50.0
    findings = detect_anomalies(data, DetectionConfig(minimum_delta_c=5.0, minimum_area_px=5))
    assert findings == []
