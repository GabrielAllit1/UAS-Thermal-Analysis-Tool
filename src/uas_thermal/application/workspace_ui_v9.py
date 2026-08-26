from __future__ import annotations

from collections import Counter
from pathlib import Path


def create_workspace_window(session):
    """Create the v0.12 consumer-grade mission workspace.

    The existing v0.11 workspace remains the implementation authority for one-click intake,
    background runtime discovery, processing, reporting and specialist tools. This layer replaces the
    default Home presentation with three operator states: Ready -> Processing -> Inspection Ready.
    """

    from PyQt5.QtCore import QTimer, Qt, QUrl
    from PyQt5.QtGui import QDesktopServices, QFont, QPixmap
    from PyQt5.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QStackedWidget,
        QTableWidget,
        QVBoxLayout,
        QWidget,
    )

    from .workspace_ui_v8 import create_workspace_window as create_v8_workspace

    app, window = create_v8_workspace(session)
    app.setFont(QFont("Segoe UI Variable", 11))
    window.setWindowTitle("UAS Thermal Intelligence")
    window.setMinimumSize(900, 560)
    window.resize(1480, 920)

    # --- Simplified product navigation -------------------------------------
    normal_pages = {
        "Autopilot": "Home",
        "Projects": "Projects",
        "Overview": "Mission",
        "Data": "Mission Data",
        "Explore": "Thermal Review",
        "Findings": "Findings",
        "Compare": "Compare",
        "Reports": "Reports",
        "Analytics": "Analytics",
        "Settings": "Settings",
    }
    advanced_pages = {
        "Analyze": "Analysis",
        "Processing": "Processing",
        "Exports": "Exports",
        "Profiles": "Profiles",
        "Measurements": "Measurements",
        "Process": "Pipeline",
    }
    window.nav.setMinimumWidth(154)
    window.nav.setMaximumWidth(184)
    for name, index in window.page_index.items():
        item = window.nav.item(index)
        if item is None:
            continue
        if name in normal_pages:
            item.setText(normal_pages[name])
            item.setHidden(False)
        elif name in advanced_pages:
            item.setText(advanced_pages[name])
            item.setHidden(True)

    inspector = getattr(window, "inspector", None)
    if inspector is not None:
        inspector.hide()
    old_inspector_toggle = window.findChild(QPushButton, "topGhostButton")
    if old_inspector_toggle is not None:
        old_inspector_toggle.hide()

    header = window.findChild(QFrame, "header")
    if header is not None:
        header.setMinimumHeight(58)
        for label in header.findChildren(QLabel):
            if label.objectName() == "brandTitle" or label.text() in {
                "UAS Thermal Intelligence",
                "UAS Thermal Analysis",
            }:
                label.setText("Thermal Intelligence")
                label.setObjectName("consumerBrand")
            elif label is getattr(window, "project_header", None):
                label.setObjectName("consumerProject")
            elif label is getattr(window, "header_status", None):
                label.setObjectName("consumerStatus")

    advanced_toggle = QPushButton("Advanced tools")
    advanced_toggle.setObjectName("headerAction")
    advanced_visible = {"value": False}

    def set_advanced_visible(visible: bool) -> None:
        advanced_visible["value"] = visible
        for name in advanced_pages:
            item = window.nav.item(window.page_index[name])
            if item is not None:
                item.setHidden(not visible)
        advanced_toggle.setText("Hide advanced tools" if visible else "Advanced tools")

    def toggle_advanced() -> None:
        set_advanced_visible(not advanced_visible["value"])

    advanced_toggle.clicked.connect(toggle_advanced)
    if header is not None and header.layout() is not None:
        header.layout().addWidget(advanced_toggle)

    # --- Capture existing authoritative actions before hiding v0.11 Home ---
    old_scroll = window.findChild(QScrollArea, "autopilotScroll")
    old_primary = window.findChild(QPushButton, "frontierPrimary")
    old_demo = window.findChild(QPushButton, "frontierDemo")
    old_review = window.findChild(QPushButton, "frontierGhost")
    pipeline = window.findChild(QTableWidget, "pipelineTable")
    if old_scroll is not None:
        old_scroll.hide()

    autopilot_page = window.pages.widget(window.page_index["Autopilot"])
    autopilot_layout = autopilot_page.layout()
    autopilot_layout.setContentsMargins(0, 0, 0, 0)
    autopilot_layout.setSpacing(0)

    # --- New Home canvas ----------------------------------------------------
    scroll = QScrollArea()
    scroll.setObjectName("consumerHomeScroll")
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    canvas = QWidget()
    canvas.setObjectName("consumerCanvas")
    canvas.setMinimumWidth(0)
    body = QVBoxLayout(canvas)
    body.setContentsMargins(30, 28, 30, 34)
    body.setSpacing(18)

    # Small ambient system line. No model names or implementation plumbing.
    ambient = QHBoxLayout()
    ambient_title = QLabel("Autonomous thermal post-processing")
    ambient_title.setObjectName("ambientTitle")
    ambient.addWidget(ambient_title)
    ambient.addStretch(1)
    ambient_state = QLabel("Local intelligence checking…")
    ambient_state.setObjectName("ambientPill")
    ambient.addWidget(ambient_state)
    body.addLayout(ambient)

    home_stack = QStackedWidget()
    home_stack.setObjectName("homeStateStack")
    body.addWidget(home_stack)

    # READY -----------------------------------------------------------------
    ready_page = QWidget()
    ready_layout = QVBoxLayout(ready_page)
    ready_layout.setContentsMargins(0, 0, 0, 0)
    ready_layout.setSpacing(18)

    launch = QFrame()
    launch.setObjectName("launchSurface")
    launch_layout = QGridLayout(launch)
    launch_layout.setContentsMargins(34, 32, 34, 32)
    launch_layout.setHorizontalSpacing(32)
    launch_layout.setVerticalSpacing(14)

    launch_copy = QVBoxLayout()
    launch_kicker = QLabel("Flight complete? Your post-processing starts here.")
    launch_kicker.setObjectName("launchKicker")
    launch_title = QLabel("Turn a mission folder into a finished thermal inspection.")
    launch_title.setObjectName("launchTitle")
    launch_title.setWordWrap(True)
    launch_subtitle = QLabel(
        "Choose the folder from your drone mission. Thermal Intelligence discovers the data, "
        "validates quantitative thermal sources, stitches when appropriate, detects and prioritizes "
        "anomalies, prepares evidence, and builds the client + engineering package."
    )
    launch_subtitle.setObjectName("launchSubtitle")
    launch_subtitle.setWordWrap(True)
    launch_copy.addWidget(launch_kicker)
    launch_copy.addWidget(launch_title)
    launch_copy.addWidget(launch_subtitle)
    launch_layout.addLayout(launch_copy, 0, 0, 1, 2)

    choose_button = QPushButton("Choose mission folder")
    choose_button.setObjectName("consumerPrimary")
    choose_button.setMinimumHeight(52)
    demo_button = QPushButton("Run guided example")
    demo_button.setObjectName("consumerSecondary")
    demo_button.setMinimumHeight(52)
    launch_layout.addWidget(choose_button, 1, 0)
    launch_layout.addWidget(demo_button, 1, 1)

    no_upload = QLabel("Runs locally on this workstation • source files stay in place")
    no_upload.setObjectName("trustLine")
    launch_layout.addWidget(no_upload, 2, 0, 1, 2)
    launch_layout.setColumnStretch(0, 3)
    launch_layout.setColumnStretch(1, 2)
    ready_layout.addWidget(launch)

    flow_card = QFrame()
    flow_card.setObjectName("softCard")
    flow_layout = QVBoxLayout(flow_card)
    flow_layout.setContentsMargins(22, 20, 22, 22)
    flow_layout.setSpacing(14)
    flow_heading = QLabel("What Autopilot handles for you")
    flow_heading.setObjectName("sectionTitle")
    flow_copy = QLabel(
        "You should not need to learn a processing sequence before getting a useful result."
    )
    flow_copy.setObjectName("sectionCopy")
    flow_layout.addWidget(flow_heading)
    flow_layout.addWidget(flow_copy)

    stages_grid = QGridLayout()
    stages_grid.setHorizontalSpacing(10)
    stages_grid.setVerticalSpacing(10)
    stage_specs = (
        ("1", "Discover", "Thermal, visible, GIS and mission context"),
        ("2", "Build", "Quantitative thermal map when supported"),
        ("3", "Detect", "Anomalies, Delta T and severity"),
        ("4", "Review", "Local AI evidence context when available"),
        ("5", "Deliver", "Report, findings, maps and client viewer"),
    )
    for index, (number, title, description) in enumerate(stage_specs):
        card = QFrame()
        card.setObjectName("flowStep")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 13, 14, 13)
        card_layout.setSpacing(5)
        number_label = QLabel(number)
        number_label.setObjectName("stepNumber")
        title_label = QLabel(title)
        title_label.setObjectName("stepTitle")
        description_label = QLabel(description)
        description_label.setObjectName("stepCopy")
        description_label.setWordWrap(True)
        card_layout.addWidget(number_label)
        card_layout.addWidget(title_label)
        card_layout.addWidget(description_label)
        row = 0 if index < 3 else 1
        column = index if index < 3 else index - 3
        stages_grid.addWidget(card, row, column)
    stages_grid.setColumnStretch(0, 1)
    stages_grid.setColumnStretch(1, 1)
    stages_grid.setColumnStretch(2, 1)
    flow_layout.addLayout(stages_grid)
    ready_layout.addWidget(flow_card)

    outputs = QFrame()
    outputs.setObjectName("softCard")
    outputs_layout = QHBoxLayout(outputs)
    outputs_layout.setContentsMargins(22, 18, 22, 18)
    outputs_text = QVBoxLayout()
    output_heading = QLabel("A deliverable, not another processing project")
    output_heading.setObjectName("sectionTitle")
    output_copy = QLabel(
        "Inspection PDF • annotated thermal evidence • finding register • quantitative GeoTIFF when "
        "supported • CSV/JSON • GIS outputs when authoritative • portable client viewer • provenance"
    )
    output_copy.setObjectName("sectionCopy")
    output_copy.setWordWrap(True)
    outputs_text.addWidget(output_heading)
    outputs_text.addWidget(output_copy)
    outputs_layout.addLayout(outputs_text, 1)
    learn_more = QPushButton("Advanced tools")
    learn_more.setObjectName("quietButton")
    learn_more.clicked.connect(lambda: set_advanced_visible(True))
    outputs_layout.addWidget(learn_more)
    ready_layout.addWidget(outputs)
    ready_layout.addStretch(1)
    home_stack.addWidget(ready_page)

    # PROCESSING ------------------------------------------------------------
    running_page = QWidget()
    running_layout = QVBoxLayout(running_page)
    running_layout.setContentsMargins(0, 0, 0, 0)
    running_layout.setSpacing(18)

    running_card = QFrame()
    running_card.setObjectName("runningSurface")
    running_card_layout = QVBoxLayout(running_card)
    running_card_layout.setContentsMargins(34, 34, 34, 34)
    running_card_layout.setSpacing(13)
    running_kicker = QLabel("Autopilot is working")
    running_kicker.setObjectName("launchKicker")
    running_title = QLabel("Preparing the inspection…")
    running_title.setObjectName("runningTitle")
    running_title.setWordWrap(True)
    running_detail = QLabel(
        "Thermal Intelligence is processing the mission locally. You can continue using the rest of "
        "the application while this runs."
    )
    running_detail.setObjectName("launchSubtitle")
    running_detail.setWordWrap(True)
    running_progress = QProgressBar()
    running_progress.setObjectName("consumerProgress")
    running_progress.setRange(0, 100)
    running_progress.setValue(5)
    running_progress.setTextVisible(False)
    running_percent = QLabel("5%")
    running_percent.setObjectName("progressPercent")
    running_card_layout.addWidget(running_kicker)
    running_card_layout.addWidget(running_title)
    running_card_layout.addWidget(running_detail)
    running_card_layout.addSpacing(6)
    running_card_layout.addWidget(running_progress)
    running_card_layout.addWidget(running_percent, 0, Qt.AlignRight)
    running_layout.addWidget(running_card)

    running_info = QFrame()
    running_info.setObjectName("softCard")
    running_info_layout = QGridLayout(running_info)
    running_info_layout.setContentsMargins(22, 20, 22, 20)
    running_info_layout.setHorizontalSpacing(18)
    running_info_layout.setVerticalSpacing(12)
    running_source_value = QLabel("Reading mission…")
    running_source_value.setObjectName("infoValue")
    running_analysis_value = QLabel("Quantitative gate active")
    running_analysis_value.setObjectName("infoValue")
    running_ai_value = QLabel("Checking local intelligence")
    running_ai_value.setObjectName("infoValue")
    for column, (title, value) in enumerate(
        (
            ("Mission data", running_source_value),
            ("Thermal authority", running_analysis_value),
            ("AI assistance", running_ai_value),
        )
    ):
        title_label = QLabel(title)
        title_label.setObjectName("infoLabel")
        cell = QVBoxLayout()
        cell.addWidget(title_label)
        cell.addWidget(value)
        running_info_layout.addLayout(cell, 0, column)
    running_layout.addWidget(running_info)

    running_note = QLabel(
        "Source measurements and radiometry remain deterministic. Local AI can add evidence context "
        "and narrative where available but does not replace the quantitative thermal calculation."
    )
    running_note.setObjectName("trustLine")
    running_note.setWordWrap(True)
    running_layout.addWidget(running_note)
    running_layout.addStretch(1)
    home_stack.addWidget(running_page)

    # COMPLETE --------------------------------------------------------------
    complete_page = QWidget()
    complete_layout = QVBoxLayout(complete_page)
    complete_layout.setContentsMargins(0, 0, 0, 0)
    complete_layout.setSpacing(16)

    complete_head = QHBoxLayout()
    complete_copy = QVBoxLayout()
    complete_kicker = QLabel("Inspection ready")
    complete_kicker.setObjectName("completeKicker")
    complete_title = QLabel("Your thermal deliverable is ready to review and share.")
    complete_title.setObjectName("completeTitle")
    complete_title.setWordWrap(True)
    complete_copy.addWidget(complete_kicker)
    complete_copy.addWidget(complete_title)
    complete_head.addLayout(complete_copy, 1)
    new_mission = QPushButton("Process another mission")
    new_mission.setObjectName("quietButton")
    complete_head.addWidget(new_mission, 0, Qt.AlignTop)
    complete_layout.addLayout(complete_head)

    result_grid = QGridLayout()
    result_grid.setHorizontalSpacing(16)
    result_grid.setVerticalSpacing(16)

    visual_card = QFrame()
    visual_card.setObjectName("resultVisualCard")
    visual_layout = QVBoxLayout(visual_card)
    visual_layout.setContentsMargins(12, 12, 12, 12)
    visual_layout.setSpacing(9)
    visual_label = QLabel("Annotated thermal overview")
    visual_label.setObjectName("resultCaption")
    visual_image = QLabel("Annotated thermal overview will appear here")
    visual_image.setObjectName("resultImage")
    visual_image.setAlignment(Qt.AlignCenter)
    visual_image.setMinimumHeight(360)
    visual_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    visual_image.setScaledContents(False)
    visual_layout.addWidget(visual_label)
    visual_layout.addWidget(visual_image, 1)
    result_grid.addWidget(visual_card, 0, 0)

    summary_card = QFrame()
    summary_card.setObjectName("resultSummaryCard")
    summary_layout = QVBoxLayout(summary_card)
    summary_layout.setContentsMargins(22, 22, 22, 22)
    summary_layout.setSpacing(12)
    summary_heading = QLabel("Inspection summary")
    summary_heading.setObjectName("sectionTitle")
    finding_total = QLabel("0")
    finding_total.setObjectName("findingTotal")
    finding_note = QLabel("canonical findings")
    finding_note.setObjectName("sectionCopy")
    summary_layout.addWidget(summary_heading)
    summary_layout.addWidget(finding_total)
    summary_layout.addWidget(finding_note)

    severity_grid = QGridLayout()
    severity_values: dict[str, QLabel] = {}
    for column, severity in enumerate(("Critical", "Moderate", "Minor")):
        block = QFrame()
        block.setObjectName(f"severity{severity}")
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(10, 10, 10, 10)
        value = QLabel("0")
        value.setObjectName("severityValue")
        label = QLabel(severity)
        label.setObjectName("severityLabel")
        block_layout.addWidget(value)
        block_layout.addWidget(label)
        severity_grid.addWidget(block, 0, column)
        severity_values[severity.lower()] = value
    summary_layout.addLayout(severity_grid)

    result_quality = QLabel("Quantitative thermal result • provenance preserved")
    result_quality.setObjectName("trustLine")
    result_quality.setWordWrap(True)
    summary_layout.addWidget(result_quality)
    summary_layout.addStretch(1)

    review_findings = QPushButton("Review findings")
    review_findings.setObjectName("consumerPrimary")
    open_report = QPushButton("Open inspection report")
    open_report.setObjectName("consumerSecondary")
    open_viewer = QPushButton("Open client viewer")
    open_viewer.setObjectName("quietButton")
    open_folder = QPushButton("Open deliverable folder")
    open_folder.setObjectName("quietButton")
    summary_layout.addWidget(review_findings)
    summary_layout.addWidget(open_report)
    summary_layout.addWidget(open_viewer)
    summary_layout.addWidget(open_folder)
    result_grid.addWidget(summary_card, 0, 1)
    result_grid.setColumnStretch(0, 7)
    result_grid.setColumnStretch(1, 3)
    complete_layout.addLayout(result_grid, 1)
    home_stack.addWidget(complete_page)

    # Error strip stays inline instead of becoming the entire product experience.
    error_strip = QFrame()
    error_strip.setObjectName("errorStrip")
    error_layout = QHBoxLayout(error_strip)
    error_layout.setContentsMargins(16, 10, 16, 10)
    error_text = QLabel("")
    error_text.setObjectName("errorText")
    error_text.setWordWrap(True)
    error_dismiss = QPushButton("Dismiss")
    error_dismiss.setObjectName("quietButton")
    error_layout.addWidget(error_text, 1)
    error_layout.addWidget(error_dismiss)
    error_strip.hide()
    body.insertWidget(1, error_strip)

    scroll.setWidget(canvas)
    autopilot_layout.addWidget(scroll, 1)

    # --- Styling ------------------------------------------------------------
    window.setStyleSheet(
        window.styleSheet()
        + """
        QMainWindow,QWidget {
            background:#080d13;
            color:#e7eef5;
            font-family:"Segoe UI Variable","Segoe UI",sans-serif;
            font-size:11pt;
        }
        QFrame#header {
            background:#0b1119;
            border:0;
            border-bottom:1px solid #1b2835;
        }
        QLabel#consumerBrand { color:#f5f9fc; font-size:16pt; font-weight:750; }
        QLabel#consumerProject { color:#73879a; font-size:9.5pt; }
        QLabel#consumerStatus { color:#7ddfb5; font-size:9.5pt; font-weight:650; }
        QPushButton#headerAction {
            background:#101a24;
            border:1px solid #243545;
            border-radius:8px;
            color:#9fb1c0;
            padding:7px 11px;
        }
        QListWidget#missionNav {
            background:#090f16;
            border:0;
            border-right:1px solid #182532;
            padding:12px 8px;
        }
        QListWidget#missionNav::item {
            color:#8ea1b1;
            border:0;
            border-radius:8px;
            padding:11px 12px;
            margin:2px 0;
            font-size:10pt;
            font-weight:600;
        }
        QListWidget#missionNav::item:hover { background:#101a24; color:#d6e0e8; }
        QListWidget#missionNav::item:selected {
            background:#112534;
            color:#ecf9ff;
            border-left:3px solid #45d5ff;
        }
        QScrollArea#consumerHomeScroll,QWidget#consumerCanvas { background:#080d13; border:0; }
        QLabel#ambientTitle { color:#8297a8; font-size:9.5pt; font-weight:650; }
        QLabel#ambientPill {
            color:#75e4b7;
            background:#0d211b;
            border:1px solid #173b30;
            border-radius:10px;
            padding:5px 9px;
            font-size:8.5pt;
            font-weight:700;
        }
        QFrame#launchSurface {
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #101f2b,stop:0.55 #0f1722,stop:1 #161422);
            border:1px solid #244154;
            border-radius:18px;
        }
        QLabel#launchKicker { color:#56d8ff; font-size:10pt; font-weight:750; }
        QLabel#launchTitle { color:#f7fbff; font-size:28pt; font-weight:780; }
        QLabel#launchSubtitle { color:#a5b6c4; font-size:11.5pt; line-height:1.35; }
        QLabel#trustLine { color:#6f8495; font-size:9pt; }
        QPushButton#consumerPrimary {
            background:#35c9f2;
            color:#031018;
            border:1px solid #6edfff;
            border-radius:10px;
            padding:12px 18px;
            font-size:11pt;
            font-weight:800;
        }
        QPushButton#consumerPrimary:hover { background:#69ddfb; border-color:#a2ecff; }
        QPushButton#consumerSecondary {
            background:#162430;
            color:#e6f4fa;
            border:1px solid #315066;
            border-radius:10px;
            padding:12px 18px;
            font-size:10.5pt;
            font-weight:700;
        }
        QPushButton#consumerSecondary:hover { background:#1d3140; border-color:#46738e; }
        QPushButton#quietButton {
            background:#0e1720;
            color:#9eb0bd;
            border:1px solid #263644;
            border-radius:8px;
            padding:9px 12px;
            font-weight:650;
        }
        QPushButton#quietButton:hover { color:#eef8fc; background:#14222d; border-color:#38566b; }
        QFrame#softCard,QFrame#runningSurface,QFrame#resultSummaryCard {
            background:#0d151e;
            border:1px solid #1d2b38;
            border-radius:14px;
        }
        QLabel#sectionTitle { color:#eef5fa; font-size:14pt; font-weight:730; }
        QLabel#sectionCopy { color:#859aaa; font-size:9.5pt; }
        QFrame#flowStep {
            background:#0a1119;
            border:1px solid #172633;
            border-radius:10px;
        }
        QLabel#stepNumber {
            color:#51d8ff;
            background:#102936;
            border:1px solid #1b4c61;
            border-radius:10px;
            padding:3px 7px;
            max-width:22px;
            font-size:8.5pt;
            font-weight:800;
        }
        QLabel#stepTitle { color:#eaf2f7; font-size:11pt; font-weight:700; }
        QLabel#stepCopy { color:#718796; font-size:8.5pt; }
        QLabel#runningTitle { color:#f6fbff; font-size:25pt; font-weight:780; }
        QProgressBar#consumerProgress {
            background:#091119;
            border:1px solid #1c3241;
            border-radius:7px;
            min-height:13px;
            max-height:13px;
        }
        QProgressBar#consumerProgress::chunk {
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #31c8f2,stop:1 #65e4ba);
            border-radius:6px;
        }
        QLabel#progressPercent { color:#75e4b7; font-size:10pt; font-weight:750; }
        QLabel#infoLabel { color:#718697; font-size:8.5pt; font-weight:650; }
        QLabel#infoValue { color:#e5eef4; font-size:11pt; font-weight:700; }
        QLabel#completeKicker { color:#66e5b6; font-size:10pt; font-weight:800; }
        QLabel#completeTitle { color:#f6fbff; font-size:23pt; font-weight:760; }
        QFrame#resultVisualCard {
            background:#070b10;
            border:1px solid #20303d;
            border-radius:14px;
        }
        QLabel#resultCaption { color:#8397a7; font-size:9pt; font-weight:650; padding:2px 4px; }
        QLabel#resultImage {
            background:#05080c;
            border:1px solid #17232d;
            border-radius:10px;
            color:#526572;
            font-size:10pt;
        }
        QLabel#findingTotal { color:#f4fbff; font-size:34pt; font-weight:800; }
        QFrame#severityCritical { background:#291318; border:1px solid #5b2630; border-radius:9px; }
        QFrame#severityModerate { background:#282014; border:1px solid #574522; border-radius:9px; }
        QFrame#severityMinor { background:#11231e; border:1px solid #255044; border-radius:9px; }
        QLabel#severityValue { color:#f3f8fb; font-size:17pt; font-weight:800; }
        QLabel#severityLabel { color:#9aabb7; font-size:8pt; }
        QFrame#errorStrip { background:#27181a; border:1px solid #593138; border-radius:10px; }
        QLabel#errorText { color:#f0b5bc; font-size:9.5pt; }
        QScrollBar:vertical { background:#080d13; width:10px; margin:0; }
        QScrollBar::handle:vertical { background:#263846; min-height:34px; border-radius:5px; }
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
        """
    )

    # --- Proxy actions / result actions ------------------------------------
    def process_folder() -> None:
        if old_primary is not None:
            old_primary.click()

    def run_demo() -> None:
        error_strip.hide()
        if old_demo is not None:
            old_demo.click()

    def show_review() -> None:
        set_advanced_visible(True)
        if old_review is not None:
            old_review.click()

    def select_page(name: str) -> None:
        index = window.page_index.get(name)
        if index is not None:
            window.nav.setCurrentRow(index)

    choose_button.clicked.connect(process_folder)
    demo_button.clicked.connect(run_demo)
    review_findings.clicked.connect(lambda: select_page("Findings"))
    new_mission.clicked.connect(lambda: (setattr(window, "autopilot_last_result", None), home_stack.setCurrentIndex(0)))

    result_path = {"root": None}

    def open_local(path: Path | None) -> None:
        if path is not None and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    open_report.clicked.connect(
        lambda: open_local(result_path["root"] / "report" / "inspection_report.pdf" if result_path["root"] else None)
    )
    open_viewer.clicked.connect(
        lambda: open_local(result_path["root"] / "viewer" / "index.html" if result_path["root"] else None)
    )
    open_folder.clicked.connect(lambda: open_local(result_path["root"]))
    error_dismiss.clicked.connect(error_strip.hide)

    stage_human = {
        "INGEST": ("Reading and organizing mission data…", 12),
        "RADIOMETRY": ("Validating quantitative thermal measurements…", 24),
        "STITCH": ("Building the thermal map…", 40),
        "ANALYZE": ("Detecting and prioritizing thermal anomalies…", 58),
        "AI REVIEW": ("Reviewing evidence with local intelligence…", 70),
        "ANNOTATE": ("Annotating findings and measurements…", 82),
        "PACKAGE": ("Building the engineering and client package…", 93),
        "COMPLETE": ("Finalizing the inspection…", 98),
    }

    preview_cache = {"path": None, "pixmap": None}

    def set_preview(path: Path | None) -> None:
        if path is None or not path.is_file():
            preview_cache["path"] = None
            preview_cache["pixmap"] = None
            visual_image.setPixmap(QPixmap())
            visual_image.setText("Annotated thermal overview is not available for this mission")
            return
        if preview_cache["path"] != path:
            pixmap = QPixmap(str(path))
            preview_cache["path"] = path
            preview_cache["pixmap"] = pixmap if not pixmap.isNull() else None
        pixmap = preview_cache["pixmap"]
        if pixmap is None:
            visual_image.setText("Annotated thermal overview could not be rendered")
            return
        visual_image.setText("")
        target = visual_image.size()
        visual_image.setPixmap(pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def present_result(result) -> None:
        root = Path(result.deliverable_dir)
        result_path["root"] = root
        findings = list(getattr(result.run, "canonical_findings", []) or [])
        counts = Counter(
            getattr(getattr(finding, "severity", None), "value", str(getattr(finding, "severity", ""))).lower()
            for finding in findings
        )
        finding_total.setText(str(len(findings)))
        for severity, label in severity_values.items():
            label.setText(str(counts.get(severity, 0)))
        preview = root / "maps" / "annotated_thermal_overview.png"
        set_preview(preview)
        home_stack.setCurrentWidget(complete_page)
        ambient_state.setText("Inspection ready")
        window.header_status.setText("Inspection ready")

    def show_error(message: str) -> None:
        if not message:
            return
        error_text.setText(message)
        error_strip.show()

    def pipeline_state() -> tuple[str | None, int]:
        if pipeline is None:
            return None, 10
        active = None
        completed = 0
        rows = pipeline.rowCount()
        for row in range(rows):
            stage_item = pipeline.item(row, 0)
            state_item = pipeline.item(row, 2)
            if stage_item is None or state_item is None:
                continue
            stage = stage_item.text().strip().upper()
            state = state_item.text().strip().upper()
            if state == "DONE":
                completed += 1
            elif state == "RUNNING":
                active = stage
        progress = max(10, min(98, int((completed / max(1, rows)) * 100)))
        if active in stage_human:
            progress = max(progress, stage_human[active][1])
        return active, progress

    def update_home() -> None:
        snapshot = getattr(window, "autopilot_snapshot", None)
        if snapshot is not None:
            if getattr(snapshot, "ai_available", False):
                ambient_state.setText("Local AI ready")
                running_ai_value.setText("Local AI available")
            else:
                ambient_state.setText("Deterministic analysis ready")
                running_ai_value.setText("Deterministic fallback ready")

        result = getattr(window, "autopilot_last_result", None)
        if result is not None:
            if home_stack.currentWidget() is not complete_page or result_path["root"] != Path(result.deliverable_dir):
                present_result(result)
            elif preview_cache["pixmap"] is not None:
                set_preview(preview_cache["path"])
            return

        demo_worker = getattr(window, "demo_mission_worker", None)
        intake_worker = getattr(window, "mission_intake_worker", None)
        autopilot_worker = getattr(window, "autopilot_worker", None)

        if demo_worker is not None and demo_worker.isRunning():
            home_stack.setCurrentWidget(running_page)
            running_title.setText("Preparing the guided inspection…")
            running_detail.setText(
                "Creating the small synthetic radiometric learning mission and validating its source contract."
            )
            running_progress.setValue(7)
            running_percent.setText("7%")
            running_source_value.setText("Guided solar mission")
            return

        if intake_worker is not None and intake_worker.isRunning():
            home_stack.setCurrentWidget(running_page)
            running_title.setText("Reading the mission folder…")
            running_detail.setText("Discovering compatible thermal, visible, GIS and context files locally.")
            running_progress.setValue(10)
            running_percent.setText("10%")
            running_source_value.setText("Discovering sources")
            return

        if autopilot_worker is not None and autopilot_worker.isRunning():
            home_stack.setCurrentWidget(running_page)
            stage, percent = pipeline_state()
            title, stage_floor = stage_human.get(
                stage or "",
                ("Processing the thermal inspection…", percent),
            )
            percent = max(percent, stage_floor)
            running_title.setText(title)
            running_detail.setText(
                "Autopilot is handling the post-processing workflow. You can continue navigating the app."
            )
            running_progress.setValue(percent)
            running_percent.setText(f"{percent}%")
            running_source_value.setText(f"{len(session.sources)} source(s) in mission")
            return

        # Mirror a blocking condition from the underlying one-click authority as inline guidance.
        legacy_state = window.findChild(QLabel, "missionState")
        if legacy_state is not None:
            text = legacy_state.text().strip()
            upper = text.upper()
            if any(token in upper for token in ("FAILED", "STOPPED", "NO SUPPORTED", "NEEDS A COMPATIBLE")):
                detail = ""
                parent = legacy_state.parentWidget()
                if parent is not None:
                    labels = parent.findChildren(QLabel)
                    try:
                        position = labels.index(legacy_state)
                    except ValueError:
                        position = -1
                    if position >= 0 and position + 1 < len(labels):
                        detail = labels[position + 1].text().strip()
                show_error(detail or text)

        if home_stack.currentWidget() is running_page:
            home_stack.setCurrentWidget(ready_page)

    # Expose result presentation for visual QA and tests without creating a second processing path.
    window.present_consumer_result = present_result
    window.refresh_consumer_home = update_home
    window.consumer_home_stack = home_stack
    window.consumer_ready_page = ready_page
    window.consumer_running_page = running_page
    window.consumer_complete_page = complete_page

    home_timer = QTimer(window)
    home_timer.setInterval(250)
    home_timer.timeout.connect(update_home)
    home_timer.start()
    window.consumer_home_timer = home_timer

    QTimer.singleShot(50, update_home)
    window.nav.setCurrentRow(window.page_index["Autopilot"])
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
