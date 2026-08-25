from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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


_PALETTES: dict[str, tuple[tuple[float, tuple[int, int, int]], ...]] = {
    "gray": ((0.0, (0, 0, 0)), (1.0, (255, 255, 255))),
    "iron": (
        (0.0, (0, 0, 0)),
        (0.25, (70, 0, 120)),
        (0.50, (200, 40, 20)),
        (0.75, (255, 170, 20)),
        (1.0, (255, 255, 235)),
    ),
    "arctic": (
        (0.0, (0, 20, 80)),
        (0.35, (0, 150, 220)),
        (0.65, (180, 240, 255)),
        (1.0, (255, 255, 255)),
    ),
    "rainbow": (
        (0.0, (0, 0, 100)),
        (0.20, (0, 80, 255)),
        (0.40, (0, 220, 200)),
        (0.60, (220, 240, 0)),
        (0.80, (255, 100, 0)),
        (1.0, (180, 0, 0)),
    ),
    "blackhot": ((0.0, (255, 255, 255)), (1.0, (0, 0, 0))),
}


def available_palettes() -> tuple[str, ...]:
    return tuple(_PALETTES)


def _finite_limits(values: np.ndarray, minimum_c: float | None, maximum_c: float | None) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0, 1.0
    low = float(np.percentile(finite, 2)) if minimum_c is None else float(minimum_c)
    high = float(np.percentile(finite, 98)) if maximum_c is None else float(maximum_c)
    if high <= low:
        high = low + 1.0
    return low, high


def normalize_temperature(
    temperature_c: np.ndarray,
    *,
    minimum_c: float | None = None,
    maximum_c: float | None = None,
) -> tuple[np.ndarray, float, float]:
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("temperature_c must be a two-dimensional matrix")
    low, high = _finite_limits(values, minimum_c, maximum_c)
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    normalized = np.nan_to_num(normalized, nan=0.0, posinf=1.0, neginf=0.0)
    return normalized.astype(np.float32, copy=False), low, high


def _interpolate_palette(values: np.ndarray, anchors) -> np.ndarray:
    flat = values.reshape(-1)
    rgb = np.empty((flat.size, 3), dtype=np.float32)
    positions = np.array([item[0] for item in anchors], dtype=np.float32)
    colors = np.array([item[1] for item in anchors], dtype=np.float32)
    for channel in range(3):
        rgb[:, channel] = np.interp(flat, positions, colors[:, channel])
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8).reshape((*values.shape, 3))


def render_temperature(
    temperature_c: np.ndarray,
    *,
    palette: str = "iron",
    minimum_c: float | None = None,
    maximum_c: float | None = None,
    isotherm_min_c: float | None = None,
    isotherm_max_c: float | None = None,
) -> tuple[np.ndarray, tuple[float, float]]:
    normalized, low, high = normalize_temperature(temperature_c, minimum_c=minimum_c, maximum_c=maximum_c)
    key = palette.strip().lower()
    if key not in _PALETTES:
        raise ValueError(f"unsupported palette: {palette!r}")
    rgb = _interpolate_palette(normalized, _PALETTES[key])
    if isotherm_min_c is not None:
        values = np.asarray(temperature_c, dtype=np.float32)
        mask = np.isfinite(values) & (values >= float(isotherm_min_c))
        if isotherm_max_c is not None:
            mask &= values <= float(isotherm_max_c)
        rgb = rgb.copy()
        rgb[mask] = np.array([255, 255, 0], dtype=np.uint8)
    return rgb, (low, high)


def temperature_at(temperature_c: np.ndarray, x: int, y: int) -> float | None:
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2 or x < 0 or y < 0 or y >= values.shape[0] or x >= values.shape[1]:
        return None
    value = float(values[y, x])
    return value if np.isfinite(value) else None


def roi_statistics(temperature_c: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> RoiStatistics:
    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("temperature_c must be a two-dimensional matrix")
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    left = max(0, min(values.shape[1] - 1, left))
    right = max(0, min(values.shape[1] - 1, right))
    top = max(0, min(values.shape[0] - 1, top))
    bottom = max(0, min(values.shape[0] - 1, bottom))
    samples = values[top : bottom + 1, left : right + 1]
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        raise ValueError("ROI contains no finite temperature samples")
    return RoiStatistics(
        left,
        top,
        right,
        bottom,
        float(np.min(finite)),
        float(np.max(finite)),
        float(np.mean(finite)),
        float(np.median(finite)),
        float(np.std(finite)),
        float(np.percentile(finite, 95)),
        int(finite.size),
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
    rows = np.minimum(source.shape[0] - 1, np.floor(np.arange(height) * source.shape[0] / height).astype(int))
    cols = np.minimum(source.shape[1] - 1, np.floor(np.arange(width) * source.shape[1] / width).astype(int))
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
