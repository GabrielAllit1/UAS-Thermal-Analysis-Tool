from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from ..inspections.models import Confidence, Finding, SuppressionRecord
from ..inspections.profiles import InspectionProfile
from ..inspections.severity import SeverityPolicy


@dataclass(frozen=True, slots=True)
class DetectionConfig:
    minimum_delta_c: float = 8.0
    minimum_area_px: int = 25
    absolute_threshold_c: float | None = None
    connectivity: int = 8
    local_radii: tuple[int, ...] = (3, 7)
    inner_reference_radius: int = 1
    minimum_scale_support: int = 1
    robust_z_threshold: float = 3.5
    edge_suppression: bool = True
    edge_margin_px: int = 1
    minimum_fill_ratio: float = 0.20

    @classmethod
    def from_profile(cls, profile: InspectionProfile) -> DetectionConfig:
        return cls(
            minimum_delta_c=profile.minimum_delta_c,
            minimum_area_px=profile.minimum_area_px,
            absolute_threshold_c=profile.absolute_threshold_c,
            local_radii=profile.local_radii,
            minimum_scale_support=profile.minimum_scale_support,
            robust_z_threshold=profile.robust_z_threshold,
            edge_suppression=profile.edge_suppression,
        )


@dataclass(slots=True)
class DetectionOutcome:
    findings: list[Finding] = field(default_factory=list)
    suppressions: list[SuppressionRecord] = field(default_factory=list)
    diagnostics: dict[str, float | int | str | bool] = field(default_factory=dict)


def _components(mask: np.ndarray, connectivity: int) -> list[list[tuple[int, int]]]:
    rows, cols = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    if connectivity == 4:
        offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
    elif connectivity == 8:
        offsets = tuple(
            (dr, dc)
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            if dr or dc
        )
    else:
        raise ValueError("connectivity must be 4 or 8")

    found: list[list[tuple[int, int]]] = []
    for row, col in zip(*np.nonzero(mask), strict=True):
        if seen[row, col]:
            continue
        queue = deque([(int(row), int(col))])
        seen[row, col] = True
        component: list[tuple[int, int]] = []
        while queue:
            r, c = queue.popleft()
            component.append((r, c))
            for dr, dc in offsets:
                nr, nc = r + dr, c + dc
                if (
                    0 <= nr < rows
                    and 0 <= nc < cols
                    and mask[nr, nc]
                    and not seen[nr, nc]
                ):
                    seen[nr, nc] = True
                    queue.append((nr, nc))
        found.append(component)
    return found


def _box_sum_count(values: np.ndarray, radius: int) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(values)
    data = np.where(finite, values, 0.0).astype(np.float32, copy=False)
    valid = finite.astype(np.float32)
    if radius <= 0:
        return data, valid
    data = np.pad(data, radius, mode="reflect")
    valid = np.pad(valid, radius, mode="reflect")

    def integral(array: np.ndarray) -> np.ndarray:
        padded = np.pad(array, ((1, 0), (1, 0)), mode="constant")
        return padded.cumsum(axis=0).cumsum(axis=1)

    sums_i = integral(data)
    count_i = integral(valid)
    height, width = values.shape
    size = radius * 2 + 1
    sums = (
        sums_i[size : size + height, size : size + width]
        - sums_i[:height, size : size + width]
        - sums_i[size : size + height, :width]
        + sums_i[:height, :width]
    )
    counts = (
        count_i[size : size + height, size : size + width]
        - count_i[:height, size : size + width]
        - count_i[size : size + height, :width]
        + count_i[:height, :width]
    )
    return sums, counts


def _annular_reference(values: np.ndarray, inner: int, outer: int) -> np.ndarray:
    if outer <= inner:
        raise ValueError("outer reference radius must exceed inner radius")
    outer_sum, outer_count = _box_sum_count(values, outer)
    inner_sum, inner_count = _box_sum_count(values, inner)
    ring_sum = outer_sum - inner_sum
    ring_count = outer_count - inner_count
    return np.divide(
        ring_sum,
        ring_count,
        out=np.full(values.shape, np.nan, dtype=np.float32),
        where=ring_count > 0,
    )


def _component_reference(
    values: np.ndarray,
    rr: np.ndarray,
    cc: np.ndarray,
    margin: int,
) -> tuple[float | None, int]:
    row0, row1 = int(np.min(rr)), int(np.max(rr))
    col0, col1 = int(np.min(cc)), int(np.max(cc))
    top = max(0, row0 - margin)
    bottom = min(values.shape[0], row1 + margin + 1)
    left = max(0, col0 - margin)
    right = min(values.shape[1], col1 + margin + 1)
    region = values[top:bottom, left:right]
    ring = np.ones(region.shape, dtype=bool)
    ring[row0 - top : row1 - top + 1, col0 - left : col1 - left + 1] = False
    samples = region[ring & np.isfinite(region)]
    if samples.size < 8:
        return None, int(samples.size)
    return float(np.median(samples)), int(samples.size)


def _robust_scene(values: np.ndarray) -> tuple[float, float, float]:
    finite = values[np.isfinite(values)]
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    scale = max(1.4826 * mad, float(np.std(finite)) * 0.25, 0.25)
    p90 = float(np.percentile(finite, 90))
    return median, scale, p90


def _confidence(
    *,
    delta_c: float,
    minimum_delta_c: float,
    area_px: int,
    minimum_area_px: int,
    scale_support: int,
    scale_count: int,
    fill_ratio: float,
    robust_score: float,
    touches_edge: bool,
) -> tuple[Confidence, dict[str, float | str | bool]]:
    contrast_score = min(1.0, delta_c / max(minimum_delta_c * 2.0, 0.1))
    area_score = min(1.0, area_px / max(minimum_area_px * 2.0, 1))
    scale_score = scale_support / max(scale_count, 1)
    coherence_score = min(1.0, max(0.0, fill_ratio))
    robust_support = min(1.0, max(0.0, robust_score / 6.0))
    edge_penalty = 0.15 if touches_edge else 0.0
    score = (
        0.35 * contrast_score
        + 0.20 * area_score
        + 0.20 * scale_score
        + 0.15 * coherence_score
        + 0.10 * robust_support
        - edge_penalty
    )
    if score >= 0.75:
        level = Confidence.HIGH
    elif score >= 0.50:
        level = Confidence.MEDIUM
    else:
        level = Confidence.LOW
    return level, {
        "internal_score": round(float(score), 4),
        "thermal_contrast": round(float(contrast_score), 4),
        "region_support": round(float(area_score), 4),
        "scale_persistence": round(float(scale_score), 4),
        "spatial_coherence": round(float(coherence_score), 4),
        "robust_scene_support": round(float(robust_support), 4),
        "touches_edge": touches_edge,
    }


def analyze_temperature(
    temperature_c: np.ndarray,
    config: DetectionConfig | None = None,
    severity_policy: SeverityPolicy | None = None,
    profile: InspectionProfile | None = None,
) -> DetectionOutcome:
    """Contextual, explainable thermal candidate detection and characterization."""

    config = config or (DetectionConfig.from_profile(profile) if profile else DetectionConfig())
    severity_policy = severity_policy or SeverityPolicy(
        moderate_delta_c=profile.moderate_delta_c if profile else 15.0,
        critical_delta_c=profile.critical_delta_c if profile else 30.0,
    )
    values = np.asarray(temperature_c, dtype=np.float32)
    finite_values = values[np.isfinite(values)]
    if finite_values.size == 0:
        return DetectionOutcome(diagnostics={"valid_pixels": 0})
    if config.minimum_area_px <= 0 or config.minimum_delta_c <= 0:
        raise ValueError("minimum_area_px and minimum_delta_c must be positive")
    if not config.local_radii:
        raise ValueError("local_radii must not be empty")

    scene_median, robust_scale, scene_p90 = _robust_scene(values)
    local_deltas: list[np.ndarray] = []
    for radius in config.local_radii:
        reference = _annular_reference(values, config.inner_reference_radius, radius)
        local_deltas.append(values - reference)
    stack = np.stack(local_deltas, axis=0)
    peak_delta = np.nanmax(stack, axis=0)
    scale_support = np.sum(stack >= config.minimum_delta_c * 0.75, axis=0)
    robust_score = (values - scene_median) / robust_scale

    mask = np.isfinite(values)
    mask &= peak_delta >= config.minimum_delta_c
    mask &= scale_support >= config.minimum_scale_support
    # Robust scene evidence is intentionally supporting rather than authoritative: a locally
    # coherent anomaly in a globally warm scene can still be accepted.
    mask &= (robust_score >= 1.0) | (values >= scene_p90) | (peak_delta >= config.minimum_delta_c * 1.5)
    if config.absolute_threshold_c is not None:
        mask &= values >= config.absolute_threshold_c

    findings: list[Finding] = []
    suppressions: list[SuppressionRecord] = []
    for component in _components(mask, config.connectivity):
        rr = np.fromiter((r for r, _ in component), dtype=int)
        cc = np.fromiter((c for _, c in component), dtype=int)
        center_x = round(float(np.mean(cc)))
        center_y = round(float(np.mean(rr)))
        area = len(component)
        if area < config.minimum_area_px:
            reason = "SINGLE_PIXEL_SPIKE" if area == 1 else "MINIMUM_REGION_SUPPORT"
            suppressions.append(SuppressionRecord(reason, area, center_x, center_y))
            continue

        row0, row1 = int(np.min(rr)), int(np.max(rr))
        col0, col1 = int(np.min(cc)), int(np.max(cc))
        width = col1 - col0 + 1
        height = row1 - row0 + 1
        fill_ratio = area / max(width * height, 1)
        touches_edge = (
            row0 <= config.edge_margin_px
            or col0 <= config.edge_margin_px
            or row1 >= values.shape[0] - 1 - config.edge_margin_px
            or col1 >= values.shape[1] - 1 - config.edge_margin_px
        )
        if fill_ratio < config.minimum_fill_ratio:
            suppressions.append(
                SuppressionRecord(
                    "LOW_SPATIAL_COHERENCE",
                    area,
                    center_x,
                    center_y,
                    {"fill_ratio": round(fill_ratio, 4)},
                )
            )
            continue

        reference, reference_count = _component_reference(
            values,
            rr,
            cc,
            margin=max(config.local_radii),
        )
        if reference is None:
            reference = scene_median
            reference_method = "scene-median-fallback"
        else:
            reference_method = "surrounding-ring-median"
        temps = values[rr, cc]
        hottest_index = int(np.argmax(temps))
        max_temp = float(temps[hottest_index])
        delta = max_temp - reference
        if delta < config.minimum_delta_c:
            suppressions.append(
                SuppressionRecord(
                    "WEAK_LOCAL_CONTRAST",
                    area,
                    center_x,
                    center_y,
                    {"delta_c": round(delta, 3), "reference_method": reference_method},
                )
            )
            continue
        if config.edge_suppression and touches_edge and delta < config.minimum_delta_c * 2.0:
            suppressions.append(
                SuppressionRecord(
                    "EDGE_ARTIFACT",
                    area,
                    center_x,
                    center_y,
                    {"delta_c": round(delta, 3)},
                )
            )
            continue

        component_scale_support = int(np.max(scale_support[rr, cc]))
        component_robust_score = float(np.max(robust_score[rr, cc]))
        confidence, confidence_components = _confidence(
            delta_c=delta,
            minimum_delta_c=config.minimum_delta_c,
            area_px=area,
            minimum_area_px=config.minimum_area_px,
            scale_support=component_scale_support,
            scale_count=len(config.local_radii),
            fill_ratio=fill_ratio,
            robust_score=component_robust_score,
            touches_edge=touches_edge,
        )
        severity = severity_policy.classify(delta)
        label = profile.finding_label if profile else "Thermal anomaly"
        hotspot_y = int(rr[hottest_index])
        hotspot_x = int(cc[hottest_index])
        evidence = [
            f"local reference established by {reference_method}",
            f"maximum local ΔT {delta:.1f} °C",
            f"spatially coherent connected region ({area} pixels)",
            f"supported at {component_scale_support}/{len(config.local_radii)} analysis scales",
        ]
        if component_robust_score >= config.robust_z_threshold:
            evidence.append("strong robust scene deviation")
        findings.append(
            Finding(
                center_x=center_x,
                center_y=center_y,
                area_px=area,
                max_temperature_c=max_temp,
                mean_temperature_c=float(np.mean(temps)),
                baseline_temperature_c=reference,
                delta_temperature_c=delta,
                severity=severity,
                finding_type=label,
                classification=label,
                classification_rationale="Contextual thermal contrast with coherent spatial support.",
                severity_rationale=(
                    f"Local ΔT {delta:.1f} °C classified by the active inspection profile."
                ),
                confidence=confidence,
                confidence_components=confidence_components,
                bbox=(col0, row0, col1, row1),
                polygon=[(col0, row0), (col1, row0), (col1, row1), (col0, row1)],
                hotspot_x=hotspot_x,
                hotspot_y=hotspot_y,
                min_temperature_c=float(np.min(temps)),
                reference_temperature_c=reference,
                reference_method=reference_method,
                morphology={
                    "width_px": width,
                    "height_px": height,
                    "fill_ratio": round(fill_ratio, 4),
                    "touches_edge": touches_edge,
                    "scale_support": component_scale_support,
                    "reference_sample_count": reference_count,
                },
                evidence=evidence,
                suppression_checks=["minimum_area", "local_contrast", "spatial_coherence", "edge_check"],
                profile_id=profile.profile_id if profile else "generic-thermal",
                profile_version=profile.version if profile else "1.0",
            )
        )

    findings.sort(key=lambda item: item.delta_temperature_c, reverse=True)
    for index, finding in enumerate(findings, 1):
        finding.finding_id = f"A-{index:03d}"
        finding.canonical_finding_id = finding.finding_id
    return DetectionOutcome(
        findings=findings,
        suppressions=suppressions,
        diagnostics={
            "valid_pixels": int(finite_values.size),
            "scene_median_c": round(scene_median, 4),
            "scene_robust_scale_c": round(robust_scale, 4),
            "scene_p90_c": round(scene_p90, 4),
            "candidate_pixels": int(np.count_nonzero(mask)),
            "accepted_findings": len(findings),
            "suppressed_candidates": len(suppressions),
            "contextual_detection": True,
        },
    )


def detect_anomalies(
    temperature_c: np.ndarray,
    config: DetectionConfig | None = None,
    severity_policy: SeverityPolicy | None = None,
) -> list[Finding]:
    """Compatibility projection returning accepted findings only."""

    return analyze_temperature(
        temperature_c,
        config=config,
        severity_policy=severity_policy,
    ).findings
