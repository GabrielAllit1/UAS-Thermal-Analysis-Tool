from __future__ import annotations

import time


def create_workspace_window(session):
    """Create the responsive AI-first v0.9 mission-control workspace.

    v0.8 established the product workflow. This layer hardens runtime discovery so no Ollama/backend
    probe executes on the Qt event thread, continuously repopulates local models, and presents the
    existing quantitative tools through a denser mission-control visual system.
    """

    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import (
        QComboBox,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidgetItem,
        QProgressBar,
        QPushButton,
        QSizePolicy,
        QTextEdit,
        QVBoxLayout,
    )

    from ..platform.config import AppConfig
    from .autopilot import RuntimeSnapshot, autopilot_summary, scan_runtime
    from .runtime_monitor import RuntimeMonitor
    from .workspace_ui_v4 import create_workspace_window as create_v4_workspace

    app, window = create_v4_workspace(session)
    config = AppConfig.from_env()
    window.setWindowTitle("UAS Thermal Intelligence — Autonomous Mission Control")
    window.setMinimumSize(1180, 720)
    window.resize(1560, 930)
    app.setFont(QFont("Segoe UI Variable", 10))

    # Move the autonomous workflow to the first navigation position without breaking the stacked-page
    # index contract inherited from prior workspaces.
    ordered = [name for name, _ in sorted(window.page_index.items(), key=lambda item: item[1])]
    if "Autopilot" in ordered and ordered[0] != "Autopilot":
        old_index = window.page_index["Autopilot"]
        autopilot_page = window.pages.widget(old_index)
        window.pages.removeWidget(autopilot_page)
        window.pages.insertWidget(0, autopilot_page)
        nav_item = window.nav.takeItem(old_index)
        window.nav.insertItem(0, nav_item or QListWidgetItem("Autopilot"))
        ordered.remove("Autopilot")
        ordered.insert(0, "Autopilot")
        window.page_index = {name: index for index, name in enumerate(ordered)}

    nav_labels = {
        "Autopilot": "AUTOPILOT",
        "Projects": "PROJECTS",
        "Overview": "MISSION OVERVIEW",
        "Data": "DATA INGEST",
        "Explore": "THERMAL LAB",
        "Analyze": "ANALYSIS",
        "Processing": "PROCESSING",
        "Findings": "FINDINGS",
        "Compare": "COMPARE",
        "Reports": "REPORTS",
        "Exports": "EXPORTS",
        "Analytics": "ANALYTICS",
        "Profiles": "PROFILES",
        "Settings": "SYSTEM",
        "Measurements": "MEASURE",
        "Process": "PIPELINE",
    }
    for name, index in window.page_index.items():
        item = window.nav.item(index)
        if item is not None:
            item.setText(nav_labels.get(name, name.upper()))
    window.nav.setMinimumWidth(185)
    window.nav.setMaximumWidth(215)
    window.nav.setSpacing(2)
    window.nav.setObjectName("missionNav")

    # The prior Windows screenshots exposed tiny typography, weak hierarchy, and default-looking
    # controls. Keep the proven widgets, but give the entire application a coherent high-density shell.
    window.setStyleSheet(
        """
        QMainWindow,QWidget {
            background:#070b11;
            color:#dce8f2;
            font-family:"Segoe UI Variable","Segoe UI",sans-serif;
            font-size:10pt;
        }
        QFrame#header {
            background:#090f17;
            border:0;
            border-bottom:1px solid #162534;
            min-height:46px;
        }
        QFrame#intelligenceRibbon {
            background:#07131d;
            border:0;
            border-bottom:1px solid #123247;
            min-height:30px;
        }
        QFrame#commandBar {
            background:#090f17;
            border:0;
            border-bottom:1px solid #162534;
            min-height:42px;
        }
        QFrame#frontierCard,QFrame#intelligenceCard {
            background:#0b121b;
            border:1px solid #1b2b3a;
            border-radius:12px;
        }
        QFrame#frontierCard:hover { border:1px solid #27506a; }
        QListWidget#missionNav {
            background:#080d14;
            border:0;
            border-right:1px solid #162534;
            padding:9px 7px;
            outline:0;
        }
        QListWidget#missionNav::item {
            color:#7990a2;
            border:0;
            border-left:3px solid transparent;
            border-radius:6px;
            padding:10px 11px;
            margin:1px 0;
            font-size:9pt;
            font-weight:600;
        }
        QListWidget#missionNav::item:hover {
            color:#d8edf9;
            background:#0d1822;
        }
        QListWidget#missionNav::item:selected {
            color:#effbff;
            background:#102332;
            border-left:3px solid #25d5ff;
        }
        QLabel#eyebrow {
            color:#37cfff;
            font-size:8.5pt;
            font-weight:700;
        }
        QLabel#heroTitle {
            color:#f4fbff;
            font-size:23pt;
            font-weight:700;
        }
        QLabel#heroSub { color:#8ca4b7; font-size:10.5pt; }
        QLabel#statusGood { color:#4ce8ad; font-weight:700; }
        QLabel#statusWarn { color:#ffd166; font-weight:700; }
        QLabel#runtimeState { color:#4ce8ad; font-weight:700; font-size:9pt; }
        QLabel#routeValue { color:#f0f8fc; font-size:11pt; font-weight:700; }
        QLabel#muted { color:#6f8799; }
        QGroupBox {
            background:#0a1119;
            border:1px solid #1a2a38;
            border-radius:10px;
            margin-top:13px;
            padding:15px 12px 10px 12px;
            font-weight:600;
            color:#c9d9e4;
        }
        QGroupBox::title {
            subcontrol-origin:margin;
            left:12px;
            padding:0 6px;
            color:#7f9bad;
        }
        QLineEdit,QComboBox,QTextEdit {
            background:#0d1620;
            color:#e9f4fb;
            border:1px solid #223545;
            border-radius:7px;
            padding:7px 9px;
            selection-background-color:#116b91;
        }
        QLineEdit:focus,QComboBox:focus,QTextEdit:focus { border:1px solid #2abde9; }
        QComboBox { min-height:22px; }
        QPushButton {
            background:#13212d;
            color:#dcebf4;
            border:1px solid #284052;
            border-radius:7px;
            padding:8px 12px;
            font-weight:600;
        }
        QPushButton:hover { background:#193040; border-color:#347195; color:white; }
        QPushButton:pressed { background:#0d536f; }
        QPushButton:disabled { background:#0b1117; color:#405361; border-color:#17232d; }
        QPushButton#autopilotPrimary {
            background:#18c7ef;
            color:#021017;
            border:1px solid #44dcff;
            border-radius:8px;
            padding:9px 16px;
            font-size:10pt;
            font-weight:800;
        }
        QPushButton#autopilotPrimary:hover { background:#54ddfa; }
        QPushButton#autopilotSecondary { background:#0d1c27; border-color:#24475c; }
        QTableView,QTableWidget {
            background:#091019;
            alternate-background-color:#0b141e;
            border:1px solid #1a2b39;
            border-radius:8px;
            gridline-color:#142330;
            selection-background-color:#113249;
            selection-color:#ffffff;
        }
        QHeaderView::section {
            background:#0e1822;
            color:#7891a3;
            border:0;
            border-bottom:1px solid #20303e;
            padding:8px;
            font-size:8.5pt;
            font-weight:700;
        }
        QProgressBar {
            background:#0a121a;
            border:1px solid #1a2b39;
            border-radius:4px;
            max-height:7px;
            text-align:center;
        }
        QProgressBar::chunk { background:#25d5ff; border-radius:3px; }
        QScrollBar:vertical { background:#080d13; width:9px; margin:0; }
        QScrollBar::handle:vertical { background:#274052; min-height:28px; border-radius:4px; }
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
        QToolTip { background:#101b25; color:#e6f3fa; border:1px solid #2b4c61; padding:5px; }
        """
    )

    # Persistent command bar. Runtime discovery is deliberately shown as ambient system state rather
    # than a workflow users must manually initiate.
    root_layout = window.centralWidget().layout()
    command_bar = QFrame()
    command_bar.setObjectName("commandBar")
    command_layout = QHBoxLayout(command_bar)
    command_layout.setContentsMargins(14, 5, 14, 5)
    core = QLabel("AUTONOMY CORE")
    core.setObjectName("eyebrow")
    runtime_state = QLabel("DISCOVERING LOCAL STACK")
    runtime_state.setObjectName("runtimeState")
    runtime_progress = QProgressBar()
    runtime_progress.setRange(0, 0)
    runtime_progress.setFixedWidth(110)
    runtime_progress.setTextVisible(False)
    route_summary = QLabel("AI ROUTING · CALCULATING")
    route_summary.setObjectName("muted")
    command_layout.addWidget(core)
    command_layout.addSpacing(14)
    command_layout.addWidget(runtime_state)
    command_layout.addWidget(runtime_progress)
    command_layout.addSpacing(16)
    command_layout.addWidget(route_summary, 1)
    auto_badge = QLabel("AUTO-DISCOVERY · BACKGROUND")
    auto_badge.setObjectName("eyebrow")
    command_layout.addWidget(auto_badge)
    root_layout.insertWidget(2, command_bar)

    # Add a routing matrix directly to Autopilot so users can see that different local models are
    # selected for different kinds of work rather than one arbitrary model being used everywhere.
    autopilot_page = window.pages.widget(window.page_index["Autopilot"])
    autopilot_layout = autopilot_page.layout()
    routing_card = QFrame()
    routing_card.setObjectName("frontierCard")
    routing_layout = QHBoxLayout(routing_card)
    routing_layout.setContentsMargins(14, 10, 14, 10)
    routing_title = QVBoxLayout()
    routing_eyebrow = QLabel("LOCAL MODEL ROUTER")
    routing_eyebrow.setObjectName("eyebrow")
    routing_note = QLabel("Autopilot continuously ranks installed models by task capability and cost of latency.")
    routing_note.setObjectName("muted")
    routing_note.setWordWrap(True)
    routing_title.addWidget(routing_eyebrow)
    routing_title.addWidget(routing_note)
    routing_layout.addLayout(routing_title, 2)
    route_labels: dict[str, QLabel] = {}
    for key, heading in (
        ("vision_review", "VISION REVIEW"),
        ("engineering_narrative", "ENGINEERING NARRATIVE"),
        ("fast_triage", "FAST TRIAGE"),
    ):
        column = QVBoxLayout()
        label = QLabel(heading)
        label.setObjectName("eyebrow")
        value = QLabel("DETECTING…")
        value.setObjectName("routeValue")
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        column.addWidget(label)
        column.addWidget(value)
        routing_layout.addLayout(column, 1)
        route_labels[key] = value
    autopilot_layout.insertWidget(4, routing_card)

    # Replace the old synchronous runtime UI with a live system panel.
    for box in window.findChildren(QGroupBox):
        if box.title() == "Local processing runtimes":
            box.hide()
    settings_page = window.pages.widget(window.page_index["Settings"])
    settings_layout = settings_page.layout()
    live_runtime = QFrame()
    live_runtime.setObjectName("frontierCard")
    live_layout = QVBoxLayout(live_runtime)
    live_head = QHBoxLayout()
    live_title = QLabel("INTELLIGENCE RUNTIME")
    live_title.setObjectName("eyebrow")
    live_status = QLabel("Background discovery starting…")
    live_status.setObjectName("runtimeState")
    live_head.addWidget(live_title)
    live_head.addStretch(1)
    live_head.addWidget(live_status)
    live_layout.addLayout(live_head)
    live_models = QLabel("Ollama · detecting")
    live_models.setWordWrap(True)
    live_models.setObjectName("muted")
    live_stitch = QLabel("Stitch backends · detecting")
    live_stitch.setObjectName("muted")
    live_layout.addWidget(live_models)
    live_layout.addWidget(live_stitch)
    settings_layout.insertWidget(2, live_runtime)

    monitor = RuntimeMonitor(lambda: scan_runtime(config=config), min_interval_s=18.0)
    window.runtime_monitor = monitor
    window.runtime_last_applied = 0.0

    def find_ai_combos() -> list[QComboBox]:
        matches: list[QComboBox] = []
        for combo in window.findChildren(QComboBox):
            texts = [combo.itemText(index).lower() for index in range(combo.count())]
            if any("auto-select" in text for text in texts) and any("deterministic" in text or text == "off" for text in texts):
                matches.append(combo)
        return matches

    def repopulate_ai_combos(snapshot: RuntimeSnapshot) -> None:
        for combo in find_ai_combos():
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            preferred = snapshot.routes.vision_review or snapshot.routes.engineering_narrative
            auto_text = "Autopilot routing · task-aware"
            if preferred:
                auto_text += f" · {preferred}"
            combo.addItem(auto_text, "auto")
            combo.addItem("Deterministic only", "off")
            for model in snapshot.models:
                tags = []
                if model.supports_vision:
                    tags.append("VISION")
                if model.parameter_size:
                    tags.append(model.parameter_size)
                suffix = f" · {' · '.join(tags)}" if tags else ""
                combo.addItem(f"{model.name}{suffix}", model.name)
            target = combo.findData(current)
            combo.setCurrentIndex(target if target >= 0 else 0)
            combo.blockSignals(False)

    # Capture the existing v0.8 readiness labels by their initial values; they are private closure
    # objects in v4, so this keeps the wrapper additive rather than duplicating the proven page.
    readiness_values: dict[str, QLabel] = {}
    initial_map = {
        "0 SOURCES": "sources",
        "GATED": "radiometry",
        "SOURCE-DEPENDENT": "stitch",
        "NOT SCANNED": "ai",
        "AUTOMATED": "deliverable",
    }
    for label in window.findChildren(QLabel):
        key = initial_map.get(label.text())
        if key and key not in readiness_values:
            readiness_values[key] = label

    autopilot_log = None
    for text_edit in window.findChildren(QTextEdit):
        if "Autopilot telemetry" in text_edit.placeholderText():
            autopilot_log = text_edit
            break

    def update_source_readiness() -> None:
        snapshot = window.autopilot_snapshot
        summary = autopilot_summary(snapshot, len(session.sources))
        if "sources" in readiness_values:
            readiness_values["sources"].setText(f"{summary['sources']} SOURCES")
        if "stitch" in readiness_values:
            readiness_values["stitch"].setText(summary["stitch"])
        if "ai" in readiness_values:
            readiness_values["ai"].setText(summary["ai"])
        labels = getattr(window, "intelligence_ribbon_labels", {})
        if "stitch" in labels:
            labels["stitch"].setText(f"AUTONOMOUS STITCH · {summary['stitch']}")
        if "ai" in labels:
            labels["ai"].setText(f"LOCAL AI · {summary['ai']}")

    def apply_snapshot(snapshot: RuntimeSnapshot) -> None:
        window.autopilot_snapshot = snapshot
        window.runtime_last_applied = time.monotonic()
        runtime_progress.hide()
        if snapshot.ai_available:
            runtime_state.setText(f"LOCAL AI READY · {len(snapshot.model_names)} MODELS")
            live_status.setText("READY")
            live_models.setText(
                f"Ollama · {len(snapshot.model_names)} model(s) · {len(snapshot.vision_models)} vision-capable · {config.ollama_base_url}"
            )
        else:
            runtime_state.setText("LOCAL AI OFFLINE · DETERMINISTIC FALLBACK READY")
            live_status.setText("DEGRADED / SAFE FALLBACK")
            live_models.setText(f"Ollama · {snapshot.ai_error or 'not reachable'} · {config.ollama_base_url}")
        available_backends = [name for name, available in snapshot.orthomosaic_backends if available]
        live_stitch.setText(
            "Stitch backends · " + (", ".join(available_backends) if available_backends else "source-dependent")
        )
        routes = snapshot.routes
        for key, value in routes.as_dict().items():
            route_labels[key].setText(value or "DETERMINISTIC")
        route_summary.setText(
            "AI ROUTING · "
            f"VISION {routes.vision_review or 'NONE'} · "
            f"NARRATIVE {routes.engineering_narrative or 'NONE'} · "
            f"FAST {routes.fast_triage or 'NONE'}"
        )
        repopulate_ai_combos(snapshot)
        update_source_readiness()
        if autopilot_log is not None:
            autopilot_log.append(
                f"Runtime auto-discovery: {len(snapshot.model_names)} local model(s), "
                f"{len(snapshot.vision_models)} vision model(s); task routing refreshed."
            )

    def request_runtime_refresh(force: bool = False) -> None:
        if monitor.request_refresh(force=force):
            runtime_state.setText("DISCOVERING LOCAL STACK")
            live_status.setText("SCANNING IN BACKGROUND")
            runtime_progress.show()

    def poll_runtime() -> None:
        update = monitor.poll()
        if update is None:
            return
        if update.snapshot is not None:
            apply_snapshot(update.snapshot)
        else:
            runtime_progress.hide()
            runtime_state.setText("RUNTIME DISCOVERY DEGRADED · APP REMAINS RESPONSIVE")
            live_status.setText("DISCOVERY ERROR")
            live_models.setText(update.error)

    # Retire every synchronous refresh entry point inherited from v0.7/v0.8. They remain useful as an
    # optional immediate rescan, but all execute through the background monitor now.
    refresh_names = {"Refresh Runtime Status", "Refresh Local Models", "Scan Local Stack"}
    for button in window.findChildren(QPushButton):
        if button.text() in refresh_names:
            try:
                button.clicked.disconnect()
            except TypeError:
                pass
            button.setText("Rescan now")
            button.setToolTip("Optional diagnostic rescan. Runtime/model discovery refreshes automatically.")
            button.clicked.connect(lambda _checked=False: request_runtime_refresh(True))

    poll_timer = QTimer(window)
    poll_timer.setInterval(100)
    poll_timer.timeout.connect(poll_runtime)
    poll_timer.start()
    window.runtime_poll_timer = poll_timer

    auto_timer = QTimer(window)
    auto_timer.setInterval(30_000)
    auto_timer.timeout.connect(request_runtime_refresh)
    auto_timer.start()
    window.runtime_auto_timer = auto_timer

    source_timer = QTimer(window)
    source_timer.setInterval(750)
    source_timer.timeout.connect(update_source_readiness)
    source_timer.start()
    window.source_readiness_timer = source_timer

    def page_changed(_row: int) -> None:
        # Page navigation remains O(1). A stale runtime refresh is merely queued in the background.
        if time.monotonic() - window.runtime_last_applied > 20.0:
            request_runtime_refresh()

    window.nav.currentRowChanged.connect(page_changed)
    app.aboutToQuit.connect(monitor.close)

    runtime_progress.show()
    QTimer.singleShot(50, request_runtime_refresh)
    window.nav.setCurrentRow(window.page_index["Autopilot"])
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
