from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..inspections.models import InspectionResult
from .csv_report import write_csv
from .kml_report import write_kml
from .pdf_report import write_pdf


@dataclass(frozen=True, slots=True)
class ReportBundle:
    pdf: Path | None
    csv: Path
    kml: Path | None


def write_report_bundle(
    result: InspectionResult,
    output_dir: str | Path,
    *,
    stem: str | None = None,
    include_pdf: bool = True,
    include_kml: bool = True,
) -> ReportBundle:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    name = stem or Path(result.source).stem or "thermal-inspection"
    csv_path = write_csv(result, destination / f"{name}-findings.csv")
    pdf_path = write_pdf(result, destination / f"{name}-report.pdf") if include_pdf else None
    has_coordinates = any(
        finding.latitude is not None and finding.longitude is not None
        for finding in result.findings
    )
    kml_path = (
        write_kml(result, destination / f"{name}-findings.kml")
        if include_kml and has_coordinates
        else None
    )
    return ReportBundle(pdf=pdf_path, csv=csv_path, kml=kml_path)
