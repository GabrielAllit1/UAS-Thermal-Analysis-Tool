from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..thermal.measurements import rectangle_statistics
from ..thermal.presentation import (
    ThermalStyle,
    available_palettes as _available_palettes,
    render_with_style,
)


@dataclass(frozen=True, slots=True)
class RoiStatistics:
    x0: int
    y0: int
    x1: int
    y1: int
    minimum_c: float
    maximum_c: float
    mean_c: float
    median_c: float
    stddev_c: float
    p95_c: float
    valid_pixels: int


def available_palettes() -> tuple[str, ...]:
    return _available_palettes()


def normalize_temperature(
    temperature_c: np.ndarray,
    *,
    minimum_c: float | None = None,
    maximum_c: float | None = None,
) -> tuple[np.ndarray, float, float]:
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("temperature_c must be a two-dimensional matrix")
    finite = values[np.isfinite(values)]
    if finite.size:
        low = float(np.percentile(finite, 2)) if minimum_c is None else float(minimum_c)
        high = float(np.percentile(finite, 98)) if maximum_c is None else float(maximum_c)
    else:
        low = 0.0 if minimum_c is None else float(minimum_c)
        high = 1.0 if maximum_c is None else float(maximum_c)
    if high <= low:
        high = low + 1.0
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    normalized = np.nan_to_num(normalized, nan=0.0, posinf=1.0, neginf=0.0)
    return normalized.astype(np.float32, copy=False), low, high


def render_temperature(
    temperature_c: np.ndarray,
    *,
    palette: str = "ironbow",
    minimum_c: float | None = None,
    maximum_c: float | None = None,
    span_c: float | None = None,
    level_c: float | None = None,
    isotherm_min_c: float | None = None,
    isotherm_max_c: float | None = None,
) -> tuple[np.ndarray, tuple[float, float]]:
    """Render a visual thermal representation without changing quantitative temperatures."""

    style = ThermalStyle(
        palette=palette,
        minimum_c=minimum_c,
        maximum_c=maximum_c,
        span_c=span_c,
        level_c=level_c,
        isotherm_min_c=isotherm_min_c,
        isotherm_max_c=isotherm_max_c,
    )
    return render_with_style(temperature_c, style)


def temperature_at(temperature_c: np.ndarray, x: int, y: int) -> float | None:
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2 or x < 0 or y < 0 or y >= values.shape[0] or x >= values.shape[1]:
        return None
    value = float(values[y, x])
    return value if np.isfinite(value) else None


def roi_statistics(
    temperature_c: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> RoiStatistics:
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("temperature_c must be a two-dimensional matrix")
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    left = max(0, min(values.shape[1] - 1, left))
    right = max(0, min(values.shape[1] - 1, right))
    top = max(0, min(values.shape[0] - 1, top))
    bottom = max(0, min(values.shape[0] - 1, bottom))
    stats = rectangle_statistics(values, left, top, right, bottom)
    return RoiStatistics(
        x0=left,
        y0=top,
        x1=right,
        y1=bottom,
        minimum_c=stats.minimum_c,
        maximum_c=stats.maximum_c,
        mean_c=stats.mean_c,
        median_c=stats.median_c,
        stddev_c=stats.stddev_c,
        p95_c=stats.p95_c,
        valid_pixels=stats.valid_pixels,
    )


def _coerce_rgb(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("RGB image must be an HxWx3 array")
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return array


def _resize_nearest(image: np.ndarray, height: int, width: int) -> np.ndarray:
    source = _coerce_rgb(image)
    if source.shape[:2] == (height, width):
        return source
    rows = np.minimum(
        source.shape[0] - 1,
        np.floor(np.arange(height) * source.shape[0] / height).astype(int),
    )
    cols = np.minimum(
        source.shape[1] - 1,
        np.floor(np.arange(width) * source.shape[1] / width).astype(int),
    )
    return source[rows[:, None], cols[None, :]]


def align_rgb_pair(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    left_rgb = _coerce_rgb(left)
    right_rgb = _coerce_rgb(right)
    height = min(left_rgb.shape[0], right_rgb.shape[0])
    width = min(left_rgb.shape[1], right_rgb.shape[1])
    return _resize_nearest(left_rgb, height, width), _resize_nearest(right_rgb, height, width)


def blend_rgb(left: np.ndarray, right: np.ndarray, opacity: float = 0.5) -> np.ndarray:
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("opacity must be between 0 and 1")
    left_rgb, right_rgb = align_rgb_pair(left, right)
    blended = left_rgb.astype(np.float32) * (1.0 - opacity) + right_rgb.astype(np.float32) * opacity
    return np.clip(np.rint(blended), 0, 255).astype(np.uint8)


def swipe_rgb(left: np.ndarray, right: np.ndarray, fraction: float = 0.5) -> np.ndarray:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    left_rgb, right_rgb = align_rgb_pair(left, right)
    split = round(left_rgb.shape[1] * fraction)
    output = right_rgb.copy()
    output[:, :split] = left_rgb[:, :split]
    return output
