from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..sensors.base import AdapterUnavailableError


@dataclass(slots=True)
class DisplayRaster:
    """Bounded display representation for large geospatial rasters.

    This is deliberately separate from ThermalFrame: display/GIS imagery must never be
    mistaken for quantitative radiometric temperature data.
    """

    source: Path
    rgb: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)
    crs: str | None = None
    transform: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if self.rgb.ndim != 3 or self.rgb.shape[2] != 3:
            raise ValueError("rgb must be an HxWx3 array")
        if self.rgb.dtype != np.uint8:
            raise ValueError("rgb must use uint8 display pixels")


def _display_channel(values: np.ndarray) -> np.ndarray:
    masked = np.ma.asarray(values)
    data = np.asarray(masked.filled(0))
    mask = np.ma.getmaskarray(masked)
    if data.dtype == np.uint8:
        result = data.copy()
        result[mask] = 0
        return result

    numeric = np.asarray(data, dtype=np.float32)
    finite = numeric[np.isfinite(numeric) & ~mask]
    if finite.size == 0:
        return np.zeros(numeric.shape, dtype=np.uint8)
    low, high = np.percentile(finite, [2, 98])
    if high <= low:
        high = low + 1.0
    scaled = np.clip((numeric - low) / (high - low), 0.0, 1.0)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=1.0, neginf=0.0)
    result = np.round(scaled * 255.0).astype(np.uint8)
    result[mask] = 0
    return result


def _preview_shape(width: int, height: int, max_edge: int) -> tuple[int, int]:
    if max_edge < 64:
        raise ValueError("max_edge must be at least 64 pixels")
    scale = min(1.0, max_edge / max(width, height))
    return max(1, round(height * scale)), max(1, round(width * scale))


def read_display_raster(path: str | Path, *, max_edge: int = 1600) -> DisplayRaster:
    """Read a bounded RGB preview without allocating the full source raster."""

    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError as exc:
        raise AdapterUnavailableError("Install the geospatial extra to preview GeoTIFF files") from exc

    source_path = Path(path)
    with rasterio.open(source_path) as source:
        preview_h, preview_w = _preview_shape(source.width, source.height, max_edge)
        if source.count >= 3:
            bands = source.read(
                [1, 2, 3],
                out_shape=(3, preview_h, preview_w),
                masked=True,
                resampling=Resampling.bilinear,
            )
            rgb = np.stack([_display_channel(bands[index]) for index in range(3)], axis=2)
        else:
            band = source.read(
                1,
                out_shape=(preview_h, preview_w),
                masked=True,
                resampling=Resampling.bilinear,
            )
            gray = _display_channel(band)
            rgb = np.repeat(gray[:, :, None], 3, axis=2)

        tags = source.tags()
        return DisplayRaster(
            source=source_path,
            rgb=rgb,
            metadata={
                "driver": source.driver,
                "source_width": source.width,
                "source_height": source.height,
                "preview_width": preview_w,
                "preview_height": preview_h,
                "band_count": source.count,
                "dtype": str(source.dtypes[0]),
                "tags": tags,
                "display_only": str(tags.get("isCalibrated", "")).strip().lower() == "false",
                "bounded_preview": True,
            },
            crs=None if source.crs is None else str(source.crs),
            transform=tuple(source.transform)[:6],
        )
