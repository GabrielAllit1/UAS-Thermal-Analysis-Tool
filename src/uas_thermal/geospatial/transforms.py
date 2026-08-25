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


def crs_warning(source_crs: str) -> str | None:
    """Return a conservative warning for CRS text that is internally suspicious."""

    normalized = source_crs.upper().replace(" ", "")
    has_foot_label = any(token in normalized for token in ("FTUS", "USFOOT", "FOOT_US"))
    has_metre_unit = 'UNIT["METRE",1' in normalized or 'LENGTHUNIT["METRE",1' in normalized
    if has_foot_label and has_metre_unit:
        return "CRS name indicates US survey feet while its WKT declares metres"
    if "LOCAL_CS" in normalized or "LOCALCRS" in normalized:
        return "CRS is encoded as a local coordinate system and requires explicit verification"
    return None


def transform_point(
    x: float,
    y: float,
    source_crs: str,
    target_crs: str = "EPSG:4326",
    *,
    allow_suspicious_crs: bool = False,
) -> tuple[float, float]:
    warning = crs_warning(source_crs)
    if warning and not allow_suspicious_crs:
        raise ValueError(f"coordinate transform blocked: {warning}")
    normalized = source_crs.upper().replace(" ", "")
    target_normalized = target_crs.upper().replace(" ", "")
    if normalized in {"EPSG:4326", "WGS84", "WGS1984"} and target_normalized == "EPSG:4326":
        return x, y
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError("Install the geospatial extra to transform coordinates") from exc
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    lon, lat = transformer.transform(x, y)
    if target_normalized == "EPSG:4326" and not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("coordinate transform produced an implausible WGS84 location")
    return float(lon), float(lat)


def map_to_pixel(
    map_x: float,
    map_y: float,
    transform: tuple[float, ...],
) -> tuple[float, float]:
    """Invert a six-coefficient affine transform without requiring rasterio."""

    if len(transform) < 6:
        raise ValueError("affine transform must contain at least six coefficients")
    a, b, c, d, e, f = transform[:6]
    determinant = a * e - b * d
    if abs(determinant) < 1e-15:
        raise ValueError("affine transform is not invertible")
    x = map_x - c
    y = map_y - f
    pixel_x = (e * x - b * y) / determinant
    pixel_y = (-d * x + a * y) / determinant
    return pixel_x, pixel_y
