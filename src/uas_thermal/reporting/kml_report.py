from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..inspections.models import InspectionResult


def write_kml(result: InspectionResult, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(root, "Document")
    ET.SubElement(document, "name").text = result.project.get("name") or "Thermal Inspection"
    context = [
        result.project.get("site", ""),
        result.project.get("client", ""),
        result.project.get("inspection_date", ""),
    ]
    ET.SubElement(document, "description").text = " | ".join(item for item in context if item)
    for index, finding in enumerate(result.findings, 1):
        if finding.latitude is None or finding.longitude is None:
            continue
        placemark = ET.SubElement(document, "Placemark")
        ET.SubElement(placemark, "name").text = f"Thermal finding {index}"
        ET.SubElement(placemark, "description").text = (
            f"Severity: {finding.severity.value}; ΔT: {finding.delta_temperature_c:.1f} °C; "
            f"Max: {finding.max_temperature_c:.1f} °C"
        )
        point = ET.SubElement(placemark, "Point")
        ET.SubElement(point, "coordinates").text = f"{finding.longitude},{finding.latitude},0"
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return destination
