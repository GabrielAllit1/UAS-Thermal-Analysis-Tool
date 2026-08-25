from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GeoTiffMetadata:
    width: int
    height: int
    bands: int
    crs: str | None
    resolution: tuple[float, float]


def inspect_geotiff(path: str | Path) -> GeoTiffMetadata:
    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("Install the geospatial extra to inspect GeoTIFF files") from exc
    with rasterio.open(path) as source:
        return GeoTiffMetadata(
            width=source.width,
            height=source.height,
            bands=source.count,
            crs=str(source.crs) if source.crs else None,
            resolution=(float(source.res[0]), float(source.res[1])),
        )
