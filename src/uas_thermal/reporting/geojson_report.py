from __future__ import annotations

import json
from pathlib import Path

from ..inspections.models import Finding
from .json_report import finding_payload


def write_geojson(findings: list[Finding], path: str | Path) -> Path | None:
    geolocated = [item for item in findings if item.latitude is not None and item.longitude is not None]
    if not geolocated:
        return None
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    features = []
    for finding in geolocated:
        properties = finding_payload(finding)
        properties.pop("latitude", None)
        properties.pop("longitude", None)
        features.append(
            {
                "type": "Feature",
                "id": finding.finding_id or None,
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(finding.longitude), float(finding.latitude)],
                },
                "properties": properties,
            }
        )
    payload = {"type": "FeatureCollection", "features": features}
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return destination
