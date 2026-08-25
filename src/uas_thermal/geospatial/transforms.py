from __future__ import annotations


def transform_point(x: float, y: float, source_crs: str, target_crs: str = "EPSG:4326") -> tuple[float, float]:
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError("Install the geospatial extra to transform coordinates") from exc
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transformer.transform(x, y)
