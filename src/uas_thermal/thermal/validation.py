from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .anomaly_detection import DetectionConfig, analyze_temperature


@dataclass(frozen=True, slots=True)
class SyntheticCase:
    name: str
    temperature_c: np.ndarray
    truth_mask: np.ndarray


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    true_positive_px: int
    false_positive_px: int
    false_negative_px: int
    precision: float
    recall: float
    iou: float
    delta_t_error_c: float | None


def synthetic_cases() -> tuple[SyntheticCase, ...]:
    cases: list[SyntheticCase] = []

    uniform = np.full((48, 48), 25.0, dtype=np.float32)
    truth = np.zeros_like(uniform, dtype=bool)
    uniform[18:28, 19:29] = 45.0
    truth[18:28, 19:29] = True
    cases.append(SyntheticCase("uniform_hotspot", uniform, truth))

    gradient = np.tile(np.linspace(20.0, 38.0, 64, dtype=np.float32), (64, 1))
    truth = np.zeros_like(gradient, dtype=bool)
    gradient[24:34, 28:38] += 16.0
    truth[24:34, 28:38] = True
    cases.append(SyntheticCase("gradient_hotspot", gradient, truth))

    warm = np.full((48, 48), 55.0, dtype=np.float32)
    truth = np.zeros_like(warm, dtype=bool)
    warm[16:26, 16:26] = 68.0
    truth[16:26, 16:26] = True
    cases.append(SyntheticCase("globally_warm_scene", warm, truth))

    spike = np.full((32, 32), 25.0, dtype=np.float32)
    truth = np.zeros_like(spike, dtype=bool)
    spike[15, 15] = 90.0
    cases.append(SyntheticCase("single_pixel_spike", spike, truth))

    edge = np.full((40, 40), 25.0, dtype=np.float32)
    truth = np.zeros_like(edge, dtype=bool)
    edge[0:2, 8:28] = 36.0
    cases.append(SyntheticCase("edge_artifact", edge, truth))

    nodata = np.full((48, 48), 25.0, dtype=np.float32)
    truth = np.zeros_like(nodata, dtype=bool)
    nodata[:6, :] = np.nan
    nodata[20:30, 20:30] = 45.0
    truth[20:30, 20:30] = True
    cases.append(SyntheticCase("nodata_boundary", nodata, truth))

    two = np.full((64, 64), 24.0, dtype=np.float32)
    truth = np.zeros_like(two, dtype=bool)
    two[10:18, 12:20] = 43.0
    two[40:50, 42:54] = 50.0
    truth[10:18, 12:20] = True
    truth[40:50, 42:54] = True
    cases.append(SyntheticCase("two_anomalies", two, truth))

    weak = np.full((48, 48), 25.0, dtype=np.float32)
    truth = np.zeros_like(weak, dtype=bool)
    weak[18:28, 18:28] = 29.0
    cases.append(SyntheticCase("weak_anomaly", weak, truth))

    broad = np.full((80, 80), 25.0, dtype=np.float32)
    truth = np.zeros_like(broad, dtype=bool)
    broad[20:55, 22:58] = 42.0
    truth[20:55, 22:58] = True
    cases.append(SyntheticCase("broad_warm_component", broad, truth))
    return tuple(cases)


def finding_mask(shape: tuple[int, int], findings) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    for finding in findings:
        if finding.bbox is None:
            mask[finding.center_y, finding.center_x] = True
            continue
        left, top, right, bottom = finding.bbox
        mask[top : bottom + 1, left : right + 1] = True
    return mask


def evaluate_case(
    case: SyntheticCase,
    config: DetectionConfig | None = None,
) -> ValidationMetrics:
    outcome = analyze_temperature(case.temperature_c, config=config)
    predicted = finding_mask(case.truth_mask.shape, outcome.findings)
    truth = case.truth_mask
    tp = int(np.count_nonzero(predicted & truth))
    fp = int(np.count_nonzero(predicted & ~truth))
    fn = int(np.count_nonzero(~predicted & truth))
    precision = tp / (tp + fp) if tp + fp else (1.0 if not np.any(truth) else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    union = int(np.count_nonzero(predicted | truth))
    iou = tp / union if union else 1.0
    expected_delta = None
    if np.any(truth):
        inside = case.temperature_c[truth]
        outside = case.temperature_c[~truth & np.isfinite(case.temperature_c)]
        if inside.size and outside.size:
            expected_delta = float(np.max(inside) - np.median(outside))
    estimated_delta = max((item.delta_temperature_c for item in outcome.findings), default=None)
    error = None
    if expected_delta is not None and estimated_delta is not None:
        error = abs(estimated_delta - expected_delta)
    return ValidationMetrics(tp, fp, fn, precision, recall, iou, error)
