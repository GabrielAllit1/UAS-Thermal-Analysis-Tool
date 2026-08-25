from __future__ import annotations


def pixel_to_map(
    pixel_x: float,
    pixel_y: float,
    transform: tuple[float, ...],
    *,
    center: bool = True,
) -> tuple[float, float]:
    if len(transform) < 6:
        raise ValueError("affine transform must contain at least six coefficients")
    a, b, c, d, e, f = transform[:6]
    x = pixel_x + 0.5 if center else pixel_x
    y = pixel_y + 0.5 if center else pixel_y
    return a * x + b * y + c, d * x + e * y + f


def transform_point(
    x: float,
    y: float,
    source_crs: str,
    target_crs: str = "EPSG:4326",
) -> tuple[float, float]:
    normalized = source_crs.upper().replace(" ", "")
    target_normalized = target_crs.upper().replace(" ", "")
    if normalized in {"EPSG:4326", "WGS84", "WGS1984"} and target_normalized == "EPSG:4326":
        return x, y
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError("Install the geospatial extra to transform coordinates") from exc
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transformer.transform(x, y)
