from __future__ import annotations

from pathlib import Path

from ..inspections.models import InspectionResult
from ..inspections.recommendations import maintenance_recommendation


def write_pdf(result: InspectionResult, path: str | Path, title: str = "Thermal Inspection Report") -> Path:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("Install the reporting extra to generate PDF reports") from exc

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(destination), pagesize=letter)
    width, height = letter
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, height - 60, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(54, height - 82, f"Source: {result.source}")
    pdf.drawString(54, height - 98, f"Adapter: {result.adapter}")
    pdf.drawString(54, height - 114, f"Findings: {len(result.findings)}")
    y = height - 150
    for index, finding in enumerate(result.findings, 1):
        if y < 90:
            pdf.showPage()
            y = height - 60
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(54, y, f"Finding {index} · {finding.severity.value.upper()}")
        y -= 14
        pdf.setFont("Helvetica", 9)
        pdf.drawString(66, y, f"Max {finding.max_temperature_c:.1f} °C · ΔT {finding.delta_temperature_c:.1f} °C · Area {finding.area_px} px")
        y -= 13
        recommendation = maintenance_recommendation(finding)
        pdf.drawString(66, y, recommendation[:100])
        y -= 24
    pdf.save()
    return destination
