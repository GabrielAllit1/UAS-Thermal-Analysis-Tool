from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from math import hypot
from typing import Any

import numpy as np


class MeasurementKind(StrEnum):
    SPOT = "spot"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    LINE = "line"
    POLYGON = "polygon"


@dataclass(frozen=True, slots=True)
class MeasurementStatistics:
    minimum_c: float
    maximum_c: float
    mean_c: float
    median_c: float
    stddev_c: float
    p95_c: float
    valid_pixels: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Measurement:
    measurement_id: str
    kind: MeasurementKind
    geometry: dict[str, Any]
    statistics: MeasurementStatistics
    label: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


def _matrix(values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError("temperature matrix must be two-dimensional")
    return matrix


def _statistics(samples: np.ndarray) -> MeasurementStatistics:
    finite = np.asarray(samples, dtype=np.float32)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("measurement contains no finite temperature samples")
    return MeasurementStatistics(
        minimum_c=float(np.min(finite)),
        maximum_c=float(np.max(finite)),
        mean_c=float(np.mean(finite)),
        median_c=float(np.median(finite)),
        stddev_c=float(np.std(finite)),
        p95_c=float(np.percentile(finite, 95)),
        valid_pixels=int(finite.size),
    )


def spot_statistics(
    temperature_c: np.ndarray,
    x: int,
    y: int,
    *,
    kernel_size: int = 4,
) -> MeasurementStatistics:
    """Measure a spot as a square neighborhood, defaulting to a 4x4 average area."""

    values = _matrix(temperature_c)
    if kernel_size <= 0:
        raise ValueError("kernel_size must be positive")
    if x < 0 or y < 0 or x >= values.shape[1] or y >= values.shape[0]:
        raise ValueError("spot is outside the temperature matrix")
    half_low = (kernel_size - 1) // 2
    half_high = kernel_size // 2
    left = max(0, int(x) - half_low)
    right = min(values.shape[1], int(x) + half_high + 1)
    top = max(0, int(y) - half_low)
    bottom = min(values.shape[0], int(y) + half_high + 1)
    return _statistics(values[top:bottom, left:right])


def spot_delta(
    temperature_c: np.ndarray,
    first: tuple[int, int],
    second: tuple[int, int],
    *,
    kernel_size: int = 4,
) -> float:
    a = spot_statistics(temperature_c, first[0], first[1], kernel_size=kernel_size)
    b = spot_statistics(temperature_c, second[0], second[1], kernel_size=kernel_size)
    return b.mean_c - a.mean_c


def rectangle_statistics(
    temperature_c: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> MeasurementStatistics:
    values = _matrix(temperature_c)
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    left = max(0, min(values.shape[1] - 1, left))
    right = max(0, min(values.shape[1] - 1, right))
    top = max(0, min(values.shape[0] - 1, top))
    bottom = max(0, min(values.shape[0] - 1, bottom))
    return _statistics(values[top : bottom + 1, left : right + 1])


def _masked_statistics(values: np.ndarray, mask: np.ndarray) -> MeasurementStatistics:
    if mask.shape != values.shape:
        raise ValueError("measurement mask shape must match temperature matrix")
    return _statistics(values[mask])


def circle_statistics(
    temperature_c: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
) -> MeasurementStatistics:
    values = _matrix(temperature_c)
    if radius <= 0:
        raise ValueError("radius must be positive")
    yy, xx = np.ogrid[: values.shape[0], : values.shape[1]]
    mask = (xx - float(center_x)) ** 2 + (yy - float(center_y)) ** 2 <= float(radius) ** 2
    return _masked_statistics(values, mask)


def ellipse_statistics(
    temperature_c: np.ndarray,
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
) -> MeasurementStatistics:
    values = _matrix(temperature_c)
    if radius_x <= 0 or radius_y <= 0:
        raise ValueError("ellipse radii must be positive")
    yy, xx = np.ogrid[: values.shape[0], : values.shape[1]]
    mask = (
        ((xx - float(center_x)) / float(radius_x)) ** 2
        + ((yy - float(center_y)) / float(radius_y)) ** 2
        <= 1.0
    )
    return _masked_statistics(values, mask)


def line_statistics(
    temperature_c: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    width_px: float = 1.5,
) -> MeasurementStatistics:
    values = _matrix(temperature_c)
    if width_px <= 0:
        raise ValueError("width_px must be positive")
    length = hypot(float(x1) - float(x0), float(y1) - float(y0))
    if length == 0:
        return spot_statistics(values, round(x0), round(y0), kernel_size=1)
    yy, xx = np.indices(values.shape, dtype=np.float32)
    dx = float(x1) - float(x0)
    dy = float(y1) - float(y0)
    t = ((xx - float(x0)) * dx + (yy - float(y0)) * dy) / (length * length)
    t = np.clip(t, 0.0, 1.0)
    projection_x = float(x0) + t * dx
    projection_y = float(y0) + t * dy
    distance = np.hypot(xx - projection_x, yy - projection_y)
    return _masked_statistics(values, distance <= float(width_px) / 2.0)


def polygon_mask(shape: tuple[int, int], points: list[tuple[float, float]]) -> np.ndarray:
    """Return a dependency-free even/odd scanline polygon mask."""

    if len(points) < 3:
        raise ValueError("polygon requires at least three points")
    height, width = shape
    yy, xx = np.indices((height, width), dtype=np.float32)
    x = xx + 0.5
    y = yy + 0.5
    inside = np.zeros((height, width), dtype=bool)
    previous_x, previous_y = map(float, points[-1])
    for current in points:
        current_x, current_y = map(float, current)
        crosses = (current_y > y) != (previous_y > y)
        denominator = previous_y - current_y
        if abs(denominator) < 1e-12:
            intersection_x = np.full_like(x, current_x)
        else:
            intersection_x = (
                (previous_x - current_x) * (y - current_y) / denominator + current_x
            )
        inside ^= crosses & (x < intersection_x)
        previous_x, previous_y = current_x, current_y
    return inside


def polygon_statistics(
    temperature_c: np.ndarray,
    points: list[tuple[float, float]],
) -> MeasurementStatistics:
    values = _matrix(temperature_c)
    return _masked_statistics(values, polygon_mask(values.shape, points))
