from __future__ import annotations

from dataclasses import asdict
import csv
from pathlib import Path

from ..inspections.models import InspectionResult


def write_csv(result: InspectionResult, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, finding in enumerate(result.findings, 1):
        row = asdict(finding)
        row["id"] = index
        row["severity"] = finding.severity.value
        rows.append(row)
    fieldnames = ["id", "finding_type", "severity", "center_x", "center_y", "area_px",
                  "max_temperature_c", "mean_temperature_c", "baseline_temperature_c",
                  "delta_temperature_c", "latitude", "longitude", "notes"]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return destination
