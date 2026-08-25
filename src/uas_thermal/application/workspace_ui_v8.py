from __future__ import annotations


def create_workspace_window(session):
    """Create the responsive operator-first frontier workspace.

    This layer leaves the proven v0.10 Autopilot/runtime/processing authorities intact and replaces
    only the presentation surface. Legacy controls remain alive but hidden so proxy actions use the
    same one-click mission and demo paths.
    """

    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtGui import QFont, QTextCursor
    from PyQt5.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QTableWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    from .workspace_ui_v7 import create_workspace_window as create_v7_workspace

    app, window = create_v7_workspace(session)
    app.setFont(QFont("Segoe UI Variable", 10))
    window.setWindowTitle("UAS Thermal Intelligence — Autonomous Thermal Workspace")
    window.setMinimumSize(880, 540)
    window.resize(1440, 900)

    # Remove stacked ribbons that consume valuable vertical space on laptop displays. Runtime
    # discovery continues in the background; the state is mirrored into the mission canvas below.
    for object_name in ("intelligenceRibbon", "commandBar"):
        frame = window.findChild(QFrame, object_name)
        if frame is not None:
            frame.hide()

    # A permanent three-pane layout is too expensive at common 1024/1366 laptop widths. Keep the
    # inspector available on demand rather than stealing hundreds of pixels from every workflow.
    inspector = getattr(window, "inspector", None)
    if inspector is not None:
        inspector.hide()

    window.nav.setMinimumWidth(142)
    window.nav.setMaximumWidth(168)
    nav_titles = {
        "Autopilot": "Autopilot",
        "Projects": "Projects",
        "Overview": "Mission",
        "Data": "Data",
        "Explore": "Thermal Lab",
        "Analyze": "Analysis",
        "Processing": "Processing",
        "Findings": "Findings",
        "Compare": "Compare",
        "Reports": "Reports",
        "Exports": "Exports",
        "Analytics": "Analytics",
        "Profiles": "Profiles",
        "Settings": "System",
        "Measurements": "Measure",
        "Process": "Pipeline",
    }
    for name, index in window.page_index.items():
        item = window.nav.item(index)
        if item is not None:
            item.setText(nav_titles.get(name, name))

    header = window.findChild(QFrame, "header")
    if header is not None:
        for label in header.findChildren(QLabel):
            if label.text() == "UAS Thermal Analysis":
                label.setText("UAS Thermal Intelligence")
                label.setObjectName("brandTitle")
                break
    if header is not None and header.layout() is not None and inspector is not None:
        inspector_toggle = QPushButton("Inspector")
        inspector_toggle.setObjectName("topGhostButton")

        def toggle_inspector() -> None:
            inspector.setVisible(not inspector.isVisible())
            inspector_toggle.setText("Hide inspector" if inspector.isVisible() else "Inspector")

        inspector_toggle.clicked.connect(toggle_inspector)
        header.layout().addWidget(inspector_toggle)
        window.inspector_toggle = inspector_toggle

    autopilot_page = window.pages.widget(window.page_index["Autopilot"])
    autopilot_layout = autopilot_page.layout()
    autopilot_layout.setContentsMargins(0, 0, 0, 0)
    autopilot_layout.setSpacing(0)

    # Capture the proven hidden controls before replacing their presentation.
    legacy_folder = window.findChild(QPushButton, "oneClickPrimary")
    legacy_demo = window.findChild(QPushButton, "demoMissionButton")
    legacy_state = window.findChild(QLabel, "missionState")
    legacy_pipeline = window.findChild(QTableWidget, "pipelineTable")
    legacy_log = next(
        (
            editor
            for editor in window.findChildren(QTextEdit)
            if "Autopilot telemetry" in editor.placeholderText()
        ),
        None,
    )
    legacy_open_folder = next(
        (
            button
            for button in window.findChildren(QPushButton)
            if button.text() in {"OPEN COMPLETED DELIVERABLE", "Open Deliverable Folder"}
        ),
        None,
    )
    legacy_open_viewer = next(
        (
            button
            for button in window.findChildren(QPushButton)
            if button.text() == "Open Client Viewer"
        ),
        None,
    )
    legacy_advanced = next(
        (
            button
            for button in window.findChildren(QPushButton)
            if button.text() in {"Advanced controls", "Hide advanced controls"}
        ),
        None,
    )

    legacy_detail = None
    if legacy_state is not None and legacy_state.parentWidget() is not None:
        siblings = legacy_state.parentWidget().findChildren(QLabel)
        try:
            state_index = siblings.index(legacy_state)
        except ValueError:
            state_index = -1
        if state_index >= 0 and state_index + 1 < len(siblings):
            legacy_detail = siblings[state_index + 1]

    # All old Autopilot widgets stay alive for signals/state, but they no longer compete visually
    # with the operator-first canvas.
    for child in autopilot_page.findChildren(QWidget):
        child.hide()

    # Give the remaining specialist pages more breathing room without changing their workflow.
    for name, index in window.page_index.items():
        if name == "Autopilot":
            continue
        page = window.pages.widget(index)
        layout = page.layout()
        if layout is not None:
            layout.setContentsMargins(20, 18, 20, 20)
            layout.setSpacing(12)
        for label in page.findChildren(QLabel):
            if len(label.text()) > 72:
                label.setWordWrap(True)

    scroll = QScrollArea()
    scroll.setObjectName("autopilotScroll")
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    canvas = QWidget()
    canvas.setObjectName("frontierCanvas")
    canvas.setMinimumWidth(0)
    body = QVBoxLayout(canvas)
    body.setContentsMargins(22, 20, 22, 28)
    body.setSpacing(16)

    hero = QFrame()
    hero.setObjectName("missionLaunchCard")
    hero_layout = QVBoxLayout(hero)
    hero_layout.setContentsMargins(26, 24, 26, 24)
    hero_layout.setSpacing(10)

    hero_top = QHBoxLayout()
    hero_eyebrow = QLabel("AUTONOMOUS THERMAL INTELLIGENCE")
    hero_eyebrow.setObjectName("frontierEyebrow")
    hero_top.addWidget(hero_eyebrow)
    hero_top.addStretch(1)
    local_badge = QLabel("LOCAL-FIRST")
    local_badge.setObjectName("frontierPill")
    hero_top.addWidget(local_badge)
    hero_layout.addLayout(hero_top)

    hero_title = QLabel("One mission in. Engineer-ready thermal intelligence out.")
    hero_title.setObjectName("frontierHeroTitle")
    hero_title.setWordWrap(True)
    hero_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    hero_layout.addWidget(hero_title)

    hero_copy = QLabel(
        "Select the flight folder and Autopilot handles discovery, radiometric validation, "
        "task-aware local AI routing, quantitative stitching when supported, anomaly detection, "
        "Delta T characterization, annotations, and the client + engineering deliverable."
    )
    hero_copy.setObjectName("frontierHeroCopy")
    hero_copy.setWordWrap(True)
    hero_layout.addWidget(hero_copy)

    hero_actions = QHBoxLayout()
    hero_actions.setSpacing(10)
    process_button = QPushButton("PROCESS FLIGHT FOLDER")
    process_button.setObjectName("frontierPrimary")
    demo_button = QPushButton("RUN GUIDED DEMO")
    demo_button.setObjectName("frontierDemo")
    review_button = QPushButton("Advanced review")
    review_button.setObjectName("frontierGhost")
    hero_actions.addWidget(process_button, 2)
    hero_actions.addWidget(demo_button)
    hero_actions.addWidget(review_button)
    hero_layout.addLayout(hero_actions)

    trust = QLabel(
        "No cloud upload required  •  deterministic radiometry remains authoritative  •  "
        "AI interpretation is supplemental and local when available"
    )
    trust.setObjectName("frontierTrust")
    trust.setWordWrap(True)
    hero_layout.addWidget(trust)
    body.addWidget(hero)

    metrics = QGridLayout()
    metrics.setHorizontalSpacing(12)
    metrics.setVerticalSpacing(12)
    metric_values: dict[str, QLabel] = {}

    def metric_card(key: str, title: str, initial: str, note: str, row: int, column: int) -> None:
        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(3)
        heading = QLabel(title)
        heading.setObjectName("metricLabel")
        value = QLabel(initial)
        value.setObjectName("metricValue")
        value.setWordWrap(True)
        sub = QLabel(note)
        sub.setObjectName("metricNote")
        sub.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(value)
        layout.addWidget(sub)
        metrics.addWidget(card, row, column)
        metric_values[key] = value

    metric_card("mission", "Mission", "READY", "Select flight data or run the demo", 0, 0)
    metric_card("radiometry", "Radiometry", "GATED", "Quantitative source authority", 0, 1)
    metric_card("ai", "Local AI", "DISCOVERING", "Task-aware model routing", 1, 0)
    metric_card("deliverable", "Deliverable", "AUTOMATED", "Engineering + client package", 1, 1)
    body.addLayout(metrics)

    operational = QGridLayout()
    operational.setHorizontalSpacing(14)
    operational.setVerticalSpacing(14)

    mission_card = QFrame()
    mission_card.setObjectName("workspaceCard")
    mission_layout = QVBoxLayout(mission_card)
    mission_layout.setContentsMargins(18, 16, 18, 16)
    mission_layout.setSpacing(9)
    mission_head = QLabel("LIVE MISSION")
    mission_head.setObjectName("frontierEyebrow")
    mission_title = QLabel("Ready for flight data")
    mission_title.setObjectName("workspaceTitle")
    mission_title.setWordWrap(True)
    mission_detail = QLabel(
        "Autopilot is idle. Choose a mission folder or run the deterministic learning mission."
    )
    mission_detail.setObjectName("workspaceCopy")
    mission_detail.setWordWrap(True)
    progress = QProgressBar()
    progress.setObjectName("missionProgress")
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setTextVisible(False)
    mission_layout.addWidget(mission_head)
    mission_layout.addWidget(mission_title)
    mission_layout.addWidget(mission_detail)
    mission_layout.addWidget(progress)
    operational.addWidget(mission_card, 0, 0)

    output_card = QFrame()
    output_card.setObjectName("workspaceCard")
    output_layout = QVBoxLayout(output_card)
    output_layout.setContentsMargins(18, 16, 18, 16)
    output_layout.setSpacing(9)
    output_head = QLabel("MISSION OUTPUT")
    output_head.setObjectName("frontierEyebrow")
    output_title = QLabel("No deliverable yet")
    output_title.setObjectName("workspaceTitle")
    output_title.setWordWrap(True)
    output_detail = QLabel(
        "Completed missions surface findings, severity distribution, report package, GIS outputs, "
        "portable viewer, and provenance here."
    )
    output_detail.setObjectName("workspaceCopy")
    output_detail.setWordWrap(True)
    output_actions = QHBoxLayout()
    open_folder = QPushButton("OPEN PACKAGE")
    open_folder.setObjectName("frontierSecondary")
    open_viewer = QPushButton("OPEN VIEWER")
    open_viewer.setObjectName("frontierGhost")
    open_folder.setEnabled(False)
    open_viewer.setEnabled(False)
    output_actions.addWidget(open_folder)
    output_actions.addWidget(open_viewer)
    output_actions.addStretch(1)
    output_layout.addWidget(output_head)
    output_layout.addWidget(output_title)
    output_layout.addWidget(output_detail)
    output_layout.addLayout(output_actions)
    operational.addWidget(output_card, 0, 1)
    body.addLayout(operational)

    route_card = QFrame()
    route_card.setObjectName("workspaceCard")
    route_layout = QVBoxLayout(route_card)
    route_layout.setContentsMargins(18, 16, 18, 16)
    route_layout.setSpacing(9)
    route_head = QHBoxLayout()
    route_title = QLabel("TASK-AWARE AI ROUTING")
    route_title.setObjectName("frontierEyebrow")
    route_status = QLabel("BACKGROUND DISCOVERY")
    route_status.setObjectName("frontierPill")
    route_head.addWidget(route_title)
    route_head.addStretch(1)
    route_head.addWidget(route_status)
    route_layout.addLayout(route_head)

    routes = QGridLayout()
    routes.setHorizontalSpacing(12)
    route_values: dict[str, QLabel] = {}
    for column, (key, heading) in enumerate(
        (
            ("vision_review", "Vision review"),
            ("engineering_narrative", "Engineering narrative"),
            ("fast_triage", "Fast triage"),
        )
    ):
        cell = QFrame()
        cell.setObjectName("routeCell")
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(12, 10, 12, 10)
        cell_heading = QLabel(heading)
        cell_heading.setObjectName("metricLabel")
        cell_value = QLabel("Detecting local stack…")
        cell_value.setObjectName("routeValueFrontier")
        cell_value.setWordWrap(True)
        cell_layout.addWidget(cell_heading)
        cell_layout.addWidget(cell_value)
        routes.addWidget(cell, 0, column)
        route_values[key] = cell_value
    route_layout.addLayout(routes)
    body.addWidget(route_card)

    capabilities_card = QFrame()
    capabilities_card.setObjectName("workspaceCard")
    capabilities_layout = QVBoxLayout(capabilities_card)
    capabilities_layout.setContentsMargins(18, 16, 18, 18)
    capabilities_layout.setSpacing(11)
    cap_title = QLabel("AUTOPILOT CAPABILITIES")
    cap_title.setObjectName("frontierEyebrow")
    cap_intro = QLabel(
        "The normal operator workflow is mission selection → automated post-processing → "
        "decision-ready deliverable. Manual tools remain available for audit and specialist review."
    )
    cap_intro.setObjectName("workspaceCopy")
    cap_intro.setWordWrap(True)
    capabilities_layout.addWidget(cap_title)
    capabilities_layout.addWidget(cap_intro)

    capability_grid = QGridLayout()
    capability_grid.setHorizontalSpacing(12)
    capability_grid.setVerticalSpacing(12)
    capability_specs = (
        ("01", "Ingest + validate", "Classify thermal, visible, GIS and context while gating radiometry."),
        ("02", "Stitch + normalize", "Build a quantitative thermal mosaic when the source contract supports it."),
        ("03", "Detect + prioritize", "Find coherent anomalies, calculate Delta T, severity and confidence."),
        ("04", "AI evidence review", "Route local vision/text models by task without changing thermal authority."),
        ("05", "Annotate + explain", "Create finding plates, evidence, measurements and engineering narrative."),
        ("06", "Package + share", "Produce PDF, GeoTIFF, CSV/JSON, GIS, viewer, provenance and hashes."),
    )
    for index, (number, title, description) in enumerate(capability_specs):
        card = QFrame()
        card.setObjectName("capabilityCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(13, 12, 13, 12)
        layout.setSpacing(10)
        number_label = QLabel(number)
        number_label.setObjectName("capabilityNumber")
        copy = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("capabilityTitle")
        description_label = QLabel(description)
        description_label.setObjectName("metricNote")
        description_label.setWordWrap(True)
        copy.addWidget(title_label)
        copy.addWidget(description_label)
        layout.addWidget(number_label)
        layout.addLayout(copy, 1)
        capability_grid.addWidget(card, index // 2, index % 2)
    capabilities_layout.addLayout(capability_grid)
    body.addWidget(capabilities_card)

    details_button = QPushButton("Show processing details")
    details_button.setObjectName("detailsToggle")
    details_panel = QFrame()
    details_panel.setObjectName("workspaceCard")
    details_panel.hide()
    details_layout = QVBoxLayout(details_panel)
    details_layout.setContentsMargins(18, 16, 18, 16)
    details_layout.setSpacing(10)
    detail_head = QLabel("PROCESSING TELEMETRY")
    detail_head.setObjectName("frontierEyebrow")
    stage_summary = QLabel("All stages standby.")
    stage_summary.setObjectName("workspaceCopy")
    stage_summary.setWordWrap(True)
    telemetry = QTextEdit()
    telemetry.setObjectName("frontierTelemetry")
    telemetry.setReadOnly(True)
    telemetry.setMinimumHeight(170)
    details_layout.addWidget(detail_head)
    details_layout.addWidget(stage_summary)
    details_layout.addWidget(telemetry)
    body.addWidget(details_button)
    body.addWidget(details_panel)
    body.addStretch(1)

    scroll.setWidget(canvas)
    autopilot_layout.addWidget(scroll, 1)

    def toggle_details() -> None:
        visible = not details_panel.isVisible()
        details_panel.setVisible(visible)
        details_button.setText("Hide processing details" if visible else "Show processing details")

    details_button.clicked.connect(toggle_details)

    def proxy_click(target: QPushButton | None) -> None:
        if target is not None and target.isEnabled():
            target.click()

    process_button.clicked.connect(lambda: proxy_click(legacy_folder))
    demo_button.clicked.connect(lambda: proxy_click(legacy_demo))

    def open_advanced() -> None:
        if legacy_advanced is not None:
            legacy_advanced.click()
        target = window.page_index.get("Process")
        if target is not None:
            window.nav.setCurrentRow(target)

    review_button.clicked.connect(open_advanced)
    open_folder.clicked.connect(lambda: proxy_click(legacy_open_folder))
    open_viewer.clicked.connect(lambda: proxy_click(legacy_open_viewer))

    def severity_summary(result) -> tuple[int, int, int]:
        critical = moderate = minor = 0
        for finding in result.run.canonical_findings:
            value = getattr(finding.severity, "value", str(finding.severity)).lower()
            if value == "critical":
                critical += 1
            elif value == "moderate":
                moderate += 1
            else:
                minor += 1
        return critical, moderate, minor

    def update_frontier_state() -> None:
        snapshot = getattr(window, "autopilot_snapshot", None)
        source_count = len(session.sources)
        metric_values["mission"].setText(f"{source_count} SOURCE{'S' if source_count != 1 else ''}" if source_count else "READY")

        if snapshot is not None:
            ai_ready = bool(getattr(snapshot, "ai_available", False))
            model_names = tuple(getattr(snapshot, "model_names", ()))
            metric_values["ai"].setText(f"{len(model_names)} MODELS" if ai_ready else "SAFE FALLBACK")
            route_status.setText("LOCAL AI READY" if ai_ready else "DETERMINISTIC FALLBACK")
            route_map = getattr(snapshot, "routes", None)
            if route_map is not None:
                route_values["vision_review"].setText(route_map.vision_review or "Deterministic")
                route_values["engineering_narrative"].setText(
                    route_map.engineering_narrative or "Deterministic"
                )
                route_values["fast_triage"].setText(route_map.fast_triage or "Deterministic")

        if legacy_state is not None and legacy_state.text():
            mission_title.setText(legacy_state.text().title())
        if legacy_detail is not None and legacy_detail.text():
            mission_detail.setText(legacy_detail.text())

        demo_worker = getattr(window, "demo_mission_worker", None)
        autopilot_worker = getattr(window, "autopilot_worker", None)
        running = bool(
            (demo_worker is not None and demo_worker.isRunning())
            or (autopilot_worker is not None and autopilot_worker.isRunning())
        )
        result = getattr(window, "autopilot_last_result", None)

        if legacy_folder is not None:
            process_button.setEnabled(legacy_folder.isEnabled())
        if legacy_demo is not None:
            demo_button.setEnabled(legacy_demo.isEnabled())

        if running:
            progress.setRange(0, 0)
            metric_values["deliverable"].setText("PROCESSING")
            output_title.setText("Autopilot is building the package")
            output_detail.setText(
                "Radiometric analysis, stitching, anomaly intelligence, local AI review, "
                "annotations and packaging are running without blocking navigation."
            )
        elif result is not None:
            progress.setRange(0, 100)
            progress.setValue(100)
            metric_values["deliverable"].setText("READY")
            critical, moderate, minor = severity_summary(result)
            finding_count = len(result.run.canonical_findings)
            output_title.setText(f"{finding_count} canonical finding{'s' if finding_count != 1 else ''}")
            output_detail.setText(
                f"Critical {critical}  •  Moderate {moderate}  •  Minor {minor}\n"
                f"{result.deliverable_dir}"
            )
            open_folder.setEnabled(True)
            viewer_path = result.deliverable_dir / "viewer" / "index.html"
            open_viewer.setEnabled(viewer_path.is_file())
        else:
            progress.setRange(0, 100)
            progress.setValue(0)
            open_folder.setEnabled(False)
            open_viewer.setEnabled(False)

        # Mirror the hidden authoritative stage table into a compact status sentence.
        if legacy_pipeline is not None:
            stage_states = []
            for row in range(legacy_pipeline.rowCount()):
                stage_item = legacy_pipeline.item(row, 0)
                status_item = legacy_pipeline.item(row, 2)
                if stage_item is None or status_item is None:
                    continue
                stage_states.append(f"{stage_item.text()} {status_item.text()}")
            if stage_states:
                stage_summary.setText("  •  ".join(stage_states))

        if legacy_log is not None:
            text = legacy_log.toPlainText().strip()
            if text and text != telemetry.toPlainText().strip():
                lines = text.splitlines()[-80:]
                telemetry.setPlainText("\n".join(lines))
                telemetry.moveCursor(QTextCursor.End)

    state_timer = QTimer(window)
    state_timer.setInterval(250)
    state_timer.timeout.connect(update_frontier_state)
    state_timer.start()
    window.frontier_state_timer = state_timer

    window.setStyleSheet(
        window.styleSheet()
        + """
        QMainWindow, QWidget {
            background:#05080d;
            color:#e8eef4;
            font-family:"Segoe UI Variable","Segoe UI",sans-serif;
            font-size:10pt;
        }
        QLabel#brandTitle {
            color:#f5fbff;
            font-size:14pt;
            font-weight:800;
        }
        QFrame#header {
            background:#070c12;
            border:0;
            border-bottom:1px solid #15212d;
            min-height:48px;
        }
        QListWidget#missionNav {
            background:#070b11;
            border:0;
            border-right:1px solid #151f2a;
            padding:10px 7px;
        }
        QListWidget#missionNav::item {
            color:#7f93a4;
            border:0;
            border-radius:7px;
            padding:9px 10px;
            margin:1px 0;
            font-size:9.5pt;
            font-weight:600;
        }
        QListWidget#missionNav::item:hover { color:#e4f1f8; background:#0d1620; }
        QListWidget#missionNav::item:selected {
            color:#f7fcff;
            background:#102432;
            border-left:3px solid #5ce1ff;
        }
        QWidget#frontierCanvas { background:#05080d; }
        QScrollArea#autopilotScroll { background:#05080d; border:0; }
        QFrame#missionLaunchCard {
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0b1722,stop:0.55 #0b111a,stop:1 #11101b);
            border:1px solid #214052;
            border-radius:18px;
        }
        QFrame#workspaceCard, QFrame#metricCard {
            background:#0a1018;
            border:1px solid #182735;
            border-radius:14px;
        }
        QFrame#workspaceCard:hover, QFrame#metricCard:hover { border-color:#24465a; }
        QFrame#routeCell, QFrame#capabilityCard {
            background:#0c141d;
            border:1px solid #172936;
            border-radius:10px;
        }
        QLabel#frontierEyebrow, QLabel#metricLabel {
            color:#6ddfff;
            font-size:8.5pt;
            font-weight:800;
        }
        QLabel#frontierPill {
            color:#70efc1;
            background:#0d211d;
            border:1px solid #1d4d40;
            border-radius:10px;
            padding:4px 8px;
            font-size:8.5pt;
            font-weight:800;
        }
        QLabel#frontierHeroTitle {
            color:#f7fbff;
            font-size:25pt;
            font-weight:800;
        }
        QLabel#frontierHeroCopy {
            color:#a7bac7;
            font-size:11pt;
        }
        QLabel#frontierTrust {
            color:#708796;
            font-size:9pt;
        }
        QLabel#metricValue {
            color:#f5fbff;
            font-size:15pt;
            font-weight:800;
        }
        QLabel#metricNote, QLabel#workspaceCopy {
            color:#8298a8;
            font-size:9.5pt;
        }
        QLabel#workspaceTitle {
            color:#f2f8fc;
            font-size:15pt;
            font-weight:750;
        }
        QLabel#routeValueFrontier {
            color:#eaf6fb;
            font-size:10.5pt;
            font-weight:700;
        }
        QLabel#capabilityNumber {
            color:#071018;
            background:#5ce1ff;
            border-radius:16px;
            min-width:32px;
            max-width:32px;
            min-height:32px;
            max-height:32px;
            qproperty-alignment:AlignCenter;
            font-weight:900;
        }
        QLabel#capabilityTitle {
            color:#eaf3f8;
            font-size:10.5pt;
            font-weight:700;
        }
        QPushButton#frontierPrimary {
            background:#61e5ff;
            color:#031015;
            border:1px solid #9cf0ff;
            border-radius:10px;
            padding:13px 18px;
            min-height:24px;
            font-size:10.5pt;
            font-weight:900;
        }
        QPushButton#frontierPrimary:hover { background:#94efff; }
        QPushButton#frontierDemo, QPushButton#frontierSecondary {
            background:#122634;
            color:#a9efff;
            border:1px solid #29566b;
            border-radius:10px;
            padding:12px 16px;
            min-height:24px;
            font-weight:800;
        }
        QPushButton#frontierDemo:hover, QPushButton#frontierSecondary:hover {
            background:#183344;
            border-color:#3e819c;
        }
        QPushButton#frontierGhost, QPushButton#topGhostButton, QPushButton#detailsToggle {
            background:#0b131b;
            color:#9fb1bd;
            border:1px solid #24333f;
            border-radius:9px;
            padding:10px 13px;
            font-weight:650;
        }
        QPushButton#frontierGhost:hover, QPushButton#topGhostButton:hover, QPushButton#detailsToggle:hover {
            color:#f4fbff;
            border-color:#3b6074;
            background:#101d27;
        }
        QProgressBar#missionProgress {
            background:#080d13;
            border:1px solid #172632;
            border-radius:4px;
            min-height:7px;
            max-height:7px;
        }
        QProgressBar#missionProgress::chunk { background:#5ce1ff; border-radius:3px; }
        QTextEdit#frontierTelemetry {
            background:#070c12;
            color:#9cb3c0;
            border:1px solid #192a36;
            border-radius:9px;
            padding:8px;
            font-family:"Cascadia Mono","Consolas",monospace;
            font-size:9pt;
        }
        QScrollBar:vertical {
            background:#060a0f;
            width:10px;
            margin:1px;
        }
        QScrollBar::handle:vertical {
            background:#263846;
            min-height:28px;
            border-radius:5px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """
    )

    update_frontier_state()
    window.nav.setCurrentRow(window.page_index["Autopilot"])
    window.frontier_scroll = scroll
    window.frontier_process_button = process_button
    window.frontier_demo_button = demo_button
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
