from __future__ import annotations

import numpy as np


def apply_scale_offset(raw: np.ndarray, scale: float = 1.0, offset: float = 0.0) -> np.ndarray:
    """Normalize numeric radiometric data to Celsius using explicit scale/offset."""
    values = np.asarray(raw, dtype=np.float32)
    return values * float(scale) + float(offset)


def normalize_display(temperature_c: np.ndarray) -> np.ndarray:
    """Create an 8-bit grayscale visualization without changing radiometric data."""
    values = np.asarray(temperature_c, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("temperature array contains no finite values")
    low, high = np.percentile(finite, (2, 98))
    if high <= low:
        high = low + 1.0
    scaled = np.clip((values - low) / (high - low), 0.0, 1.0)
    return np.nan_to_num(scaled * 255.0).astype(np.uint8)
