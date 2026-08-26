from types import SimpleNamespace

import numpy as np

from uas_thermal.thermal.evidence import (
    EvidenceConfig,
    compute_evidence_layers,
    compute_illumination_context,
)
from uas_thermal.thermal.evidence_validation import evaluate_residual_ablation


def test_evidence_layers_preserve_temperature_authority_and_expose_detector_support():
    values = np.full((64, 64), 24.0, dtype=np.float32)
    values[22:34, 24:36] = 48.0
    finding = SimpleNamespace(bbox=(24, 22, 35, 33), center_x=30, center_y=28)

    layers = compute_evidence_layers(values, findings=[finding])

    assert np.array_equal(layers.temperature_c, values)
    assert float(np.nanmax(layers.local_delta_c)) > 8.0
    assert int(np.count_nonzero(layers.candidate_mask)) == 144
    assert int(np.count_nonzero(layers.finding_mask)) == 144
    assert float(np.nanmax(layers.structural_residual_c)) > 0.0
    assert float(np.nanmax(layers.texture_curvature_c)) > 0.0


def test_finding_mask_supports_tiled_global_coordinate_offsets():
    values = np.full((32, 32), 25.0, dtype=np.float32)
    finding = SimpleNamespace(bbox=(110, 210, 114, 214), center_x=112, center_y=212)

    layers = compute_evidence_layers(
        values,
        findings=[finding],
        finding_offset=(100, 200),
    )

    assert int(np.count_nonzero(layers.finding_mask)) == 25
    assert layers.finding_mask[10:15, 10:15].all()


def test_rgb_illumination_context_is_supplemental_and_detects_local_shadow():
    rgb = np.full((20, 20, 3), 220, dtype=np.uint8)
    rgb[7:13, 7:13] = 50

    context = compute_illumination_context(rgb, radius=3)

    assert context.brightness.shape == rgb.shape[:2]
    assert float(np.max(context.shadow_score)) > 0.5
    assert np.all((context.shadow_score >= 0.0) & (context.shadow_score <= 1.0))


def test_residual_ablation_is_evaluation_only_and_reports_both_masks():
    values = np.full((64, 64), 24.0, dtype=np.float32)
    truth = np.zeros((64, 64), dtype=bool)
    values[22:34, 24:36] = 48.0
    truth[22:34, 24:36] = True

    result = evaluate_residual_ablation(
        values,
        truth,
        config=EvidenceConfig(minimum_delta_c=8.0),
    )

    assert result.baseline.precision == 1.0
    assert result.baseline.recall == 1.0
    assert result.residual_gated.false_positive_px == 0
    assert np.isfinite(result.residual_threshold_c)
