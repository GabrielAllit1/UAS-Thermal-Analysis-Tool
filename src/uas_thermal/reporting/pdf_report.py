from __future__ import annotations

from pathlib import Path

from ..inspections.models import InspectionResult
from ..inspections.recommendations import maintenance_recommendation


def write_pdf(
    result: InspectionResult,
    path: str | Path,
    title: str | None = None,
) -> Path:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("Install the reporting extra to generate PDF reports") from exc

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    report_title = title or result.project.get("report_title") or "Thermal Inspection Report"
    pdf = canvas.Canvas(str(destination), pagesize=letter)
    _, height = letter
    pdf.setTitle(report_title)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, height - 60, report_title)
    pdf.setFont("Helvetica", 10)

    y = height - 84
    project_fields = (
        ("Project", result.project.get("name")),
        ("Site", result.project.get("site")),
        ("Client", result.project.get("client")),
        ("Operator", result.project.get("operator")),
        ("Inspection date", result.project.get("inspection_date")),
        ("Asset type", result.project.get("asset_type")),
        ("Sensor", " ".join(filter(None, [result.project.get("sensor_vendor"), result.project.get("sensor_model")]))),
    )
    for label, value in project_fields:
        if value:
            pdf.drawString(54, y, f"{label}: {value}")
            y -= 14
    pdf.drawString(54, y, f"Source: {result.source}")
    y -= 14
    pdf.drawString(54, y, f"Adapter: {result.adapter}")
    y -= 14
    pdf.drawString(54, y, f"Findings: {len(result.findings)}")
    y -= 14
    stats = result.statistics
    pdf.drawString(
        54,
        y,
        f"Temperature: min {stats.minimum_c:.1f} °C | mean {stats.mean_c:.1f} °C | max {stats.maximum_c:.1f} °C",
    )
    y -= 26

    for index, finding in enumerate(result.findings, 1):
        if y < 100:
            pdf.showPage()
            y = height - 60
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(54, y, f"Finding {index} · {finding.severity.value.upper()}")
        y -= 14
        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            66,
            y,
            f"Max {finding.max_temperature_c:.1f} °C · ΔT {finding.delta_temperature_c:.1f} °C · Area {finding.area_px} px",
        )
        y -= 13
        if finding.latitude is not None and finding.longitude is not None:
            pdf.drawString(66, y, f"Location {finding.latitude:.6f}, {finding.longitude:.6f}")
            y -= 13
        recommendation = maintenance_recommendation(finding)
        pdf.drawString(66, y, recommendation[:100])
        y -= 24
    pdf.save()
    return destination
