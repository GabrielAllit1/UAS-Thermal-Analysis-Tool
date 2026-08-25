from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True, slots=True)
class TemperatureStatistics:
    minimum_c: float
    maximum_c: float
    mean_c: float
    median_c: float
    stddev_c: float
    p95_c: float
    valid_pixels: int


def summarize_temperature(values: np.ndarray) -> TemperatureStatistics:
    array = np.asarray(values, dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        raise ValueError("temperature array contains no finite values")
    return TemperatureStatistics(
        minimum_c=float(np.min(finite)),
        maximum_c=float(np.max(finite)),
        mean_c=float(np.mean(finite)),
        median_c=float(np.median(finite)),
        stddev_c=float(np.std(finite)),
        p95_c=float(np.percentile(finite, 95)),
        valid_pixels=int(finite.size),
    )


def celsius_to_fahrenheit(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("temperature must be finite")
    return value * 9.0 / 5.0 + 32.0
