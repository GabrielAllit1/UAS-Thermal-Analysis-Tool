from __future__ import annotations

from pathlib import Path


def create_workspace_window(session):
    """Create the AI-first autonomous thermal mission workspace."""

    from PyQt5.QtCore import QThread, QUrl, pyqtSignal
    from PyQt5.QtGui import QDesktopServices
    from PyQt5.QtWidgets import (
        QComboBox,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
    )

    from ..inspections.profiles import get_profile
    from ..orthomosaic import OrthomosaicService
    from ..platform.config import AppConfig
    from ..thermal.presentation import ThermalStyle, available_palettes
    from .autopilot import RuntimeSnapshot, autopilot_summary, scan_runtime, stage_for_event
    from .universal_pipeline import UniversalProcessingPlan, UniversalThermalProcessor
    from .workspace_ui_v3 import create_workspace_window as create_v3_workspace

    app, window = create_v3_workspace(session)
    config = AppConfig.from_env()
    window.setWindowTitle("UAS Thermal Intelligence — Autonomous Mission Control")
    window.resize(1640, 980)
    window.autopilot_last_result = None
    window.autopilot_snapshot = RuntimeSnapshot(
        ai_available=False,
        model_names=(),
        vision_models=(),
        orthomosaic_backends=tuple(
            (str(item["name"]), bool(item["available"]))
            for item in OrthomosaicService().status()
        ),
        ai_error="Local AI runtime not scanned",
    )

    window.setStyleSheet(
        window.styleSheet()
        + """
        QMainWindow,QWidget { background:#071019; color:#e8f3fb; }
        QFrame#intelligenceRibbon { background:#071722; border-bottom:1px solid #16435b; }
        QFrame#intelligenceCard { background:#0b1b27; border:1px solid #173b50; border-radius:10px; }
        QLabel#eyebrow { color:#56d7ff; font-size:9pt; font-weight:700; letter-spacing:1px; }
        QLabel#heroTitle { color:#f2fbff; font-size:24pt; font-weight:800; }
        QLabel#heroSub { color:#91aebf; font-size:11pt; }
        QLabel#statusGood { color:#5ef2b0; font-weight:700; }
        QLabel#statusWarn { color:#ffd56a; font-weight:700; }
        QPushButton#autopilotPrimary { background:#0aa6d8; color:#031018; border-radius:7px; padding:11px 18px; font-size:11pt; font-weight:800; }
        QPushButton#autopilotPrimary:hover { background:#26c3ef; }
        QPushButton#autopilotSecondary { background:#102a39; border:1px solid #24506a; border-radius:7px; padding:9px 14px; }
        QTableWidget#pipelineTable { background:#08131c; border:1px solid #17394c; gridline-color:#17394c; }
        QTableWidget#pipelineTable::item { padding:8px; }
        """
    )

    # Persistent AI/autonomy ribbon.
    root_layout = window.centralWidget().layout()
    ribbon = QFrame()
    ribbon.setObjectName("intelligenceRibbon")
    ribbon_layout = QHBoxLayout(ribbon)
    ribbon_layout.setContentsMargins(14, 7, 14, 7)
    ribbon_layout.addWidget(QLabel("THERMAL INTELLIGENCE"))
    ribbon_layout.addSpacing(18)
    ribbon_labels = {}
    for key, label in (
        ("radiometry", "RADIOMETRY"),
        ("stitch", "AUTONOMOUS STITCH"),
        ("ai", "LOCAL AI"),
        ("deliverable", "DELIVERABLE"),
    ):
        value = QLabel(f"{label} · READY")
        value.setObjectName("statusGood")
        ribbon_layout.addWidget(value)
        ribbon_labels[key] = value
    ribbon_layout.addStretch(1)
    privacy = QLabel("LOCAL-FIRST · SOURCE DATA STAYS ON THIS WORKSTATION")
    privacy.setStyleSheet("color:#64889d;font-size:8.5pt;")
    ribbon_layout.addWidget(privacy)
    root_layout.insertWidget(1, ribbon)
    window.intelligence_ribbon_labels = ribbon_labels

    # AI-first Autopilot page.
    layout = window._page(
        "Autopilot",
        "Thermal Intelligence Autopilot",
        (
            "Operator in, deliverable out. The stack plans processing, selects available local engines, "
            "stitches when appropriate, enforces radiometric gates, analyzes, applies local AI context, "
            "annotates findings, and packages client/engineering outputs."
        ),
    )
    window.nav.addItem("Autopilot")

    hero = QFrame()
    hero.setObjectName("intelligenceCard")
    hero_layout = QVBoxLayout(hero)
    eyebrow = QLabel("AUTONOMOUS POST-PROCESSING · LOCAL AI · QUANTITATIVE THERMAL")
    eyebrow.setObjectName("eyebrow")
    title = QLabel("From flight data to decision-ready thermal intelligence")
    title.setObjectName("heroTitle")
    subtitle = QLabel(
        "You execute the mission. Autopilot handles the post-flight workload while deterministic "
        "radiometry remains the quantitative authority."
    )
    subtitle.setObjectName("heroSub")
    subtitle.setWordWrap(True)
    hero_layout.addWidget(eyebrow)
    hero_layout.addWidget(title)
    hero_layout.addWidget(subtitle)
    layout.addWidget(hero)

    cards = QHBoxLayout()
    readiness_labels = {}

    def add_card(key, heading, initial):
        card = QFrame()
        card.setObjectName("intelligenceCard")
        card_layout = QVBoxLayout(card)
        label = QLabel(heading.upper())
        label.setObjectName("eyebrow")
        value = QLabel(initial)
        value.setStyleSheet("font-size:13pt;font-weight:800;color:#f3fbff;")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        cards.addWidget(card, 1)
        readiness_labels[key] = value

    add_card("sources", "Mission data", "0 SOURCES")
    add_card("radiometry", "Quantitative gate", "GATED")
    add_card("stitch", "Stitch engine", "SOURCE-DEPENDENT")
    add_card("ai", "AI copilot", "NOT SCANNED")
    add_card("deliverable", "Output", "AUTOMATED")
    layout.addLayout(cards)

    mission = QGroupBox("Autonomous mission plan")
    mission_layout = QHBoxLayout(mission)
    stitch_policy = QComboBox()
    stitch_policy.addItems(["auto", "on", "off"])
    ai_policy = QComboBox()
    ai_policy.addItem("Auto-select best local model", "auto")
    ai_policy.addItem("Deterministic only", "off")
    palette = QComboBox()
    palette.addItems(list(available_palettes()))
    iron_index = palette.findText("ironbow")
    if iron_index >= 0:
        palette.setCurrentIndex(iron_index)
    output = QLineEdit(str(config.data_dir / "deliverables"))
    browse = QPushButton("Output…")
    browse.setObjectName("autopilotSecondary")
    scan = QPushButton("Scan Local Stack")
    scan.setObjectName("autopilotSecondary")
    run = QPushButton("RUN AUTOPILOT")
    run.setObjectName("autopilotPrimary")
    mission_layout.addWidget(QLabel("Stitch"))
    mission_layout.addWidget(stitch_policy)
    mission_layout.addWidget(QLabel("AI"))
    mission_layout.addWidget(ai_policy, 1)
    mission_layout.addWidget(QLabel("Palette"))
    mission_layout.addWidget(palette)
    mission_layout.addWidget(output, 1)
    mission_layout.addWidget(browse)
    mission_layout.addWidget(scan)
    mission_layout.addWidget(run)
    layout.addWidget(mission)

    pipeline = QTableWidget(8, 3)
    pipeline.setObjectName("pipelineTable")
    pipeline.setHorizontalHeaderLabels(["Stage", "Authority / Engine", "Status"])
    pipeline.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    pipeline.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    pipeline.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
    pipeline.verticalHeader().setVisible(False)
    pipeline.setEditTriggers(QTableWidget.NoEditTriggers)
    stages = [
        ("INGEST", "Source classification + project context"),
        ("RADIOMETRY", "Validated ThermalFrame quantitative gate"),
        ("STITCH", "Native GeoTIFF or configured photogrammetry backend"),
        ("ANALYZE", "Contextual deterministic thermal analysis"),
        ("AI REVIEW", "Local Ollama vision/text interpretation when available"),
        ("ANNOTATE", "Canonical finding overlays + evidence plates"),
        ("PACKAGE", "PDF + GeoTIFF + CSV/JSON + GIS + portable viewer"),
        ("COMPLETE", "Manifest + provenance + client/engineering handoff"),
    ]
    stage_rows = {}
    for row, (stage, authority) in enumerate(stages):
        pipeline.setItem(row, 0, QTableWidgetItem(stage))
        pipeline.setItem(row, 1, QTableWidgetItem(authority))
        pipeline.setItem(row, 2, QTableWidgetItem("STANDBY"))
        stage_rows[stage] = row
    layout.addWidget(pipeline, 1)

    lower = QHBoxLayout()
    log = QTextEdit()
    log.setReadOnly(True)
    log.setPlaceholderText("Autopilot telemetry will appear here…")
    lower.addWidget(log, 2)
    result_panel = QFrame()
    result_panel.setObjectName("intelligenceCard")
    result_layout = QVBoxLayout(result_panel)
    result_title = QLabel("MISSION OUTPUT")
    result_title.setObjectName("eyebrow")
    result_summary = QLabel("No autonomous run completed yet.")
    result_summary.setWordWrap(True)
    open_folder = QPushButton("Open Deliverable Folder")
    open_folder.setObjectName("autopilotSecondary")
    open_folder.setEnabled(False)
    open_viewer = QPushButton("Open Client Viewer")
    open_viewer.setObjectName("autopilotSecondary")
    open_viewer.setEnabled(False)
    result_layout.addWidget(result_title)
    result_layout.addWidget(result_summary)
    result_layout.addStretch(1)
    result_layout.addWidget(open_folder)
    result_layout.addWidget(open_viewer)
    lower.addWidget(result_panel, 1)
    layout.addLayout(lower)

    def set_stage(stage, state):
        row = stage_rows.get(stage)
        if row is None:
            return
        item = pipeline.item(row, 2)
        item.setText(state)

    def reset_stages():
        for stage, _ in stages:
            set_stage(stage, "STANDBY")

    def update_readiness():
        summary = autopilot_summary(window.autopilot_snapshot, len(session.sources))
        readiness_labels["sources"].setText(f"{summary['sources']} SOURCES")
        readiness_labels["radiometry"].setText(summary["radiometry"])
        readiness_labels["stitch"].setText(summary["stitch"])
        readiness_labels["ai"].setText(summary["ai"])
        readiness_labels["deliverable"].setText(summary["deliverable"])
        ribbon_labels["radiometry"].setText("RADIOMETRY · GATED")
        ribbon_labels["stitch"].setText(f"AUTONOMOUS STITCH · {summary['stitch']}")
        ribbon_labels["ai"].setText(f"LOCAL AI · {summary['ai']}")
        ribbon_labels["deliverable"].setText("DELIVERABLE · AUTOMATED")

    def scan_stack():
        scan.setEnabled(False)
        log.append("Scanning local AI models and quantitative stitching runtimes…")
        app.processEvents()
        snapshot = scan_runtime(config=config)
        window.autopilot_snapshot = snapshot
        current = ai_policy.currentData()
        ai_policy.clear()
        ai_policy.addItem("Auto-select best local model", "auto")
        ai_policy.addItem("Deterministic only", "off")
        for model_name in snapshot.model_names:
            suffix = " · VISION" if model_name in snapshot.vision_models else ""
            ai_policy.addItem(f"{model_name}{suffix}", model_name)
        if current:
            index = ai_policy.findData(current)
            if index >= 0:
                ai_policy.setCurrentIndex(index)
        update_readiness()
        if snapshot.ai_available:
            log.append(
                f"Local AI ready: {len(snapshot.model_names)} model(s), "
                f"{len(snapshot.vision_models)} vision-capable."
            )
        else:
            log.append(
                "Local AI unavailable; Autopilot will continue through deterministic authorities. "
                + snapshot.ai_error
            )
        for backend, available in snapshot.orthomosaic_backends:
            log.append(f"Stitch backend {backend}: {'READY' if available else 'UNAVAILABLE'}")
        scan.setEnabled(True)

    def browse_output():
        selected = QFileDialog.getExistingDirectory(window, "Autopilot deliverable destination")
        if selected:
            output.setText(selected)

    class AutopilotWorker(QThread):
        eventRaised = pyqtSignal(str)
        completed = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, processor, project, sources, output_dir, calibration, profile, plan):
            super().__init__()
            self.processor = processor
            self.project = project
            self.sources = sources
            self.output_dir = output_dir
            self.calibration = calibration
            self.profile = profile
            self.plan = plan

        def run(self):
            try:
                result = self.processor.process(
                    self.project,
                    self.sources,
                    self.output_dir,
                    calibration=self.calibration,
                    profile=self.profile,
                    plan=self.plan,
                    on_event=self.eventRaised.emit,
                )
                self.completed.emit(result)
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def event_raised(message):
        stage = stage_for_event(message)
        for stage_name, _ in stages:
            row = stage_rows[stage_name]
            current = pipeline.item(row, 2).text()
            if stage_name == stage:
                set_stage(stage_name, "RUNNING")
            elif current == "RUNNING":
                set_stage(stage_name, "DONE")
        log.append(message)
        window.header_status.setText(f"Autopilot · {stage}")

    def run_autopilot():
        try:
            window._sync_project_form()
            if not session.sources:
                raise ValueError("Add thermal mission data before running Autopilot")
            profile = get_profile(window.profile_combo.currentData())
            calibration = window._calibration()
            destination = Path(output.text()).expanduser()
            style = ThermalStyle(palette=palette.currentText())
            ai_mode = ai_policy.currentData() or window.autopilot_snapshot.preferred_ai_mode
            plan = UniversalProcessingPlan(
                stitch_mode=stitch_policy.currentText(),
                orthomosaic_backend="auto",
                ai_mode=ai_mode,
                thermal_style=style,
            )
        except Exception as exc:
            QMessageBox.warning(window, "Autopilot", str(exc))
            return

        reset_stages()
        set_stage("INGEST", "RUNNING")
        log.clear()
        log.append("Autopilot engaged. Source data remains local unless an explicitly configured local backend says otherwise.")
        run.setEnabled(False)
        scan.setEnabled(False)
        open_folder.setEnabled(False)
        open_viewer.setEnabled(False)
        window.header_status.setText("Autopilot engaged")
        worker = AutopilotWorker(
            UniversalThermalProcessor(),
            session.project,
            list(session.sources),
            destination,
            calibration,
            profile,
            plan,
        )
        window.autopilot_worker = worker
        worker.eventRaised.connect(event_raised)

        def complete(result):
            window.autopilot_last_result = result
            session.last_run = result.run
            session.artifacts = list(result.run.artifacts)
            for stage_name, _ in stages:
                set_stage(stage_name, "DONE")
            window.header_status.setText("Autopilot complete")
            run.setEnabled(True)
            scan.setEnabled(True)
            open_folder.setEnabled(True)
            viewer = result.deliverable_dir / "viewer" / "index.html"
            open_viewer.setEnabled(viewer.is_file())
            ai_text = (
                f"Local AI: {result.ai_provider}/{result.ai_model} · "
                f"{result.ai_enriched_findings} finding(s) enriched"
                if result.ai_model
                else "Local AI: deterministic fallback used"
            )
            ortho_text = (
                f"Stitch: {result.orthomosaic.backend} quantitative orthomosaic"
                if result.orthomosaic is not None
                else "Stitch: not required / source-level analysis"
            )
            result_summary.setText(
                f"{result.run.summary.canonical_findings} canonical finding(s)\n"
                f"{ortho_text}\n{ai_text}\n"
                f"Deliverable: {result.deliverable_dir}"
            )
            for warning in result.warnings:
                log.append(f"Warning: {warning}")
            log.append(f"Mission complete: {result.deliverable_dir}")
            window.refresh_all()
            update_readiness()

        def failed(message):
            for stage_name, _ in stages:
                row = stage_rows[stage_name]
                if pipeline.item(row, 2).text() == "RUNNING":
                    set_stage(stage_name, "FAILED")
            window.header_status.setText("Autopilot failed")
            run.setEnabled(True)
            scan.setEnabled(True)
            log.append(message)
            QMessageBox.critical(window, "Autopilot", message)

        worker.completed.connect(complete)
        worker.failed.connect(failed)
        worker.start()

    def open_last_folder():
        result = window.autopilot_last_result
        if result is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.deliverable_dir)))

    def open_last_viewer():
        result = window.autopilot_last_result
        if result is not None:
            viewer = result.deliverable_dir / "viewer" / "index.html"
            if viewer.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(viewer)))

    browse.clicked.connect(browse_output)
    scan.clicked.connect(scan_stack)
    run.clicked.connect(run_autopilot)
    open_folder.clicked.connect(open_last_folder)
    open_viewer.clicked.connect(open_last_viewer)

    update_readiness()
    window.nav.setCurrentRow(window.page_index["Autopilot"])
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
