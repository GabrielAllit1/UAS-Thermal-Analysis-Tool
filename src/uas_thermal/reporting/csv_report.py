from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from ..inspections.models import InspectionResult

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


def write_csv(result: InspectionResult, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    project = result.project
    project_values = {
        "project_name": project.get("name", ""),
        **{column: project.get(column, "") for column in _PROJECT_COLUMNS if column != "project_name"},
    }
    for index, finding in enumerate(result.findings, 1):
        row = asdict(finding)
        row.update(project_values)
        row["id"] = index
        row["source"] = result.source
        row["adapter"] = result.adapter
        row["severity"] = finding.severity.value
        rows.append(row)
    fieldnames = [
        *_PROJECT_COLUMNS,
        "source",
        "adapter",
        "id",
        "finding_type",
        "severity",
        "center_x",
        "center_y",
        "area_px",
        "max_temperature_c",
        "mean_temperature_c",
        "baseline_temperature_c",
        "delta_temperature_c",
        "latitude",
        "longitude",
        "notes",
    ]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return destination
