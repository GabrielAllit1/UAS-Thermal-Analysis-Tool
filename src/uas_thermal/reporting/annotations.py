from __future__ import annotations

from pathlib import Path

import numpy as np

from ..inspections.models import Finding, Severity
from ..sensors.base import ThermalFrame


_SEVERITY_RGB = {
    Severity.CRITICAL: (220, 38, 38),
    Severity.MODERATE: (234, 138, 0),
    Severity.MINOR: (250, 204, 21),
}


def _display_rgb(frame: ThermalFrame) -> np.ndarray:
    if frame.display_rgb is not None:
        return np.asarray(frame.display_rgb, dtype=np.uint8).copy()
    values = np.asarray(frame.temperature_c, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros((*values.shape, 3), dtype=np.uint8)
    low, high = np.percentile(finite, [2, 98])
    if high <= low:
        high = low + 1.0
    scaled = np.clip((values - low) / (high - low), 0.0, 1.0)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=1.0, neginf=0.0)
    gray = np.round(scaled * 255).astype(np.uint8)
    return np.repeat(gray[:, :, None], 3, axis=2)


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Install the reporting extra to render annotated finding imagery") from exc
    return Image, ImageDraw, ImageFont


def render_annotated_frame(frame: ThermalFrame, finding: Finding):
    """Render finding evidence without modifying the quantitative temperature matrix."""

    Image, ImageDraw, ImageFont = _pillow()
    image = Image.fromarray(_display_rgb(frame), mode="RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    color = _SEVERITY_RGB.get(finding.severity, (255, 255, 255))
    bbox = finding.bbox or (
        max(0, finding.center_x - 8),
        max(0, finding.center_y - 8),
        min(image.width - 1, finding.center_x + 8),
        min(image.height - 1, finding.center_y + 8),
    )
    draw.rectangle(bbox, outline=color, width=3)
    if finding.polygon:
        draw.line([*finding.polygon, finding.polygon[0]], fill=color, width=2)
    hx = finding.hotspot_x if finding.hotspot_x is not None else finding.center_x
    hy = finding.hotspot_y if finding.hotspot_y is not None else finding.center_y
    draw.line((hx - 7, hy, hx + 7, hy), fill=(255, 255, 255), width=2)
    draw.line((hx, hy - 7, hx, hy + 7), fill=(255, 255, 255), width=2)

    label = (
        f"{finding.finding_id or 'FINDING'}  {finding.max_temperature_c:.1f} C  "
        f"dT {finding.delta_temperature_c:+.1f} C  "
        f"{finding.severity.value.upper()} / {finding.confidence.value.upper()}"
    )
    text_box = draw.textbbox((0, 0), label, font=font)
    label_w = text_box[2] - text_box[0] + 10
    label_h = text_box[3] - text_box[1] + 8
    x = max(0, min(bbox[0], image.width - label_w))
    above_y = bbox[1] - label_h - 4
    y = above_y if above_y >= 0 else min(image.height - label_h, bbox[3] + 4)
    draw.rectangle((x, y, x + label_w, y + label_h), fill=(20, 24, 30), outline=color)
    draw.text((x + 5, y + 4), label, fill=(255, 255, 255), font=font)
    return image


def write_finding_evidence(
    frame: ThermalFrame,
    finding: Finding,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write reusable overview, crop and finding plate artifacts."""

    Image, ImageDraw, ImageFont = _pillow()
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    finding_id = finding.finding_id or "finding"
    overview = render_annotated_frame(frame, finding)
    overview_path = destination / "annotated_thermal.png"
    overview.save(overview_path)

    bbox = finding.bbox or (
        max(0, finding.center_x - 16),
        max(0, finding.center_y - 16),
        min(overview.width - 1, finding.center_x + 16),
        min(overview.height - 1, finding.center_y + 16),
    )
    margin = max(12, int(max(bbox[2] - bbox[0], bbox[3] - bbox[1]) * 0.5))
    crop_box = (
        max(0, bbox[0] - margin),
        max(0, bbox[1] - margin),
        min(overview.width, bbox[2] + margin + 1),
        min(overview.height, bbox[3] + margin + 1),
    )
    crop = overview.crop(crop_box)
    crop_path = destination / "thermal_crop.png"
    crop.save(crop_path)

    plate_w = max(1000, overview.width + 380)
    plate_h = max(700, overview.height + 80)
    plate = Image.new("RGB", (plate_w, plate_h), (245, 247, 250))
    draw = ImageDraw.Draw(plate)
    font = ImageFont.load_default()
    thumb = overview.copy()
    thumb.thumbnail((plate_w - 400, plate_h - 80))
    plate.paste(thumb, (24, 40))
    crop_thumb = crop.copy()
    crop_thumb.thumbnail((340, 220))
    panel_x = plate_w - 360
    plate.paste(crop_thumb, (panel_x, 56))
    lines = [
        finding_id,
        f"Classification: {finding.classification or finding.finding_type}",
        f"Severity: {finding.severity.value.upper()}",
        f"Confidence: {finding.confidence.value.upper()}",
        f"Maximum: {finding.max_temperature_c:.1f} C",
        f"Reference: {finding.reference_temperature_c if finding.reference_temperature_c is not None else finding.baseline_temperature_c:.1f} C",
        f"Delta T: {finding.delta_temperature_c:+.1f} C",
        f"Area: {finding.area_px} px",
        f"Reference: {finding.reference_method or 'not established'}",
    ]
    if finding.latitude is not None and finding.longitude is not None:
        lines.append(f"Location: {finding.latitude:.6f}, {finding.longitude:.6f}")
    lines.extend(["", "Evidence:"])
    lines.extend(f"- {item}" for item in finding.evidence[:5])
    lines.extend(["", "Recommendation:", finding.recommendation or finding.notes or "Field verification recommended."])
    y = 300
    for line in lines:
        draw.text((panel_x, y), line[:64], fill=(20, 28, 38), font=font)
        y += 18
    plate_path = destination / "finding_plate.png"
    plate.save(plate_path)

    finding.annotated_image_path = str(overview_path)
    finding.crop_path = str(crop_path)
    return {"annotated": overview_path, "crop": crop_path, "plate": plate_path}
