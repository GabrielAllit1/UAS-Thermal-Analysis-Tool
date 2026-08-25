from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np

from ..thermal.calibration import ThermalCalibration
from ..thermal.radiometry import apply_scale_offset
from .base import AdapterUnavailableError, ThermalFrame, ThermalSensorAdapter

_UNIT_KEYS = ("THERMAL_UNIT", "TEMPERATURE_UNIT", "TEMP_UNIT", "UNIT", "UNITS")
_SCALE_KEYS = ("THERMAL_SCALE", "TEMPERATURE_SCALE", "TEMP_SCALE")
_OFFSET_KEYS = ("THERMAL_OFFSET", "TEMPERATURE_OFFSET", "TEMP_OFFSET")


def _tag_value(tags: Mapping[str, str], keys: tuple[str, ...]) -> str | None:
    normalized = {str(key).upper(): value for key, value in tags.items()}
    for key in keys:
        if key in normalized and str(normalized[key]).strip():
            return str(normalized[key]).strip()
    return None


def masked_band_to_float(values: np.ndarray) -> np.ndarray:
    """Convert a masked raster band to float while preserving nodata as NaN."""

    masked = np.ma.asarray(values)
    return np.asarray(masked.astype(np.float64).filled(np.nan), dtype=np.float64)


def _infer_unit(values: np.ndarray) -> str:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("GeoTIFF contains no finite thermal samples")
    median = float(np.median(finite))
    if -100.0 <= median <= 200.0:
        return "celsius"
    if 170.0 <= median <= 400.0:
        return "kelvin"
    if 1500.0 <= median <= 4000.0:
        return "decikelvin"
    if 20000.0 <= median <= 40000.0:
        return "centikelvin"
    raise ValueError(
        "Unable to infer thermal units safely. Add a THERMAL_UNIT tag or configure "
        "GenericGeoTiffAdapter(unit=...)."
    )


def temperature_to_celsius(values: np.ndarray, unit: str) -> np.ndarray:
    normalized = unit.strip().lower().replace("°", "").replace(" ", "")
    array = np.asarray(values, dtype=float)
    aliases = {
        "c": "celsius",
        "degc": "celsius",
        "celsius": "celsius",
        "k": "kelvin",
        "kelvin": "kelvin",
        "f": "fahrenheit",
        "degf": "fahrenheit",
        "fahrenheit": "fahrenheit",
        "decic": "decicelsius",
        "decicelsius": "decicelsius",
        "0.1c": "decicelsius",
        "decik": "decikelvin",
        "decikelvin": "decikelvin",
        "0.1k": "decikelvin",
        "centik": "centikelvin",
        "centikelvin": "centikelvin",
        "0.01k": "centikelvin",
    }
    canonical = aliases.get(normalized, normalized)
    if canonical == "auto":
        canonical = _infer_unit(array)
    if canonical == "celsius":
        return array
    if canonical == "kelvin":
        return array - 273.15
    if canonical == "fahrenheit":
        return (array - 32.0) * 5.0 / 9.0
    if canonical == "decicelsius":
        return array / 10.0
    if canonical == "decikelvin":
        return array / 10.0 - 273.15
    if canonical == "centikelvin":
        return array / 100.0 - 273.15
    raise ValueError(f"unsupported thermal unit: {unit!r}")


def thermal_preview(temperature_c: np.ndarray) -> np.ndarray:
    values = np.asarray(temperature_c, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros((*values.shape, 3), dtype=np.uint8)
    low, high = np.percentile(finite, [2, 98])
    if high <= low:
        high = low + 1.0
    scaled = np.clip((values - low) / (high - low), 0.0, 1.0)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=1.0, neginf=0.0)
    gray = np.round(scaled * 255.0).astype(np.uint8)
    return np.repeat(gray[:, :, None], 3, axis=2)


def _sidecar_metadata(path: Path) -> dict[str, str]:
    candidates = {
        "world_file": (path.with_suffix(".tfw"), path.with_suffix(".tifw"), path.with_suffix(".wld")),
        "projection": (path.with_suffix(".prj"),),
        "kml": (path.with_suffix(".kml"),),
    }
    found: dict[str, str] = {}
    for kind, paths in candidates.items():
        for candidate in paths:
            if candidate.is_file():
                found[kind] = str(candidate)
                break
    return found


class GenericGeoTiffAdapter(ThermalSensorAdapter):
    name = "generic-geotiff"
    vendor = "generic"
    support_level = "operational"

    def __init__(self, scale: float = 1.0, offset: float = 0.0, unit: str = "auto"):
        self.scale = scale
        self.offset = offset
        self.unit = unit

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in {".tif", ".tiff"}

    def source_diagnostics(self, path: Path) -> dict[str, object]:
        try:
            import rasterio
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to read GeoTIFF files") from exc

        with rasterio.open(path) as source:
            sample = source.read(
                1,
                out_shape=(min(source.height, 512), min(source.width, 512)),
                masked=True,
            )
            sample_values = masked_band_to_float(sample)
            finite = sample_values[np.isfinite(sample_values)]
            return {
                "driver": source.driver,
                "width": source.width,
                "height": source.height,
                "count": source.count,
                "dtype": str(source.dtypes[0]),
                "nodata": source.nodata,
                "scales": [float(value) for value in source.scales],
                "offsets": [float(value) for value in source.offsets],
                "crs": None if source.crs is None else str(source.crs),
                "transform": [float(value) for value in tuple(source.transform)[:6]],
                "tags": source.tags(),
                "sidecars": _sidecar_metadata(path),
                "sample_masked_pixels": int(np.count_nonzero(np.ma.getmaskarray(sample))),
                "sample_min_raw": None if finite.size == 0 else float(np.min(finite)),
                "sample_max_raw": None if finite.size == 0 else float(np.max(finite)),
                "sample_median_raw": None if finite.size == 0 else float(np.median(finite)),
            }

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        try:
            import rasterio
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to read GeoTIFF files") from exc

        with rasterio.open(path) as source:
            masked_band = source.read(1, masked=True)
            raw = masked_band_to_float(masked_band)
            masked_pixels = int(np.count_nonzero(np.ma.getmaskarray(masked_band)))
            tags = source.tags()
            tag_scale = _tag_value(tags, _SCALE_KEYS)
            tag_offset = _tag_value(tags, _OFFSET_KEYS)
            dataset_scale = source.scales[0] if source.scales else None
            dataset_offset = source.offsets[0] if source.offsets else None
            scale = float(tag_scale) if tag_scale is not None else float(dataset_scale or self.scale)
            offset = float(tag_offset) if tag_offset is not None else float(dataset_offset or self.offset)
            scaled = apply_scale_offset(raw, scale, offset)
            unit = _tag_value(tags, _UNIT_KEYS) or self.unit
            temperature_c = temperature_to_celsius(scaled, unit)
            resolved_unit = _infer_unit(scaled) if unit.strip().lower() == "auto" else unit
            transform = tuple(source.transform)[:6]
            return ThermalFrame(
                temperature_c=temperature_c,
                source=path,
                display_rgb=thermal_preview(temperature_c),
                metadata={
                    "driver": source.driver,
                    "width": source.width,
                    "height": source.height,
                    "count": source.count,
                    "dtype": str(masked_band.dtype),
                    "nodata": source.nodata,
                    "masked_pixels": masked_pixels,
                    "tags": tags,
                    "sidecars": _sidecar_metadata(path),
                    "calibration": {
                        "emissivity": calibration.emissivity,
                        "distance_m": calibration.distance_m,
                        "relative_humidity": calibration.relative_humidity,
                        "reflected_temperature_c": calibration.reflected_temperature_c,
                    },
                    "scale": scale,
                    "offset": offset,
                    "input_unit": resolved_unit,
                    "output_unit": "celsius",
                },
                crs=str(source.crs) if source.crs else None,
                transform=transform,
            )
