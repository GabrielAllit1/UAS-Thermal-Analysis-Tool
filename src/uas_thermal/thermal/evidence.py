from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    minimum_delta_c: float = 8.0
    absolute_threshold_c: float | None = None
    local_radii: tuple[int, ...] = (3, 7)
    inner_reference_radius: int = 1
    minimum_scale_support: int = 1

    @classmethod
    def from_profile(cls, profile) -> "EvidenceConfig":
        return cls(
            minimum_delta_c=float(profile.minimum_delta_c),
            absolute_threshold_c=profile.absolute_threshold_c,
            local_radii=tuple(int(value) for value in profile.local_radii),
            minimum_scale_support=int(profile.minimum_scale_support),
        )


@dataclass(frozen=True, slots=True)
class EvidenceLayers:
    temperature_c: np.ndarray
    local_reference_c: np.ndarray
    local_delta_c: np.ndarray
    robust_scene_deviation: np.ndarray
    scale_support: np.ndarray
    candidate_mask: np.ndarray
    finding_mask: np.ndarray
    structural_residual_c: np.ndarray
    texture_curvature_c: np.ndarray

    def arrays(self) -> tuple[np.ndarray, ...]:
        return (
            self.temperature_c,
            self.local_reference_c,
            self.local_delta_c,
            self.robust_scene_deviation,
            self.scale_support.astype(np.float32, copy=False),
            self.candidate_mask.astype(np.float32, copy=False),
            self.finding_mask.astype(np.float32, copy=False),
            self.structural_residual_c,
            self.texture_curvature_c,
        )


@dataclass(frozen=True, slots=True)
class IlluminationContext:
    brightness: np.ndarray
    illumination_field: np.ndarray
    shadow_score: np.ndarray


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


def _box_mean(values: np.ndarray, radius: int) -> np.ndarray:
    sums, counts = _box_sum_count(values, radius)
    return np.divide(
        sums,
        counts,
        out=np.full(values.shape, np.nan, dtype=np.float32),
        where=counts > 0,
    )


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


def _robust_scene(values: np.ndarray) -> tuple[float, float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0, 1.0, 0.0
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    scale = max(1.4826 * mad, float(np.std(finite)) * 0.25, 0.25)
    p90 = float(np.percentile(finite, 90))
    return median, scale, p90


def _finding_mask(
    shape: tuple[int, int],
    findings: Iterable[object],
    *,
    x_offset: int = 0,
    y_offset: int = 0,
) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    height, width = shape
    for finding in findings:
        bbox = getattr(finding, "bbox", None)
        if bbox is None:
            x = int(getattr(finding, "center_x", -1)) - x_offset
            y = int(getattr(finding, "center_y", -1)) - y_offset
            if 0 <= x < width and 0 <= y < height:
                mask[y, x] = True
            continue
        left, top, right, bottom = (int(value) for value in bbox)
        left -= x_offset
        right -= x_offset
        top -= y_offset
        bottom -= y_offset
        clip_left = max(0, left)
        clip_top = max(0, top)
        clip_right = min(width - 1, right)
        clip_bottom = min(height - 1, bottom)
        if clip_left <= clip_right and clip_top <= clip_bottom:
            mask[clip_top : clip_bottom + 1, clip_left : clip_right + 1] = True
    return mask


def _texture_curvature(values: np.ndarray, fallback: float) -> np.ndarray:
    local = np.asarray(values, dtype=np.float32)
    filled = np.where(np.isfinite(local), local, np.float32(fallback))
    padded = np.pad(filled, 1, mode="edge")
    center = padded[1:-1, 1:-1]
    laplacian = (
        4.0 * center
        - padded[:-2, 1:-1]
        - padded[2:, 1:-1]
        - padded[1:-1, :-2]
        - padded[1:-1, 2:]
    )
    magnitude = np.abs(laplacian).astype(np.float32)
    magnitude[~np.isfinite(local)] = np.nan
    return magnitude


def compute_evidence_layers(
    temperature_c: np.ndarray,
    *,
    config: EvidenceConfig | None = None,
    findings: Iterable[object] = (),
    finding_offset: tuple[int, int] = (0, 0),
) -> EvidenceLayers:
    config = config or EvidenceConfig()
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("thermal evidence requires a 2D Celsius matrix")
    if not config.local_radii:
        raise ValueError("local_radii must not be empty")
    if config.minimum_delta_c <= 0:
        raise ValueError("minimum_delta_c must be positive")

    scene_median, robust_scale, scene_p90 = _robust_scene(values)
    local_deltas: list[np.ndarray] = []
    references: list[np.ndarray] = []
    for radius in config.local_radii:
        reference = _annular_reference(values, config.inner_reference_radius, radius)
        references.append(reference)
        local_deltas.append(values - reference)

    stack = np.stack(local_deltas, axis=0)
    peak_delta = np.nanmax(stack, axis=0)
    safe_stack = np.where(np.isfinite(stack), stack, -np.inf)
    best_index = np.argmax(safe_stack, axis=0)
    reference_stack = np.stack(references, axis=0)
    best_reference = np.take_along_axis(reference_stack, best_index[None, ...], axis=0)[0]
    best_reference[~np.isfinite(peak_delta)] = np.nan

    scale_support = np.sum(stack >= config.minimum_delta_c * 0.75, axis=0).astype(np.float32)
    robust_score = (values - np.float32(scene_median)) / np.float32(robust_scale)

    candidate = np.isfinite(values)
    candidate &= peak_delta >= config.minimum_delta_c
    candidate &= scale_support >= config.minimum_scale_support
    candidate &= (
        (robust_score >= 1.0)
        | (values >= scene_p90)
        | (peak_delta >= config.minimum_delta_c * 1.5)
    )
    if config.absolute_threshold_c is not None:
        candidate &= values >= config.absolute_threshold_c

    smooth = _box_mean(values, max(config.local_radii))
    structural_residual = values - smooth
    texture = _texture_curvature(values, scene_median)
    x_offset, y_offset = finding_offset

    return EvidenceLayers(
        temperature_c=values,
        local_reference_c=best_reference.astype(np.float32, copy=False),
        local_delta_c=peak_delta.astype(np.float32, copy=False),
        robust_scene_deviation=robust_score.astype(np.float32, copy=False),
        scale_support=scale_support,
        candidate_mask=candidate,
        finding_mask=_finding_mask(values.shape, findings, x_offset=x_offset, y_offset=y_offset),
        structural_residual_c=structural_residual.astype(np.float32, copy=False),
        texture_curvature_c=texture,
    )


def compute_illumination_context(rgb: np.ndarray, *, radius: int = 15) -> IlluminationContext:
    """Return supplemental RGB illumination evidence without modifying radiometric temperature."""

    image = np.asarray(rgb)
    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("illumination context requires an HxWx3 RGB image")
    image = image[..., :3].astype(np.float32)
    if image.max(initial=0.0) > 1.0:
        image /= np.float32(255.0)
    brightness = np.mean(image, axis=2, dtype=np.float32)
    illumination = _box_mean(brightness, radius)
    shadow_score = np.clip(
        (illumination - brightness) / np.maximum(illumination, np.float32(1e-6)),
        0.0,
        1.0,
    ).astype(np.float32)
    return IlluminationContext(brightness, illumination, shadow_score)
