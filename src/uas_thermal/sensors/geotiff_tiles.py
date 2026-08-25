from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..thermal.calibration import ThermalCalibration
from ..thermal.radiometry import apply_scale_offset
from .base import AdapterUnavailableError, ThermalFrame
from .generic import (
    GenericGeoTiffAdapter,
    _encoding,
    _infer_unit,
    _radiometric_classification,
    _sidecar_metadata,
    masked_band_to_float,
    temperature_to_celsius,
    thermal_preview,
)


@dataclass(frozen=True, slots=True)
class TileBounds:
    read_col_off: int
    read_row_off: int
    read_width: int
    read_height: int
    core_col_off: int
    core_row_off: int
    core_width: int
    core_height: int

    @property
    def local_core(self) -> tuple[int, int, int, int]:
        left = self.core_col_off - self.read_col_off
        top = self.core_row_off - self.read_row_off
        return left, top, left + self.core_width, top + self.core_height


@dataclass(slots=True)
class RadiometricTile:
    frame: ThermalFrame
    bounds: TileBounds

    def owns(self, x: int, y: int) -> bool:
        left, top, right, bottom = self.bounds.local_core
        return left <= x < right and top <= y < bottom

    def core_temperature(self) -> np.ndarray:
        left, top, right, bottom = self.bounds.local_core
        return self.frame.temperature_c[top:bottom, left:right]


@dataclass(frozen=True, slots=True)
class GeoTiffSourceContext:
    width: int
    height: int
    crs: str | None
    transform: tuple[float, ...]
    metadata: dict[str, object]


def _resolved_encoding(source, tags, adapter: GenericGeoTiffAdapter) -> tuple[float, float, str]:
    scale, offset, unit = _encoding(
        source,
        tags,
        adapter.scale,
        adapter.offset,
        adapter.unit,
    )
    normalized = unit.strip().lower().replace("°", "").replace(" ", "")
    if normalized != "auto":
        return scale, offset, unit
    max_edge = 512
    factor = min(1.0, max_edge / max(source.width, source.height))
    width = max(1, round(source.width * factor))
    height = max(1, round(source.height * factor))
    sample = masked_band_to_float(source.read(1, out_shape=(height, width), masked=True))
    scaled = apply_scale_offset(sample, scale, offset)
    return scale, offset, _infer_unit(scaled)


class TiledGeoTiffReader:
    """Windowed quantitative reader for scalar radiometric GeoTIFFs.

    Tiles carry an overlap halo for neighborhood-based detectors while every pixel belongs to
    exactly one core window. This keeps large-raster memory bounded and prevents halo pixels from
    being double-counted in global statistics.
    """

    def __init__(
        self,
        adapter: GenericGeoTiffAdapter,
        *,
        tile_size: int = 2048,
        overlap: int = 64,
    ):
        if tile_size <= 0:
            raise ValueError("tile_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        self.adapter = adapter
        self.tile_size = int(tile_size)
        self.overlap = int(overlap)

    def context(self, path: str | Path) -> GeoTiffSourceContext:
        rasterio, _ = _rasterio()
        source_path = Path(path)
        with rasterio.open(source_path) as source:
            tags = source.tags()
            classification = _radiometric_classification(
                tags=tags,
                count=source.count,
                dtype=str(source.dtypes[0]),
                pixel_count=int(source.width) * int(source.height),
            )
            if not classification["radiometric_candidate"]:
                reasons = "; ".join(classification["radiometric_reasons"])
                raise AdapterUnavailableError(
                    "GeoTIFF is not a validated radiometric temperature raster: " + reasons
                )
            scale, offset, unit = _resolved_encoding(source, tags, self.adapter)
            return GeoTiffSourceContext(
                width=int(source.width),
                height=int(source.height),
                crs=None if source.crs is None else str(source.crs),
                transform=tuple(float(value) for value in tuple(source.transform)[:6]),
                metadata={
                    "driver": source.driver,
                    "width": int(source.width),
                    "height": int(source.height),
                    "count": int(source.count),
                    "dtype": str(source.dtypes[0]),
                    "nodata": source.nodata,
                    "tags": tags,
                    "sidecars": _sidecar_metadata(source_path),
                    "scale": scale,
                    "offset": offset,
                    "input_unit": unit,
                    "output_unit": "celsius",
                    "tiled_analysis": True,
                    "tile_size": self.tile_size,
                    "tile_overlap": self.overlap,
                    **classification,
                },
            )

    def iter_tiles(
        self,
        path: str | Path,
        calibration: ThermalCalibration,
    ):
        rasterio, Window = _rasterio()
        source_path = Path(path)
        with rasterio.open(source_path) as source:
            tags = source.tags()
            classification = _radiometric_classification(
                tags=tags,
                count=source.count,
                dtype=str(source.dtypes[0]),
                pixel_count=int(source.width) * int(source.height),
            )
            if not classification["radiometric_candidate"]:
                reasons = "; ".join(classification["radiometric_reasons"])
                raise AdapterUnavailableError(
                    "GeoTIFF is not a validated radiometric temperature raster: " + reasons
                )
            scale, offset, unit = _resolved_encoding(source, tags, self.adapter)
            for core_row in range(0, source.height, self.tile_size):
                core_height = min(self.tile_size, source.height - core_row)
                for core_col in range(0, source.width, self.tile_size):
                    core_width = min(self.tile_size, source.width - core_col)
                    read_row = max(0, core_row - self.overlap)
                    read_col = max(0, core_col - self.overlap)
                    read_bottom = min(source.height, core_row + core_height + self.overlap)
                    read_right = min(source.width, core_col + core_width + self.overlap)
                    window = Window(
                        read_col,
                        read_row,
                        read_right - read_col,
                        read_bottom - read_row,
                    )
                    masked = source.read(1, window=window, masked=True)
                    raw = masked_band_to_float(masked)
                    scaled = apply_scale_offset(raw, scale, offset)
                    temperature_c = temperature_to_celsius(scaled, unit)
                    window_transform = source.window_transform(window)
                    bounds = TileBounds(
                        read_col_off=int(read_col),
                        read_row_off=int(read_row),
                        read_width=int(read_right - read_col),
                        read_height=int(read_bottom - read_row),
                        core_col_off=int(core_col),
                        core_row_off=int(core_row),
                        core_width=int(core_width),
                        core_height=int(core_height),
                    )
                    yield RadiometricTile(
                        frame=ThermalFrame(
                            temperature_c=temperature_c,
                            source=source_path,
                            display_rgb=None,
                            metadata={
                                "tiled_analysis": True,
                                "tile_bounds": {
                                    "read_col_off": bounds.read_col_off,
                                    "read_row_off": bounds.read_row_off,
                                    "core_col_off": bounds.core_col_off,
                                    "core_row_off": bounds.core_row_off,
                                    "core_width": bounds.core_width,
                                    "core_height": bounds.core_height,
                                },
                                "scale": scale,
                                "offset": offset,
                                "input_unit": unit,
                                "output_unit": "celsius",
                                "calibration": {
                                    "emissivity": calibration.emissivity,
                                    "distance_m": calibration.distance_m,
                                    "relative_humidity": calibration.relative_humidity,
                                    "reflected_temperature_c": calibration.reflected_temperature_c,
                                },
                            },
                            crs=None if source.crs is None else str(source.crs),
                            transform=tuple(float(value) for value in tuple(window_transform)[:6]),
                        ),
                        bounds=bounds,
                    )

    def preview_frame(
        self,
        path: str | Path,
        calibration: ThermalCalibration,
        *,
        max_edge: int = 1600,
    ) -> ThermalFrame:
        rasterio, _ = _rasterio()
        source_path = Path(path)
        with rasterio.open(source_path) as source:
            scale_factor = min(1.0, max_edge / max(source.width, source.height))
            width = max(1, round(source.width * scale_factor))
            height = max(1, round(source.height * scale_factor))
            tags = source.tags()
            scale, offset, unit = _resolved_encoding(source, tags, self.adapter)
            masked = source.read(1, out_shape=(height, width), masked=True)
            raw = masked_band_to_float(masked)
            temperature_c = temperature_to_celsius(apply_scale_offset(raw, scale, offset), unit)
            preview_transform = source.transform * source.transform.scale(
                source.width / width,
                source.height / height,
            )
            return ThermalFrame(
                temperature_c=temperature_c,
                source=source_path,
                display_rgb=thermal_preview(temperature_c),
                metadata={
                    "preview_only": True,
                    "tiled_analysis": True,
                    "source_width": int(source.width),
                    "source_height": int(source.height),
                    "preview_width": width,
                    "preview_height": height,
                    "scale": scale,
                    "offset": offset,
                    "input_unit": unit,
                    "output_unit": "celsius",
                    "calibration": {
                        "emissivity": calibration.emissivity,
                        "distance_m": calibration.distance_m,
                        "relative_humidity": calibration.relative_humidity,
                        "reflected_temperature_c": calibration.reflected_temperature_c,
                    },
                },
                crs=None if source.crs is None else str(source.crs),
                transform=tuple(float(value) for value in tuple(preview_transform)[:6]),
            )

    def temperature_at(
        self,
        path: str | Path,
        x: int,
        y: int,
    ) -> float | None:
        rasterio, Window = _rasterio()
        source_path = Path(path)
        with rasterio.open(source_path) as source:
            if x < 0 or y < 0 or x >= source.width or y >= source.height:
                return None
            tags = source.tags()
            scale, offset, unit = _resolved_encoding(source, tags, self.adapter)
            masked = source.read(1, window=Window(x, y, 1, 1), masked=True)
            raw = masked_band_to_float(masked)
            temperature_c = temperature_to_celsius(apply_scale_offset(raw, scale, offset), unit)
            value = float(temperature_c[0, 0])
            return value if np.isfinite(value) else None


def _rasterio():
    try:
        import rasterio
        from rasterio.windows import Window
    except ImportError as exc:
        raise AdapterUnavailableError("Install the geospatial extra to process tiled GeoTIFFs") from exc
    return rasterio, Window
