from __future__ import annotations

from dataclasses import dataclass

from ..inspections.models import Finding
from .display import DisplayRaster
from .transforms import map_to_pixel, transform_point


@dataclass(frozen=True, slots=True)
class DisplayFindingPoint:
    finding_id: str
    x: float
    y: float
    severity: str


def finding_to_display_point(
    finding: Finding,
    display: DisplayRaster,
) -> DisplayFindingPoint | None:
    """Project a geolocated finding onto a bounded display preview."""

    if finding.latitude is None or finding.longitude is None:
        return None
    if not display.crs or display.transform is None:
        return None
    try:
        map_x, map_y = transform_point(
            float(finding.longitude),
            float(finding.latitude),
            "EPSG:4326",
            display.crs,
        )
        source_x, source_y = map_to_pixel(map_x, map_y, display.transform)
    except (RuntimeError, ValueError):
        return None
    source_width = float(display.metadata.get("source_width", 0) or 0)
    source_height = float(display.metadata.get("source_height", 0) or 0)
    preview_width = float(display.metadata.get("preview_width", 0) or 0)
    preview_height = float(display.metadata.get("preview_height", 0) or 0)
    if min(source_width, source_height, preview_width, preview_height) <= 0:
        return None
    x = source_x * preview_width / source_width
    y = source_y * preview_height / source_height
    if not (0 <= x < preview_width and 0 <= y < preview_height):
        return None
    return DisplayFindingPoint(
        finding_id=finding.finding_id,
        x=float(x),
        y=float(y),
        severity=finding.severity.value,
    )
