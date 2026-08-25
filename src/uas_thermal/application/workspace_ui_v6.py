from __future__ import annotations

import re
from pathlib import Path


def create_workspace_window(session):
    """Create the one-click operator-first Autopilot workspace.

    The normal path is intentionally one decision: choose the flight folder. Intake, project setup,
    profile selection, local AI routing, processing, annotation, and packaging are automatic. The
    detailed pages remain available for audit/review and advanced workflows, but they are not required
    to produce a deliverable.
    """

    from PyQt5.QtCore import QThread, QTimer, QUrl, pyqtSignal
    from PyQt5.QtGui import QDesktopServices
    from PyQt5.QtWidgets import (
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
    )

    from ..platform.config import AppConfig
    from .mission_intake import MissionIntake, scan_mission_files, scan_mission_folder
    from .projects import Project
    from .workspace_ui_v5 import create_workspace_window as create_v5_workspace

    app, window = create_v5_workspace(session)
    config = AppConfig.from_env()
    window.setWindowTitle("UAS Thermal Intelligence — One-Click Autopilot")
    window.setMinimumSize(1180, 720)

    # The previous mission-plan control strip remains accessible as Advanced Controls, but it is no
    # longer the first thing an operator has to understand.
    manual_plan = None
    for box in window.findChildren(QGroupBox):
        if box.title() == "Autonomous mission plan":
            manual_plan = box
            manual_plan.hide()
            break

    existing_run = None
    for button in window.findChildren(QPushButton):
        if button.text() == "RUN AUTOPILOT":
            existing_run = button
            break

    if existing_run is None:
        raise RuntimeError("Autopilot action was not found in the workspace")

    autopilot_page = window.pages.widget(window.page_index["Autopilot"])
    autopilot_layout = autopilot_page.layout()

    # Hide the older marketing hero. The new start card is action-oriented and answers the operator's
    # first question immediately: where do I put the flight data?
    for label in window.findChildren(QLabel):
        if label.text() == "From flight data to decision-ready thermal intelligence":
            parent = label.parentWidget()
            if parent is not None:
                parent.hide()
            break

    start_card = QFrame()
    start_card.setObjectName("startMissionCard")
    start_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    start_layout = QVBoxLayout(start_card)
    start_layout.setContentsMargins(24, 22, 24, 22)
    start_layout.setSpacing(10)

    start_eyebrow = QLabel("START HERE · ONE-CLICK THERMAL AUTOPILOT")
    start_eyebrow.setObjectName("eyebrow")
    start_title = QLabel("Choose the flight folder. Autopilot handles the rest.")
    start_title.setObjectName("oneClickTitle")
    start_subtitle = QLabel(
        "No upload workflow and no processing expertise required. Select the local folder containing "
        "the mission data; Thermal Intelligence automatically discovers compatible sources, creates "
        "the project, chooses the inspection profile and local AI routes, processes/stitches when "
        "appropriate, detects and annotates anomalies, and builds the client + engineering package."
    )
    start_subtitle.setObjectName("oneClickSub")
    start_subtitle.setWordWrap(True)
    start_layout.addWidget(start_eyebrow)
    start_layout.addWidget(start_title)
    start_layout.addWidget(start_subtitle)

    action_row = QHBoxLayout()
    choose_folder = QPushButton("SELECT FLIGHT FOLDER & RUN AUTOPILOT")
    choose_folder.setObjectName("oneClickPrimary")
    choose_files = QPushButton("Select mission files instead")
    choose_files.setObjectName("autopilotSecondary")
    advanced = QPushButton("Advanced controls")
    advanced.setObjectName("autopilotSecondary")
    action_row.addWidget(choose_folder, 2)
    action_row.addWidget(choose_files)
    action_row.addStretch(1)
    action_row.addWidget(advanced)
    start_layout.addLayout(action_row)

    privacy = QLabel("LOCAL-FIRST · Your source data is read in place; Autopilot does not require a cloud upload.")
    privacy.setObjectName("muted")
    start_layout.addWidget(privacy)

    mission_state = QLabel("READY FOR FLIGHT DATA")
    mission_state.setObjectName("missionState")
    mission_detail = QLabel(
        "After you choose a folder, there are no required setup screens. You can review advanced "
        "settings later if a project needs a non-default calibration assumption."
    )
    mission_detail.setObjectName("muted")
    mission_detail.setWordWrap(True)
    start_layout.addWidget(mission_state)
    start_layout.addWidget(mission_detail)

    autopilot_layout.insertWidget(2, start_card)

    deliverables_card = QFrame()
    deliverables_card.setObjectName("frontierCard")
    deliverables_layout = QHBoxLayout(deliverables_card)
    deliverables_layout.setContentsMargins(16, 10, 16, 10)
    deliverables_head = QVBoxLayout()
    deliverables_title = QLabel("AUTOMATIC DELIVERABLE")
    deliverables_title.setObjectName("eyebrow")
    deliverables_copy = QLabel(
        "Engineer-facing PDF · annotated finding plates · thermal imagery · quantitative GeoTIFF when "
        "available · CSV/JSON · GeoJSON/KML when authoritative · portable client viewer · provenance "
        "and SHA-256 manifest"
    )
    deliverables_copy.setObjectName("muted")
    deliverables_copy.setWordWrap(True)
    deliverables_head.addWidget(deliverables_title)
    deliverables_head.addWidget(deliverables_copy)
    deliverables_layout.addLayout(deliverables_head, 1)
    open_delivery = QPushButton("OPEN COMPLETED DELIVERABLE")
    open_delivery.setObjectName("autopilotSecondary")
    open_delivery.setEnabled(False)
    deliverables_layout.addWidget(open_delivery)
    autopilot_layout.insertWidget(3, deliverables_card)

    window.setStyleSheet(
        window.styleSheet()
        + """
        QFrame#startMissionCard {
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0b1c2a,stop:0.58 #0c1722,stop:1 #10121b);
            border:1px solid #24556d;
            border-radius:16px;
        }
        QLabel#oneClickTitle { color:#f5fbff; font-size:25pt; font-weight:800; }
        QLabel#oneClickSub { color:#9db5c5; font-size:11pt; }
        QLabel#missionState { color:#54e7ae; font-size:11pt; font-weight:800; padding-top:4px; }
        QPushButton#oneClickPrimary {
            background:#24d5ff;
            color:#021018;
            border:1px solid #66e4ff;
            border-radius:9px;
            padding:13px 18px;
            min-height:24px;
            font-size:11pt;
            font-weight:900;
        }
        QPushButton#oneClickPrimary:hover { background:#74e8ff; border-color:#a9f2ff; }
        """
    )

    class IntakeWorker(QThread):
        completed = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, mode: str, payload):
            super().__init__()
            self.mode = mode
            self.payload = payload

        def run(self):
            try:
                if self.mode == "folder":
                    result = scan_mission_folder(self.payload, registry=session.workflow.registry)
                else:
                    result = scan_mission_files(self.payload, registry=session.workflow.registry)
                self.completed.emit(result)
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _slug(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
        return normalized or "thermal-mission"

    def _find_output_edit() -> QLineEdit | None:
        for edit in window.findChildren(QLineEdit):
            if "deliverables" in edit.text().lower():
                return edit
        return None

    def _apply_intake(intake: MissionIntake) -> None:
        if not intake.discovered_files:
            QMessageBox.information(
                window,
                "No Mission Data Found",
                "No supported imagery or GIS files were found in that folder. Select the folder that "
                "contains the exported/original flight data.",
            )
            mission_state.setText("NO SUPPORTED MISSION DATA FOUND")
            choose_folder.setEnabled(True)
            choose_files.setEnabled(True)
            return
        if not intake.analysis_sources:
            QMessageBox.warning(
                window,
                "No Quantitative Thermal Source Detected",
                f"Autopilot found {len(intake.discovered_files)} supported file(s), but none can be "
                "decoded by an operational radiometric adapter on this workstation. Original "
                "radiometric R-JPEGs or calibrated thermal GeoTIFFs are required for quantitative "
                "analysis. Context/display files were not discarded.",
            )
            mission_state.setText("MISSION DISCOVERED · RADIOMETRY NEEDS A COMPATIBLE SOURCE")
            mission_detail.setText(str(intake.root))
            choose_folder.setEnabled(True)
            choose_files.setEnabled(True)
            return

        # A new one-click mission owns its project context. The operator can enrich the metadata later,
        # but no project-creation form is required to get a valid processing run started.
        session.project = Project(
            name=intake.project_name,
            site=intake.project_name,
            profile_id=intake.profile_id,
            metadata={
                "autopilot_intake_root": str(intake.root),
                "autopilot_context_files": [str(path) for path in intake.context_files],
                "autopilot_intake_mode": "one-click",
            },
        )
        session.set_sources(list(intake.analysis_sources))
        session.project.add_dataset(
            list(intake.analysis_sources),
            name="Autopilot thermal sources",
            data_type="thermal-radiometric",
        )
        if intake.context_files:
            session.project.add_dataset(
                list(intake.context_files),
                name="Autopilot context / GIS",
                data_type="context",
            )

        profile_combo = getattr(window, "profile_combo", None)
        if profile_combo is not None:
            index = profile_combo.findData(intake.profile_id)
            if index >= 0:
                profile_combo.setCurrentIndex(index)

        output_edit = _find_output_edit()
        destination = config.data_dir / "deliverables" / _slug(intake.project_name)
        if output_edit is not None:
            output_edit.setText(str(destination))

        window.refresh_all()
        mission_state.setText("MISSION INGESTED · AUTOPILOT STARTING")
        mission_detail.setText(
            f"{len(intake.analysis_sources)} quantitative candidate(s) · "
            f"{len(intake.context_files)} context/GIS file(s) · profile {intake.profile_id} · "
            f"output {destination}"
        )
        choose_folder.setEnabled(False)
        choose_files.setEnabled(False)
        # Allow the UI to paint the discovered mission state before starting the existing worker-backed
        # quantitative pipeline. This click invokes the same proven Autopilot authority as manual mode.
        QTimer.singleShot(120, existing_run.click)

    def _intake_failed(message: str) -> None:
        mission_state.setText("MISSION INTAKE FAILED")
        mission_detail.setText(message)
        choose_folder.setEnabled(True)
        choose_files.setEnabled(True)
        QMessageBox.critical(window, "Mission Intake Failed", message)

    def _start_intake(mode: str, payload) -> None:
        mission_state.setText("DISCOVERING FLIGHT DATA · NO ACTION REQUIRED")
        mission_detail.setText("Autopilot is classifying local files and preparing the mission context…")
        choose_folder.setEnabled(False)
        choose_files.setEnabled(False)
        worker = IntakeWorker(mode, payload)
        window.mission_intake_worker = worker
        worker.completed.connect(_apply_intake)
        worker.failed.connect(_intake_failed)
        worker.start()

    def choose_mission_folder() -> None:
        folder = QFileDialog.getExistingDirectory(
            window,
            "Select the flight / mission folder — Autopilot will process it automatically",
        )
        if folder:
            _start_intake("folder", folder)

    def choose_mission_files() -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            window,
            "Select thermal mission files — Autopilot will process them automatically",
            "",
            "Mission data (*.tif *.tiff *.jpg *.jpeg *.png *.kml *.kmz *.geojson *.json *.csv *.srt);;All files (*)",
        )
        if paths:
            _start_intake("files", paths)

    def toggle_advanced() -> None:
        if manual_plan is None:
            return
        visible = not manual_plan.isVisible()
        manual_plan.setVisible(visible)
        advanced.setText("Hide advanced controls" if visible else "Advanced controls")

    def open_completed_delivery() -> None:
        result = getattr(window, "autopilot_last_result", None)
        if result is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.deliverable_dir)))

    def watch_mission() -> None:
        worker = getattr(window, "autopilot_worker", None)
        if worker is not None and worker.isRunning():
            mission_state.setText("AUTOPILOT ACTIVE · PROCESSING THE MISSION FOR YOU")
            mission_detail.setText(
                "Radiometry, stitching, anomaly analysis, local AI review, annotations, and packaging "
                "are running in the background. You can continue navigating the application."
            )
            return
        result = getattr(window, "autopilot_last_result", None)
        if result is not None:
            mission_state.setText("DELIVERABLE READY · MISSION COMPLETE")
            mission_detail.setText(
                f"{result.run.summary.canonical_findings} canonical finding(s) · "
                f"client/engineering package: {result.deliverable_dir}"
            )
            open_delivery.setEnabled(True)
            choose_folder.setEnabled(True)
            choose_files.setEnabled(True)

    choose_folder.clicked.connect(choose_mission_folder)
    choose_files.clicked.connect(choose_mission_files)
    advanced.clicked.connect(toggle_advanced)
    open_delivery.clicked.connect(open_completed_delivery)

    mission_timer = QTimer(window)
    mission_timer.setInterval(350)
    mission_timer.timeout.connect(watch_mission)
    mission_timer.start()
    window.mission_status_timer = mission_timer

    window.nav.setCurrentRow(window.page_index["Autopilot"])
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
