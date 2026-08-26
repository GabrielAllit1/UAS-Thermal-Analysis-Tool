from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.mission_intake import scan_mission_folder
from uas_thermal.application.projects import Project
from uas_thermal.application.universal_pipeline import UniversalProcessingPlan, UniversalThermalProcessor
from uas_thermal.application.workspace_ui_v9 import create_workspace_window
from uas_thermal.validation.demo_mission import materialize_demo_mission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("build/ui-qa"))
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="uas-thermal-result-qa-") as temp_dir:
        root = Path(temp_dir)
        mission_root = materialize_demo_mission(root / "mission")
        intake = scan_mission_folder(mission_root)
        project = Project(
            name=intake.project_name,
            site="Synthetic Solar Farm Demo",
            profile_id=intake.profile_id,
            metadata={"synthetic_demo": True, "visual_qa": True},
        )
        result = UniversalThermalProcessor().process(
            project,
            list(intake.analysis_sources),
            root / "deliverables",
            plan=UniversalProcessingPlan(
                stitch_mode="on",
                orthomosaic_backend="native-geotiff",
                ai_mode="off",
            ),
        )
        session = DesktopSession(project=project)
        session.set_sources(list(intake.analysis_sources))
        session.last_run = result.run
        session.artifacts = list(result.run.artifacts)

        app, window = create_workspace_window(session)
        window.autopilot_last_result = result
        window.present_consumer_result(result)
        window.nav.setCurrentRow(window.page_index["Autopilot"])
        window.resize(1366, 768)
        window.show()
        app.processEvents()
        window.refresh_consumer_home()
        app.processEvents()

        destination = args.output_dir / "guided-result-1366x768.png"
        if not window.grab().save(str(destination), "PNG"):
            raise RuntimeError(f"failed to capture {destination}")
        if destination.stat().st_size <= 0:
            raise RuntimeError(f"empty completed-result visual QA capture: {destination}")

        if hasattr(window, "runtime_monitor"):
            window.runtime_monitor.close()
        window.close()
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
