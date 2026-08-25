from __future__ import annotations

import re


def create_workspace_window(session):
    """Add a zero-setup learning mission to the one-click Autopilot workspace."""

    from PyQt5.QtCore import QThread, QTimer, pyqtSignal
    from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

    from ..platform.config import AppConfig
    from ..validation.demo_mission import materialize_demo_mission
    from .mission_intake import MissionIntake, scan_mission_folder
    from .projects import Project
    from .workspace_ui_v6 import create_workspace_window as create_v6_workspace

    app, window = create_v6_workspace(session)
    config = AppConfig.from_env()

    start_card = window.findChild(QFrame, "startMissionCard")
    if start_card is None or start_card.layout() is None:
        raise RuntimeError("One-click Autopilot start card was not found")

    demo_row = QHBoxLayout()
    demo_button = QPushButton("RUN BUNDLED DEMO")
    demo_button.setObjectName("demoMissionButton")
    demo_copy = QLabel(
        "New here? Run the synthetic solar-farm mission. No files or setup required; Autopilot "
        "creates calibrated thermal tiles, stitches, analyzes, annotates, and packages the result."
    )
    demo_copy.setObjectName("muted")
    demo_copy.setWordWrap(True)
    demo_row.addWidget(demo_button)
    demo_row.addWidget(demo_copy, 1)
    # Place learning directly below the primary mission action row and above the privacy notice.
    start_card.layout().insertLayout(4, demo_row)

    window.setStyleSheet(
        window.styleSheet()
        + """
        QPushButton#demoMissionButton {
            background:#132937;
            color:#7be8ff;
            border:1px solid #2c718b;
            border-radius:8px;
            padding:10px 16px;
            min-height:22px;
            font-weight:800;
        }
        QPushButton#demoMissionButton:hover { background:#193748; border-color:#55c8e8; }
        QPushButton#demoMissionButton:disabled { color:#607985; border-color:#29404a; }
        """
    )

    existing_run = next(
        (button for button in window.findChildren(QPushButton) if button.text() == "RUN AUTOPILOT"),
        None,
    )
    if existing_run is None:
        raise RuntimeError("Autopilot action was not found in the workspace")

    mission_state = window.findChild(QLabel, "missionState")

    def _mission_detail_label() -> QLabel | None:
        if mission_state is None:
            return None
        parent = mission_state.parentWidget()
        if parent is None:
            return None
        labels = parent.findChildren(QLabel)
        try:
            index = labels.index(mission_state)
        except ValueError:
            return None
        return labels[index + 1] if index + 1 < len(labels) else None

    mission_detail = _mission_detail_label()

    def _slug(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
        return normalized or "thermal-mission"

    def _find_output_edit() -> QLineEdit | None:
        return next(
            (edit for edit in window.findChildren(QLineEdit) if "deliverables" in edit.text().lower()),
            None,
        )

    class DemoWorker(QThread):
        completed = pyqtSignal(object)
        failed = pyqtSignal(str)

        def run(self):
            try:
                root = materialize_demo_mission(config.data_dir / "demo")
                intake = scan_mission_folder(root, registry=session.workflow.registry)
                self.completed.emit(intake)
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def apply_demo(intake: MissionIntake) -> None:
        if not intake.analysis_sources:
            demo_button.setEnabled(True)
            QMessageBox.critical(
                window,
                "Demo Mission Could Not Start",
                "The synthetic demo was created but no quantitative thermal source was accepted. "
                "Verify the geospatial/rasterio installation and retry.",
            )
            return

        window.autopilot_last_result = None
        session.project = Project(
            name=intake.project_name,
            site="Synthetic Solar Farm Demo",
            profile_id="photovoltaic",
            description="Bundled synthetic Autopilot learning and functional-acceptance mission.",
            metadata={
                "autopilot_intake_root": str(intake.root),
                "autopilot_context_files": [str(path) for path in intake.context_files],
                "autopilot_intake_mode": "bundled-demo",
                "synthetic_demo": True,
            },
        )
        session.set_sources(list(intake.analysis_sources))
        session.project.add_dataset(
            list(intake.analysis_sources),
            name="Synthetic calibrated thermal tiles",
            data_type="thermal-radiometric",
        )
        if intake.context_files:
            session.project.add_dataset(
                list(intake.context_files),
                name="Synthetic demo context / GIS",
                data_type="context",
            )

        profile_combo = getattr(window, "profile_combo", None)
        if profile_combo is not None:
            index = profile_combo.findData("photovoltaic")
            if index >= 0:
                profile_combo.setCurrentIndex(index)

        destination = config.data_dir / "deliverables" / _slug(intake.project_name)
        output_edit = _find_output_edit()
        if output_edit is not None:
            output_edit.setText(str(destination))

        window.refresh_all()
        if mission_state is not None:
            mission_state.setText("DEMO READY · AUTOPILOT STARTING")
        if mission_detail is not None:
            mission_detail.setText(
                f"{len(intake.analysis_sources)} calibrated synthetic thermal tiles · photovoltaic "
                f"profile · quantitative stitch + analysis + deliverable · {destination}"
            )
        QTimer.singleShot(150, existing_run.click)

    def demo_failed(message: str) -> None:
        demo_button.setEnabled(True)
        if mission_state is not None:
            mission_state.setText("DEMO MISSION FAILED TO MATERIALIZE")
        if mission_detail is not None:
            mission_detail.setText(message)
        QMessageBox.critical(window, "Demo Mission Failed", message)

    def run_demo() -> None:
        demo_button.setEnabled(False)
        if mission_state is not None:
            mission_state.setText("BUILDING SYNTHETIC DEMO · NO ACTION REQUIRED")
        if mission_detail is not None:
            mission_detail.setText(
                "Creating a small deterministic radiometric solar-farm mission in the local app data "
                "directory. No download or customer data is used."
            )
        worker = DemoWorker(window)
        window.demo_mission_worker = worker
        worker.completed.connect(apply_demo)
        worker.failed.connect(demo_failed)
        worker.start()

    def watch_demo() -> None:
        worker = getattr(window, "demo_mission_worker", None)
        autopilot_worker = getattr(window, "autopilot_worker", None)
        if worker is not None and worker.isRunning():
            return
        if autopilot_worker is not None and autopilot_worker.isRunning():
            return
        demo_button.setEnabled(True)

    demo_button.clicked.connect(run_demo)
    demo_timer = QTimer(window)
    demo_timer.setInterval(600)
    demo_timer.timeout.connect(watch_demo)
    demo_timer.start()
    window.demo_mission_timer = demo_timer
    window.demo_mission_button = demo_button
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
