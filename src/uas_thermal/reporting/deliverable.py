from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import html
import json
from pathlib import Path
import shutil
from typing import Any, TYPE_CHECKING

import numpy as np

from ..inspections.models import Finding
from ..thermal.presentation import ThermalStyle, render_with_style
from .json_report import finding_payload
from .package import write_inspection_package
from .thermograms import write_tuned_thermograms

if TYPE_CHECKING:
    from ..application.orchestrator import InspectionRun
    from ..orthomosaic.base import OrthomosaicResult
    from ..sensors.base import ThermalFrame


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _overview_image(
    frame: ThermalFrame,
    findings: list[Finding],
    output_path: Path,
    style: ThermalStyle,
) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Install the reporting extra to render client deliverables") from exc

    rgb, _ = render_with_style(frame.temperature_c, style)
    image = Image.fromarray(np.asarray(rgb, dtype=np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    metadata = frame.metadata or {}
    source_width = int(metadata.get("source_width") or image.width)
    source_height = int(metadata.get("source_height") or image.height)
    scale_x = image.width / max(source_width, 1)
    scale_y = image.height / max(source_height, 1)
    colors = {
        "critical": (230, 50, 50),
        "moderate": (255, 160, 20),
        "minor": (255, 220, 40),
    }
    for finding in findings:
        if finding.bbox is None:
            source_box = (
                finding.center_x - 8,
                finding.center_y - 8,
                finding.center_x + 8,
                finding.center_y + 8,
            )
        else:
            source_box = finding.bbox
        box = tuple(
            round(value * (scale_x if index % 2 == 0 else scale_y))
            for index, value in enumerate(source_box)
        )
        color = colors.get(finding.severity.value, (255, 255, 255))
        draw.rectangle(box, outline=color, width=3)
        label = (
            f"{finding.finding_id or 'finding'} | {finding.delta_temperature_c:+.1f} C | "
            f"{finding.severity.value.upper()}"
        )
        x = max(0, box[0])
        y = max(0, box[1] - 16)
        draw.text(
            (x + 2, y + 2),
            label,
            fill=(255, 255, 255),
            font=font,
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def _client_html(run: InspectionRun, overview_name: str, output_path: Path) -> Path:
    findings = [finding_payload(item) for item in run.canonical_findings]
    embedded = json.dumps(findings, ensure_ascii=False).replace("</", "<\\/")
    project_name = html.escape(run.project.name)
    site = html.escape(run.project.site or run.project.location or "")
    output_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{project_name} - Thermal Intelligence Deliverable</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#071019;color:#e9f4fb}}
header{{padding:22px 28px;background:#0b1b27;border-bottom:1px solid #174158}}
.brand{{font-size:11px;letter-spacing:1.6px;color:#56d7ff;font-weight:800}}
main{{display:grid;grid-template-columns:minmax(0,2fr) minmax(360px,1fr);gap:18px;padding:20px}}
.card{{background:#0d1c27;border:1px solid #24475c;border-radius:10px;padding:14px}}
img{{width:100%;height:auto;background:#080c10}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #29475a;text-align:left}}
select,input{{background:#07131c;color:#e9eef3;border:1px solid #405e70;padding:7px;border-radius:4px}}
.small{{color:#9bacba;font-size:12px}}.critical{{color:#ff6868}}.moderate{{color:#ffb24d}}.minor{{color:#ffe36a}}
.ai{{border-left:3px solid #56d7ff;padding-left:10px;margin-top:10px;color:#c8edf9}}
@media(max-width:900px){{main{{grid-template-columns:1fr}}}}
</style></head>
<body>
<header><div class="brand">UAS THERMAL INTELLIGENCE · AUTONOMOUS DELIVERABLE</div><h1>{project_name}</h1><div>{site}</div><div class="small">Automated thermal inspection intelligence. Not thermographer certification.</div></header>
<main>
<section class="card"><img src="../maps/{html.escape(overview_name)}" alt="Annotated thermal overview"></section>
<section class="card">
<div style="display:flex;gap:8px;margin-bottom:10px"><select id="severity"><option value="">All severities</option><option>critical</option><option>moderate</option><option>minor</option></select><input id="search" placeholder="Search findings"></div>
<table><thead><tr><th>ID</th><th>Finding</th><th>Severity</th><th>Max</th><th>Delta T</th></tr></thead><tbody id="rows"></tbody></table>
<div id="detail" class="small" style="margin-top:16px"></div>
</section></main>
<script>
const findings={embedded};
const rows=document.getElementById('rows'),detail=document.getElementById('detail');
function esc(v){{const e=document.createElement('div');e.textContent=String(v??'');return e.innerHTML}}
function draw(){{const sev=document.getElementById('severity').value,q=document.getElementById('search').value.toLowerCase();rows.innerHTML='';findings.filter(f=>(!sev||f.severity===sev)&&(!q||JSON.stringify(f).toLowerCase().includes(q))).forEach(f=>{{const tr=document.createElement('tr');tr.innerHTML=`<td>${{esc(f.finding_id||'')}}</td><td>${{esc(f.classification||f.finding_type||'')}}</td><td class="${{esc(f.severity)}}">${{esc(f.severity)}}</td><td>${{Number(f.max_temperature_c).toFixed(1)}} C</td><td>${{Number(f.delta_temperature_c).toFixed(1)}} C</td>`;tr.onclick=()=>{{const ai=f.ai_enrichment&&f.ai_enrichment.summary?`<div class="ai"><b>AI-assisted context:</b> ${{esc(f.ai_enrichment.summary)}}<br><span class="small">Supplemental interpretation only; deterministic radiometry remains authoritative.</span></div>`:'';detail.innerHTML=`<b>${{esc(f.finding_id)}}</b><br>${{esc(f.classification||f.finding_type)}}<br><b>Evidence:</b> ${{esc((f.evidence||[]).join('; '))}}<br><b>Recommended action:</b> ${{esc(f.recommendation||'')}}${{ai}}`}};rows.appendChild(tr)}})}}
document.getElementById('severity').onchange=draw;document.getElementById('search').oninput=draw;draw();
</script></body></html>""",
        encoding="utf-8",
    )
    return output_path


def _refresh_manifest(root: Path, metadata: dict[str, Any]) -> None:
    manifest_path = root / "inspection_manifest.json"
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    ]
    manifest["schema_version"] = "1.2"
    manifest["deliverable"] = metadata
    manifest["files"] = {
        str(path.relative_to(root)).replace("\\", "/"): {
            "sha256": _hash_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(files)
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def write_client_deliverable(
    run: InspectionRun,
    output_dir: str | Path,
    *,
    orthomosaic: OrthomosaicResult | None = None,
    style: ThermalStyle | None = None,
    processing_metadata: dict[str, Any] | None = None,
) -> Path:
    """Build a shareable, deterministic package for clients and engineering teams."""

    root = write_inspection_package(run, output_dir)
    maps_dir = root / "maps"
    viewer_dir = root / "viewer"
    report_dir = root / "report"
    thermogram_dir = maps_dir / "thermograms"
    maps_dir.mkdir(exist_ok=True)
    viewer_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)

    active_style = style or ThermalStyle(palette="ironbow")
    if orthomosaic is not None and orthomosaic.orthomosaic.is_file():
        target = maps_dir / "thermal_orthomosaic.tif"
        if orthomosaic.orthomosaic.resolve() != target.resolve():
            shutil.copy2(orthomosaic.orthomosaic, target)

    if not run.artifacts:
        raise ValueError("client deliverable requires at least one quantitative artifact")
    overview_path = maps_dir / "annotated_thermal_overview.png"
    _overview_image(
        run.artifacts[0].frame,
        run.canonical_findings,
        overview_path,
        active_style,
    )
    thermograms = write_tuned_thermograms(run.artifacts, thermogram_dir, style=active_style)
    _client_html(run, overview_path.name, viewer_dir / "index.html")

    metadata = processing_metadata or {}
    processing = {
        "project": run.project.report_metadata(),
        "profile": run.profile.as_dict(),
        "summary": asdict(run.summary),
        "orthomosaic": None if orthomosaic is None else {
            "backend": orthomosaic.backend,
            "quantitative": orthomosaic.quantitative,
            "temperature_unit": orthomosaic.temperature_unit,
            "source_count": orthomosaic.source_count,
            "processing_report": None if orthomosaic.processing_report is None else str(orthomosaic.processing_report),
        },
        "thermal_style": active_style.as_dict(),
        "calibration": metadata.get("calibration", {}),
        "ai": metadata.get("ai", metadata),
        "automation": metadata.get("automation", {}),
        "rendered_thermograms": len(thermograms),
        "claim_boundary": (
            "AI-assisted interpretation is supplemental. Quantitative radiometry, finding geometry, "
            "severity and confidence are produced by deterministic authorities and require field "
            "verification appropriate to the inspection domain. Thermal palettes and Span/Level affect "
            "presentation only and never alter temperature measurements."
        ),
    }
    (report_dir / "processing_report.json").write_text(
        json.dumps(processing, indent=2, default=str),
        encoding="utf-8",
    )
    _refresh_manifest(
        root,
        {
            "type": "autonomous-thermal-intelligence-client-engineering-package",
            "overview": "maps/annotated_thermal_overview.png",
            "thermograms": "maps/thermograms/thermogram_index.json",
            "viewer": "viewer/index.html",
            "processing_report": "report/processing_report.json",
            "quantitative_orthomosaic": (
                "maps/thermal_orthomosaic.tif" if orthomosaic is not None else None
            ),
        },
    )
    return root
