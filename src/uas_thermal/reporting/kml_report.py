from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..inspections.models import Finding, InspectionResult


def write_findings_kml(
    findings: list[Finding],
    path: str | Path,
    *,
    project: dict[str, Any] | None = None,
) -> Path | None:
    geolocated = [item for item in findings if item.latitude is not None and item.longitude is not None]
    if not geolocated:
        return None
    project = project or {}
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(root, "Document")
    ET.SubElement(document, "name").text = project.get("name") or "Thermal Inspection"
    context = [project.get("site", ""), project.get("client", ""), project.get("inspection_date", "")]
    ET.SubElement(document, "description").text = " | ".join(item for item in context if item)
    for index, finding in enumerate(geolocated, 1):
        placemark = ET.SubElement(document, "Placemark")
        ET.SubElement(placemark, "name").text = finding.finding_id or f"Thermal finding {index}"
        ET.SubElement(placemark, "description").text = (
            f"Classification: {finding.classification or finding.finding_type}; "
            f"Severity: {finding.severity.value}; Confidence: {finding.confidence.value}; "
            f"ΔT: {finding.delta_temperature_c:.1f} °C; "
            f"Max: {finding.max_temperature_c:.1f} °C"
        )
        point = ET.SubElement(placemark, "Point")
        ET.SubElement(point, "coordinates").text = f"{finding.longitude},{finding.latitude},0"
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return destination


def write_kml(result: InspectionResult, path: str | Path) -> Path:
    written = write_findings_kml(result.findings, path, project=result.project)
    if written is None:
        # Preserve historical contract for callers that only invoke write_kml when coordinates exist.
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        document = ET.SubElement(root, "Document")
        ET.SubElement(document, "name").text = result.project.get("name") or "Thermal Inspection"
        ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
        return destination
    return written
