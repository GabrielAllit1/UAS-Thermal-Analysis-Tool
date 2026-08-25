from __future__ import annotations

from pathlib import Path

import numpy as np

from .base import AdapterUnavailableError, ThermalFrame, ThermalSensorAdapter
from ..thermal.calibration import ThermalCalibration
from ..thermal.radiometry import apply_scale_offset


class GenericGeoTiffAdapter(ThermalSensorAdapter):
    name = "generic-geotiff"
    vendor = "generic"
    support_level = "foundation"

    def __init__(self, scale: float = 1.0, offset: float = 0.0):
        self.scale = scale
        self.offset = offset

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in {".tif", ".tiff"}

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        try:
            import rasterio
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to read GeoTIFF files") from exc

        with rasterio.open(path) as source:
            raw = source.read(1, masked=True).filled(np.nan)
            tags = source.tags()
            scale = float(tags.get("THERMAL_SCALE", self.scale))
            offset = float(tags.get("THERMAL_OFFSET", self.offset))
            temperature_c = apply_scale_offset(raw, scale, offset)
            transform = tuple(source.transform)[:6]
            return ThermalFrame(
                temperature_c=temperature_c,
                source=path,
                metadata={
                    "driver": source.driver,
                    "width": source.width,
                    "height": source.height,
                    "count": source.count,
                    "tags": tags,
                    "calibration": calibration,
                    "scale": scale,
                    "offset": offset,
                },
                crs=str(source.crs) if source.crs else None,
                transform=transform,
            )
