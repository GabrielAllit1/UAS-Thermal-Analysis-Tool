from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ..inspections.models import InspectionResult
from ..thermal.statistics import TemperatureStatistics
from .annotations import write_finding_evidence
from .csv_report import write_findings_csv
from .evidence_cube import band_manifest, write_artifact_evidence_cube
from .geojson_report import write_geojson
from .json_report import finding_payload, write_findings_json
from .kml_report import write_findings_kml
from .pdf_report import write_pdf

if TYPE_CHECKING:
    from ..application.orchestrator import InspectionRun


def _aggregate_stats(run: InspectionRun) -> TemperatureStatistics:
    stats = [artifact.result.statistics for artifact in run.artifacts]
    valid = sum(item.valid_pixels for item in stats)
    if not stats or not valid:
        raise ValueError("inspection package requires at least one accepted radiometric artifact")
    weighted_mean = sum(item.mean_c * item.valid_pixels for item in stats) / valid
    weighted_median = sum(item.median_c * item.valid_pixels for item in stats) / valid
    weighted_std = sum(item.stddev_c * item.valid_pixels for item in stats) / valid
    weighted_p95 = sum(item.p95_c * item.valid_pixels for item in stats) / valid
    return TemperatureStatistics(
        minimum_c=min(item.minimum_c for item in stats),
        maximum_c=max(item.maximum_c for item in stats),
        mean_c=weighted_mean,
        median_c=weighted_median,
        stddev_c=weighted_std,
        p95_c=weighted_p95,
        valid_pixels=valid,
    )


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_engineering_evidence_appendix(
    report_dir: Path,
    *,
    evidence_cubes: list[dict[str, object]],
) -> tuple[Path, Path]:
    bands = band_manifest()
    payload = {
        "schema_version": "1.0",
        "title": "Thermal Evidence Cube Engineering Appendix",
        "authority_boundary": (
            "Band 1 is decoded Celsius radiometry. Bands 2-9 are deterministic derived evidence. "
            "Experimental residual bands do not alter finding identity, temperature, severity, "
            "confidence, or geolocation."
        ),
        "bands": bands,
        "cubes": evidence_cubes,
        "illumination_context": {
            "status": "supplemental-api-only",
            "note": (
                "RGB illumination/shadow context is available as a supplemental computation but is not "
                "registered into pixel-level finding evidence until an authoritative thermal-visible "
                "registration exists."
            ),
        },
    }
    json_path = report_dir / "engineering_evidence_appendix.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Thermal Evidence Cube Engineering Appendix",
        "",
        payload["authority_boundary"],
        "",
        "## Band contract",
        "",
        "| Band | Name | Unit | Authority | Experimental |",
        "|---:|---|---|---|---|",
    ]
    for band in bands:
        lines.append(
            f"| {band['band']} | {band['name']} | {band['unit']} | "
            f"{band['authority']} | {str(band['experimental']).lower()} |"
        )
    lines.extend(["", "## Generated cubes", ""])
    if evidence_cubes:
        for cube in evidence_cubes:
            lines.append(
                f"- `{cube.get('source', '')}`: {cube.get('status', 'unknown')}"
                + (f" -> `{cube.get('path')}`" if cube.get("path") else "")
            )
    else:
        lines.append("- No accepted radiometric artifacts were available for evidence export.")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "Derived evidence supports inspection review; it is not an independent temperature "
            "measurement, defect proof, standards certification, or thermographer certification.",
        ]
    )
    markdown_path = report_dir / "engineering_evidence_appendix.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def write_inspection_package(run: InspectionRun, output_dir: str | Path) -> Path:
    root = Path(output_dir) / (run.project.inspection_id or run.project.project_id or "inspection")
    report_dir = root / "report"
    findings_dir = root / "findings"
    annotated_dir = root / "annotated"
    maps_dir = root / "maps"
    evidence_dir = maps_dir / "evidence"
    data_dir = root / "data"
    for directory in (report_dir, findings_dir, annotated_dir, maps_dir, evidence_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)

    artifact_by_source = {
        str(Path(artifact.result.source)): artifact
        for artifact in run.artifacts
    }
    for finding in run.canonical_findings:
        finding_dir = findings_dir / (finding.finding_id or "finding")
        finding_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_by_source.get(str(Path(finding.source_path)))
        if artifact is not None:
            evidence = write_finding_evidence(artifact.frame, finding, finding_dir)
            overview_copy = annotated_dir / f"{finding.finding_id or 'finding'}.png"
            overview_copy.write_bytes(evidence["annotated"].read_bytes())
        (finding_dir / "finding.json").write_text(
            json.dumps(finding_payload(finding), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    evidence_cubes: list[dict[str, object]] = []
    for index, artifact in enumerate(run.artifacts, 1):
        source = str(Path(artifact.result.source))
        stem = Path(source).stem or "thermal"
        cube_path = evidence_dir / f"{index:03d}_{stem}_thermal_evidence.tif"
        try:
            cube = write_artifact_evidence_cube(artifact, run.profile, cube_path)
        except Exception as exc:
            evidence_cubes.append(
                {
                    "source": source,
                    "status": "unavailable",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        else:
            cube_payload = cube.as_dict()
            cube_payload["path"] = str(cube.path.relative_to(root)).replace("\\", "/")
            cube_payload["source"] = source
            cube_payload["status"] = "written"
            evidence_cubes.append(cube_payload)

    _write_engineering_evidence_appendix(report_dir, evidence_cubes=evidence_cubes)

    project_metadata = run.project.report_metadata()
    summary_payload = asdict(run.summary)
    write_findings_csv(
        run.canonical_findings,
        data_dir / "findings.csv",
        project=project_metadata,
    )
    write_findings_json(
        run.canonical_findings,
        data_dir / "findings.json",
        project=project_metadata,
        summary=summary_payload,
    )
    geojson_path = write_geojson(run.canonical_findings, data_dir / "findings.geojson")
    if geojson_path is not None:
        (maps_dir / "survey_overview.geojson").write_bytes(geojson_path.read_bytes())
    write_findings_kml(
        run.canonical_findings,
        data_dir / "findings.kml",
        project=project_metadata,
    )

    combined = InspectionResult(
        source="inspection dataset",
        adapter="multi-source",
        statistics=_aggregate_stats(run),
        findings=run.canonical_findings,
        metadata={
            "source_count": len(run.artifacts),
            "rejected_sources": [asdict(item) for item in run.failures],
            "statistics_note": (
                "Inspection-level median/stddev/p95 are weighted summaries of per-frame statistics; "
                "finding temperatures remain source-frame quantitative values."
            ),
            "thermal_evidence_cubes": evidence_cubes,
            "thermal_evidence_band_manifest": band_manifest(),
        },
        project=project_metadata,
        profile=run.profile.as_dict(),
        summary=run.summary,
        quality={
            "status": "pass_with_warnings" if run.failures else "pass",
            "warnings": [
                f"{len(run.failures)} source(s) were rejected and excluded from quantitative results"
            ] if run.failures else [],
            "reasons": [],
        },
    )
    write_pdf(combined, report_dir / "inspection_report.pdf")

    files = [path for path in root.rglob("*") if path.is_file()]
    manifest = {
        "schema_version": "1.1",
        "project": project_metadata,
        "profile": run.profile.as_dict(),
        "summary": summary_payload,
        "claim_boundary": (
            "Automated thermal analysis and anomaly classification generated by UAS Thermal Analysis; "
            "this package is not thermographer certification. Evidence cube band 1 preserves decoded "
            "Celsius radiometry while all other evidence bands are derived."
        ),
        "failures": [asdict(item) for item in run.failures],
        "thermal_evidence": {
            "bands": band_manifest(),
            "cubes": evidence_cubes,
        },
        "files": {
            str(path.relative_to(root)).replace("\\", "/"): {
                "sha256": _hash_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(files)
        },
    }
    manifest_path = root / "inspection_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return root
