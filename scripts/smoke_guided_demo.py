from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import tempfile

from uas_thermal.application.mission_intake import scan_mission_folder
from uas_thermal.application.projects import Project
from uas_thermal.application.universal_pipeline import UniversalProcessingPlan, UniversalThermalProcessor
from uas_thermal.validation.demo_mission import bundled_demo_blueprint, materialize_demo_mission


def run(output_root: Path) -> dict[str, object]:
    mission_root = materialize_demo_mission(output_root / "mission")
    intake = scan_mission_folder(mission_root)
    if not intake.ready or len(intake.analysis_sources) != 4:
        raise RuntimeError(
            f"guided demo intake failed: ready={intake.ready} sources={len(intake.analysis_sources)}"
        )

    project = Project(
        name=intake.project_name,
        site="Synthetic Solar Farm Demo",
        profile_id=intake.profile_id,
        metadata={"synthetic_demo": True, "smoke_test": True},
    )
    result = UniversalThermalProcessor().process(
        project,
        list(intake.analysis_sources),
        output_root / "deliverables",
        plan=UniversalProcessingPlan(
            stitch_mode="on",
            orthomosaic_backend="native-geotiff",
            ai_mode="off",
        ),
    )

    expected = bundled_demo_blueprint()
    findings = list(result.run.canonical_findings)
    severities = Counter(finding.severity.value for finding in findings)
    if len(findings) != expected["expected_canonical_findings"]:
        raise RuntimeError(
            f"guided demo finding count mismatch: expected {expected['expected_canonical_findings']}, "
            f"got {len(findings)}"
        )
    if dict(severities) != expected["expected_severity_counts"]:
        raise RuntimeError(
            f"guided demo severity mismatch: expected {expected['expected_severity_counts']}, "
            f"got {dict(severities)}"
        )

    required = (
        "report/inspection_report.pdf",
        "data/findings.csv",
        "data/findings.json",
        "maps/annotated_thermal_overview.png",
        "maps/thermal_orthomosaic.tif",
        "viewer/index.html",
        "report/processing_report.json",
        "inspection_manifest.json",
    )
    missing = [relative for relative in required if not (result.deliverable_dir / relative).is_file()]
    if missing:
        raise RuntimeError(f"guided demo deliverable missing: {missing}")

    return {
        "ok": True,
        "mission_root": str(mission_root),
        "deliverable_dir": str(result.deliverable_dir),
        "sources": len(intake.analysis_sources),
        "findings": len(findings),
        "severity_counts": dict(severities),
        "orthomosaic": str(result.orthomosaic.orthomosaic) if result.orthomosaic else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the bundled guided mission end to end")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)

    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        payload = run(args.output_dir)
    else:
        with tempfile.TemporaryDirectory(prefix="uas-thermal-guided-demo-") as temp_dir:
            payload = run(Path(temp_dir))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
