from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .evidence import EvidenceConfig, compute_evidence_layers


@dataclass(frozen=True, slots=True)
class MaskMetrics:
    precision: float
    recall: float
    iou: float
    true_positive_px: int
    false_positive_px: int
    false_negative_px: int


@dataclass(frozen=True, slots=True)
class EvidenceAblationResult:
    baseline: MaskMetrics
    residual_gated: MaskMetrics
    residual_threshold_c: float


def _metrics(predicted: np.ndarray, truth: np.ndarray) -> MaskMetrics:
    predicted = np.asarray(predicted, dtype=bool)
    truth = np.asarray(truth, dtype=bool)
    if predicted.shape != truth.shape:
        raise ValueError("predicted and truth masks must have the same shape")
    tp = int(np.count_nonzero(predicted & truth))
    fp = int(np.count_nonzero(predicted & ~truth))
    fn = int(np.count_nonzero(~predicted & truth))
    precision = tp / (tp + fp) if tp + fp else (1.0 if not np.any(truth) else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    union = int(np.count_nonzero(predicted | truth))
    iou = tp / union if union else 1.0
    return MaskMetrics(precision, recall, iou, tp, fp, fn)


def evaluate_residual_ablation(
    temperature_c: np.ndarray,
    truth_mask: np.ndarray,
    *,
    config: EvidenceConfig | None = None,
    residual_quantile: float = 0.50,
) -> EvidenceAblationResult:
    """Compare existing pre-morphology candidates with an experimental residual-support gate.

    This is an evaluation hook only. It does not alter canonical detector behavior.
    """

    if not 0.0 <= residual_quantile <= 1.0:
        raise ValueError("residual_quantile must be between 0 and 1")
    layers = compute_evidence_layers(temperature_c, config=config)
    baseline = layers.candidate_mask
    residual = np.abs(layers.structural_residual_c)
    samples = residual[baseline & np.isfinite(residual)]
    threshold = float(np.quantile(samples, residual_quantile)) if samples.size else float("inf")
    assisted = baseline & (residual >= threshold)
    return EvidenceAblationResult(
        baseline=_metrics(baseline, truth_mask),
        residual_gated=_metrics(assisted, truth_mask),
        residual_threshold_c=threshold,
    )
