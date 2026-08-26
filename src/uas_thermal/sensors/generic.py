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
_MAX_IN_MEMORY_PIXELS = 50_000_000
_SAMPLE_EDGE = 512


def _tag_value(tags: Mapping[str, str], keys: tuple[str, ...]) -> str | None:
    normalized = {str(key).upper(): value for key, value in tags.items()}
    for key in keys:
        if key in normalized and str(normalized[key]).strip():
            return str(normalized[key]).strip()
    return None


def _parse_bool(value: object) -> bool | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def masked_band_to_float(values: np.ndarray) -> np.ndarray:
    """Convert a masked raster band to float32 while preserving nodata as NaN."""

    masked = np.ma.asarray(values)
    return np.asarray(masked.astype(np.float32).filled(np.nan), dtype=np.float32)


def _infer_unit(values: np.ndarray) -> str:
    finite = np.asarray(values, dtype=np.float32)
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
    array = np.asarray(values, dtype=np.float32)
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
        return array - np.float32(273.15)
    if canonical == "fahrenheit":
        return (array - np.float32(32.0)) * np.float32(5.0 / 9.0)
    if canonical == "decicelsius":
        return array / np.float32(10.0)
    if canonical == "decikelvin":
        return array / np.float32(10.0) - np.float32(273.15)
    if canonical == "centikelvin":
        return array / np.float32(100.0) - np.float32(273.15)
    raise ValueError(f"unsupported thermal unit: {unit!r}")


def thermal_preview(temperature_c: np.ndarray) -> np.ndarray:
    values = np.asarray(temperature_c, dtype=np.float32)
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


def _radiometric_classification(
    *,
    tags: Mapping[str, str],
    count: int,
    dtype: str,
    pixel_count: int,
) -> dict[str, object]:
    normalized = {str(key).upper(): str(value) for key, value in tags.items()}
    is_calibrated = _parse_bool(normalized.get("ISCALIBRATED"))
    unit_tag = _tag_value(tags, _UNIT_KEYS)
    scale_tag = _tag_value(tags, _SCALE_KEYS)
    offset_tag = _tag_value(tags, _OFFSET_KEYS)
    explicit_radiometry = any(value is not None for value in (unit_tag, scale_tag, offset_tag))
    dtype_name = dtype.lower()
    is_8bit = dtype_name in {"uint8", "int8"}

    reasons: list[str] = []
    if is_calibrated is False:
        reasons.append("metadata declares isCalibrated=False")
    if is_8bit and not explicit_radiometry:
        if count >= 3:
            reasons.append(
                "multi-band 8-bit raster looks like rendered imagery rather than scalar temperature data"
            )
        else:
            reasons.append(
                "8-bit scalar raster lacks explicit thermal unit/scale/offset metadata; refusing "
                "to infer temperature from ambiguous display-like values"
            )

    radiometric_candidate = not reasons
    requires_tiled_processing = pixel_count > _MAX_IN_MEMORY_PIXELS
    minimum_float32_gib = pixel_count * np.dtype(np.float32).itemsize / (1024**3)

    return {
        "is_calibrated": is_calibrated,
        "radiometric_candidate": radiometric_candidate,
        "radiometric_reasons": reasons,
        "pixel_count": pixel_count,
        "full_frame_pixel_limit": _MAX_IN_MEMORY_PIXELS,
        "requires_tiled_processing": requires_tiled_processing,
        "minimum_float32_band_gib": round(float(minimum_float32_gib), 3),
    }


def _encoding(source, tags: Mapping[str, str], fallback_scale: float, fallback_offset: float, unit: str):
    tag_scale = _tag_value(tags, _SCALE_KEYS)
    tag_offset = _tag_value(tags, _OFFSET_KEYS)
    dataset_scale = source.scales[0] if source.scales else None
    dataset_offset = source.offsets[0] if source.offsets else None
    scale = float(tag_scale) if tag_scale is not None else float(dataset_scale or fallback_scale)
    offset = float(tag_offset) if tag_offset is not None else float(dataset_offset or fallback_offset)
    resolved_unit = _tag_value(tags, _UNIT_KEYS) or unit
    return scale, offset, resolved_unit


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
                out_shape=(min(source.height, _SAMPLE_EDGE), min(source.width, _SAMPLE_EDGE)),
                masked=True,
            )
            sample_values = masked_band_to_float(sample)
            finite = sample_values[np.isfinite(sample_values)]
            tags = source.tags()
            pixel_count = int(source.width) * int(source.height)
            classification = _radiometric_classification(
                tags=tags,
                count=source.count,
                dtype=str(source.dtypes[0]),
                pixel_count=pixel_count,
            )
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
                "tags": tags,
                "sidecars": _sidecar_metadata(path),
                "sample_shape": [int(sample.shape[0]), int(sample.shape[1])],
                "sample_masked_pixels": int(np.count_nonzero(np.ma.getmaskarray(sample))),
                "sample_min_raw": None if finite.size == 0 else float(np.min(finite)),
                "sample_max_raw": None if finite.size == 0 else float(np.max(finite)),
                "sample_median_raw": None if finite.size == 0 else float(np.median(finite)),
                **classification,
            }

    def sample_temperature(self, path: Path) -> tuple[np.ndarray, dict[str, object]]:
        """Decode a bounded sample for diagnostics without allocating the full raster."""

        try:
            import rasterio
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to read GeoTIFF files") from exc

        with rasterio.open(path) as source:
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
            sample = source.read(
                1,
                out_shape=(min(source.height, _SAMPLE_EDGE), min(source.width, _SAMPLE_EDGE)),
                masked=True,
            )
            raw = masked_band_to_float(sample)
            scale, offset, unit = _encoding(source, tags, self.scale, self.offset, self.unit)
            scaled = apply_scale_offset(raw, scale, offset)
            temperature_c = temperature_to_celsius(scaled, unit)
            resolved_unit = _infer_unit(scaled) if unit.strip().lower() == "auto" else unit
            return temperature_c, {
                "scale": scale,
                "offset": offset,
                "input_unit": resolved_unit,
                **classification,
            }

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        try:
            import rasterio
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to read GeoTIFF files") from exc

        with rasterio.open(path) as source:
            tags = source.tags()
            pixel_count = int(source.width) * int(source.height)
            classification = _radiometric_classification(
                tags=tags,
                count=source.count,
                dtype=str(source.dtypes[0]),
                pixel_count=pixel_count,
            )
            if not classification["radiometric_candidate"]:
                reasons = "; ".join(classification["radiometric_reasons"])
                raise AdapterUnavailableError(
                    "GeoTIFF is not a validated radiometric temperature raster: " + reasons
                )
            if classification["requires_tiled_processing"]:
                raise AdapterUnavailableError(
                    f"GeoTIFF contains {pixel_count:,} pixels, above the current full-frame "
                    f"analysis limit of {_MAX_IN_MEMORY_PIXELS:,}. Use radiometric source tiles "
                    "or the forthcoming tiled-mosaic workflow instead of loading the whole raster."
                )

            masked_band = source.read(1, masked=True)
            raw = masked_band_to_float(masked_band)
            masked_pixels = int(np.count_nonzero(np.ma.getmaskarray(masked_band)))
            scale, offset, unit = _encoding(source, tags, self.scale, self.offset, self.unit)
            scaled = apply_scale_offset(raw, scale, offset)
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
                    **classification,
                },
                crs=str(source.crs) if source.crs else None,
                transform=transform,
            )
