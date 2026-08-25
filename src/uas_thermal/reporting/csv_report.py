from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..inspections.models import Finding, InspectionResult

_PROJECT_COLUMNS = (
    "project_name",
    "site",
    "client",
    "operator",
    "inspection_id",
    "asset_type",
    "location",
    "inspection_date",
    "sensor_vendor",
    "sensor_model",
)

_FINDING_COLUMNS = (
    "finding_id",
    "classification",
    "severity",
    "confidence",
    "source_path",
    "source_image_id",
    "center_x",
    "center_y",
    "hotspot_x",
    "hotspot_y",
    "area_px",
    "min_temperature_c",
    "mean_temperature_c",
    "max_temperature_c",
    "reference_temperature_c",
    "reference_method",
    "delta_temperature_c",
    "latitude",
    "longitude",
    "profile_id",
    "profile_version",
    "analysis_engine_version",
    "lifecycle_status",
    "recommendation",
    "notes",
)


def _project_values(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_name": project.get("name", ""),
        **{
            column: project.get(column, "")
            for column in _PROJECT_COLUMNS
            if column != "project_name"
        },
    }


def _finding_row(finding: Finding) -> dict[str, Any]:
    row = asdict(finding)
    row["severity"] = finding.severity.value
    row["confidence"] = finding.confidence.value
    row["lifecycle_status"] = finding.lifecycle_status.value
    return row


def write_findings_csv(
    findings: list[Finding],
    path: str | Path,
    *,
    project: dict[str, Any] | None = None,
    source: str = "",
    adapter: str = "",
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    project_values = _project_values(project or {})
    rows = []
    for index, finding in enumerate(findings, 1):
        row = _finding_row(finding)
        row.update(project_values)
        row["id"] = index
        row["source"] = source or finding.source_path
        row["adapter"] = adapter or finding.radiometric_provenance.get("adapter", "")
        rows.append(row)
    fieldnames = [*_PROJECT_COLUMNS, "source", "adapter", "id", *_FINDING_COLUMNS]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return destination


def write_csv(result: InspectionResult, path: str | Path) -> Path:
    return write_findings_csv(
        result.findings,
        path,
        project=result.project,
        source=result.source,
        adapter=result.adapter,
    )
