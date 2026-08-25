from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


def create_workspace_window(session):
    """Create the v0.6 project-centric desktop without entering the Qt event loop."""

    try:
        from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt, QThread, pyqtSignal
        from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
        from PyQt5.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QSlider,
            QSplitter,
            QStackedWidget,
            QTableView,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("Install the desktop extra to launch the Windows UI") from exc

    import sys

    from .. import __version__
    from ..inspections.models import FindingStatus
    from ..inspections.profiles import available_profiles
    from ..platform.config import AppConfig
    from ..reporting.json_report import read_findings_json
    from ..sensors.generic import GenericGeoTiffAdapter
    from ..thermal.calibration import ThermalCalibration
    from .pairing import MediaObservation, pair_thermal_visible
    from .processing import ProcessingHistoryRecord, ProcessingHistoryStore
    from .projects import Project
    from .viewer import (
        align_rgb_pair,
        available_palettes,
        blend_rgb,
        render_temperature,
        roi_statistics,
        swipe_rgb,
        temperature_at,
    )
    from .workspace import ProjectCatalog, finding_details, summarize_workspace

    app = QApplication.instance() or QApplication(sys.argv)
    config = AppConfig.from_env()
    catalog = ProjectCatalog(config.data_dir / "projects")
    history_store = ProcessingHistoryStore.default()

    class RowsModel(QAbstractTableModel):
        def __init__(self, columns):
            super().__init__()
            self.columns = columns
            self.rows = []

        def set_rows(self, rows):
            self.beginResetModel()
            self.rows = list(rows)
            self.endResetModel()

        def rowCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(self.rows)

        def columnCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(self.columns)

        def data(self, index, role=Qt.DisplayRole):
            if not index.isValid() or role not in (Qt.DisplayRole, Qt.ToolTipRole):
                return None
            row = self.rows[index.row()]
            _, key = self.columns[index.column()]
            value = row.get(key, "")
            if isinstance(value, float):
                return f"{value:.2f}"
            return str(value)

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            if role == Qt.DisplayRole and orientation == Qt.Horizontal:
                return self.columns[section][0]
            return super().headerData(section, orientation, role)

        def row(self, index):
            if not index.isValid() or not 0 <= index.row() < len(self.rows):
                return None
            return self.rows[index.row()]

    class ProjectMapCanvas(QFrame):
        def __init__(self):
            super().__init__()
            self.setMinimumHeight(360)
            self.points = []
            self.setToolTip("Projects are plotted only when explicit latitude/longitude metadata exists.")

        def set_projects(self, projects):
            points = []
            for project, path in projects:
                lat = project.metadata.get("latitude")
                lon = project.metadata.get("longitude")
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (TypeError, ValueError):
                    continue
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    points.append((lat, lon, project.name, str(path)))
            self.points = points
            self.update()

        def paintEvent(self, event):
            super().paintEvent(event)
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#0d141c"))
            painter.setPen(QPen(QColor("#526273"), 1))
            for fraction in (0.25, 0.5, 0.75):
                painter.drawLine(0, int(self.height() * fraction), self.width(), int(self.height() * fraction))
                painter.drawLine(int(self.width() * fraction), 0, int(self.width() * fraction), self.height())
            if not self.points:
                painter.setPen(QColor("#9aacbb"))
                painter.drawText(self.rect(), Qt.AlignCenter, "No projects have explicit coordinates")
                return
            lats = [item[0] for item in self.points]
            lons = [item[1] for item in self.points]
            lat_min, lat_max = min(lats), max(lats)
            lon_min, lon_max = min(lons), max(lons)
            lat_span = max(lat_max - lat_min, 0.001)
            lon_span = max(lon_max - lon_min, 0.001)
            for lat, lon, name, _ in self.points:
                x = 24 + (lon - lon_min) / lon_span * max(1, self.width() - 48)
                y = 24 + (lat_max - lat) / lat_span * max(1, self.height() - 48)
                painter.setBrush(QColor("#39a0ed"))
                painter.setPen(QPen(QColor("white"), 1))
                painter.drawEllipse(QPointF(x, y), 6, 6)
                painter.drawText(int(x + 9), int(y + 4), name[:28])

    class RadiometricCanvas(QFrame):
        cursorMoved = pyqtSignal(float, float)
        roiSelected = pyqtSignal(float, float, float, float)

        def __init__(self):
            super().__init__()
            self.setMinimumSize(520, 360)
            self.setMouseTracking(True)
            self.pixmap = None
            self.image_shape = None
            self.drag_start = None
            self.drag_end = None

        def set_rgb(self, rgb):
            array = np.ascontiguousarray(rgb, dtype=np.uint8)
            height, width, _ = array.shape
            image = QImage(array.data, width, height, width * 3, QImage.Format_RGB888).copy()
            self.pixmap = QPixmap.fromImage(image)
            self.image_shape = (height, width)
            self.drag_start = None
            self.drag_end = None
            self.update()

        def clear(self):
            self.pixmap = None
            self.image_shape = None
            self.update()

        def _target(self):
            if self.pixmap is None:
                return None
            scaled = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            return x, y, scaled

        def _source_point(self, point):
            target = self._target()
            if target is None or self.image_shape is None:
                return None
            x0, y0, scaled = target
            if not (x0 <= point.x() < x0 + scaled.width() and y0 <= point.y() < y0 + scaled.height()):
                return None
            height, width = self.image_shape
            x = (point.x() - x0) * width / scaled.width()
            y = (point.y() - y0) * height / scaled.height()
            return x, y

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#080c10"))
            target = self._target()
            if target is None:
                painter.setPen(QColor("#8ea0af"))
                painter.drawText(self.rect(), Qt.AlignCenter, "Select an analyzed radiometric source")
                return
            x0, y0, scaled = target
            painter.drawPixmap(x0, y0, scaled)
            if self.drag_start is not None and self.drag_end is not None:
                painter.setPen(QPen(QColor("#ffffff"), 2, Qt.DashLine))
                painter.drawRect(QRectF(self.drag_start, self.drag_end).normalized())

        def mouseMoveEvent(self, event):
            source = self._source_point(event.pos())
            if source is not None:
                self.cursorMoved.emit(*source)
            if self.drag_start is not None:
                self.drag_end = event.pos()
                self.update()

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton and self._source_point(event.pos()) is not None:
                self.drag_start = event.pos()
                self.drag_end = event.pos()
                self.update()

        def mouseReleaseEvent(self, event):
            if self.drag_start is None:
                return
            start = self._source_point(self.drag_start)
            end = self._source_point(event.pos())
            self.drag_end = event.pos()
            if start is not None and end is not None:
                self.roiSelected.emit(start[0], start[1], end[0], end[1])
            self.update()

    class InspectionWorker(QThread):
        eventRaised = pyqtSignal(object)
        completed = pyqtSignal(object, str)
        failed = pyqtSignal(str)

        def __init__(self, calibration, adapter_name, profile_id):
            super().__init__()
            self.calibration = calibration
            self.adapter_name = adapter_name
            self.profile_id = profile_id
            self.cancelled = False
            self.started_at = datetime.now(UTC).isoformat()

        def cancel(self):
            self.cancelled = True

        def run(self):
            try:
                run = session.analyze_inspection(
                    self.calibration,
                    adapter_name=self.adapter_name,
                    profile_id=self.profile_id,
                    on_event=self.eventRaised.emit,
                    is_cancelled=lambda: self.cancelled,
                )
                self.completed.emit(run, self.started_at)
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    class WorkspaceWindow(QMainWindow):
        NAV_ITEMS = (
            "Projects",
            "Overview",
            "Data",
            "Explore",
            "Analyze",
            "Processing",
            "Findings",
            "Compare",
            "Reports",
            "Exports",
            "Analytics",
            "Profiles",
            "Settings",
        )

        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"UAS Thermal Analysis {__version__} — Thermal Operations")
            self.resize(1520, 920)
            self.worker = None
            self.current_artifact = None
            self.previous_findings = []
            self.visible_pairs = {}
            self.project_rows = []
            self._build()
            self._theme()
            self.refresh_all()

        def _theme(self):
            self.setStyleSheet(
                "QMainWindow,QWidget{background:#10161d;color:#e7edf3;font-size:10pt;}"
                "QFrame#header{background:#18212b;border-bottom:1px solid #2f3b48;}"
                "QListWidget{background:#141c24;border:0;border-right:1px solid #2f3b48;padding:8px;}"
                "QListWidget::item{padding:10px 12px;margin:2px;border-radius:5px;}"
                "QListWidget::item:selected{background:#28415a;color:white;}"
                "QTableView,QTextEdit,QLineEdit,QComboBox{background:#18212b;border:1px solid #354454;border-radius:4px;padding:4px;}"
                "QHeaderView::section{background:#202b36;color:#c9d4de;padding:7px;border:0;border-right:1px solid #354454;}"
                "QGroupBox{border:1px solid #32404e;border-radius:6px;margin-top:10px;padding:10px;}"
                "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}"
                "QPushButton{background:#286fae;border:0;border-radius:4px;padding:8px 12px;font-weight:600;}"
                "QPushButton:hover{background:#3481c1;} QPushButton:disabled{background:#303943;color:#75818c;}"
                "QProgressBar{border:1px solid #354454;border-radius:4px;text-align:center;background:#18212b;}"
                "QProgressBar::chunk{background:#2f82c4;}"
            )

        def _build(self):
            root_widget = QWidget()
            self.setCentralWidget(root_widget)
            root = QVBoxLayout(root_widget)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            header = QFrame(objectName="header")
            header_layout = QHBoxLayout(header)
            title = QLabel("UAS Thermal Analysis")
            title.setStyleSheet("font-size:16pt;font-weight:700;")
            self.project_header = QLabel()
            self.header_status = QLabel("Ready")
            header_layout.addWidget(title)
            header_layout.addSpacing(20)
            header_layout.addWidget(self.project_header)
            header_layout.addStretch(1)
            header_layout.addWidget(self.header_status)
            root.addWidget(header)

            splitter = QSplitter(Qt.Horizontal)
            self.nav = QListWidget()
            self.nav.setMinimumWidth(165)
            self.nav.setMaximumWidth(190)
            for item in self.NAV_ITEMS:
                self.nav.addItem(QListWidgetItem(item))
            splitter.addWidget(self.nav)
            self.pages = QStackedWidget()
            self.page_index = {}
            splitter.addWidget(self.pages)
            self.inspector = QTextEdit()
            self.inspector.setReadOnly(True)
            self.inspector.setMinimumWidth(260)
            self.inspector.setMaximumWidth(360)
            splitter.addWidget(self.inspector)
            splitter.setStretchFactor(1, 1)
            root.addWidget(splitter, 1)
            self.footer = QLabel("Ready")
            self.footer.setContentsMargins(10, 5, 10, 5)
            root.addWidget(self.footer)
            self._pages()
            self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
            self.nav.setCurrentRow(1)

        def _page(self, name, title, subtitle):
            page = QWidget()
            layout = QVBoxLayout(page)
            heading = QLabel(title)
            heading.setStyleSheet("font-size:18pt;font-weight:700;")
            description = QLabel(subtitle)
            description.setWordWrap(True)
            description.setStyleSheet("color:#94a6b5;")
            layout.addWidget(heading)
            layout.addWidget(description)
            self.page_index[name] = self.pages.count()
            self.pages.addWidget(page)
            return layout

        def _pages(self):
            self._projects_page()
            self._overview_page()
            self._data_page()
            self._explore_page()
            self._analyze_page()
            self._processing_page()
            self._findings_page()
            self._compare_page()
            self._reports_page()
            self._exports_page()
            self._analytics_page()
            self._profiles_page()
            self._settings_page()

        def _projects_page(self):
            layout = self._page("Projects", "Projects", "Search and open the local inspection portfolio. Location view uses only explicit project coordinates.")
            controls = QHBoxLayout()
            self.project_search = QLineEdit()
            self.project_search.setPlaceholderText("Search name, site, client, location, tag…")
            self.project_view_mode = QComboBox()
            self.project_view_mode.addItems(["List", "Locations"])
            new_btn = QPushButton("New")
            open_btn = QPushButton("Open selected")
            save_btn = QPushButton("Save current")
            controls.addWidget(self.project_search, 1)
            controls.addWidget(self.project_view_mode)
            controls.addWidget(new_btn)
            controls.addWidget(open_btn)
            controls.addWidget(save_btn)
            layout.addLayout(controls)
            self.project_stack = QStackedWidget()
            self.project_model = RowsModel(
                [("Project", "name"), ("Client", "client"), ("Site", "site"), ("Profile", "profile"), ("Modified", "modified")]
            )
            self.project_table = QTableView()
            self.project_table.setModel(self.project_model)
            self.project_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self.project_table.setSortingEnabled(False)
            self.project_map = ProjectMapCanvas()
            self.project_stack.addWidget(self.project_table)
            self.project_stack.addWidget(self.project_map)
            layout.addWidget(self.project_stack, 1)
            form = QGroupBox("Current project")
            form_layout = QFormLayout(form)
            self.project_name = QLineEdit()
            self.project_client = QLineEdit()
            self.project_site = QLineEdit()
            self.project_location = QLineEdit()
            self.project_operator = QLineEdit()
            self.project_asset = QLineEdit()
            for label, widget in (
                ("Name", self.project_name),
                ("Client", self.project_client),
                ("Site", self.project_site),
                ("Location", self.project_location),
                ("Operator", self.project_operator),
                ("Asset", self.project_asset),
            ):
                form_layout.addRow(label, widget)
            layout.addWidget(form)
            self.project_search.textChanged.connect(self.refresh_projects)
            self.project_view_mode.currentIndexChanged.connect(self.project_stack.setCurrentIndex)
            new_btn.clicked.connect(self.new_project)
            save_btn.clicked.connect(self.save_project)
            open_btn.clicked.connect(self.open_selected_project)
            self.project_table.doubleClicked.connect(lambda _: self.open_selected_project())

        def _overview_page(self):
            layout = self._page("Overview", "Project Overview", "Data health, current findings, processing state, and next actions.")
            self.overview = QLabel()
            self.overview.setWordWrap(True)
            self.overview.setStyleSheet("font-size:12pt;")
            layout.addWidget(self.overview)
            run_btn = QPushButton("Analyze Inspection")
            run_btn.clicked.connect(lambda: self.nav.setCurrentRow(self.page_index["Analyze"]))
            layout.addWidget(run_btn, 0, Qt.AlignLeft)
            layout.addStretch(1)

        def _data_page(self):
            layout = self._page("Data", "Data", "Virtualized source inventory. Removing a row never deletes the source file.")
            actions = QHBoxLayout()
            add_btn = QPushButton("Add Data")
            remove_btn = QPushButton("Remove from Project")
            validate_btn = QPushButton("Validate / Classify")
            actions.addWidget(add_btn)
            actions.addWidget(validate_btn)
            actions.addWidget(remove_btn)
            actions.addStretch(1)
            layout.addLayout(actions)
            self.data_model = RowsModel(
                [("Source", "source"), ("Type", "type"), ("Radiometric", "radiometric"), ("Size", "size"), ("State", "state")]
            )
            self.data_table = QTableView()
            self.data_table.setModel(self.data_model)
            self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            layout.addWidget(self.data_table, 1)
            add_btn.clicked.connect(self.add_data)
            remove_btn.clicked.connect(self.remove_data)
            validate_btn.clicked.connect(self.validate_data)
            self.data_table.doubleClicked.connect(self.open_data_row)

        def _explore_page(self):
            layout = self._page("Explore", "Radiometric Viewer", "Temperature-under-cursor, ROI statistics, palettes, isotherms, and explicit thermal/visible review.")
            toolbar = QHBoxLayout()
            self.viewer_source = QComboBox()
            self.palette = QComboBox()
            self.palette.addItems(list(available_palettes()))
            self.range_min = QLineEdit()
            self.range_min.setPlaceholderText("Auto min")
            self.range_max = QLineEdit()
            self.range_max.setPlaceholderText("Auto max")
            self.isotherm = QLineEdit()
            self.isotherm.setPlaceholderText("Isotherm ≥ °C")
            pair_btn = QPushButton("Pair Visible…")
            toolbar.addWidget(self.viewer_source, 1)
            toolbar.addWidget(self.palette)
            toolbar.addWidget(self.range_min)
            toolbar.addWidget(self.range_max)
            toolbar.addWidget(self.isotherm)
            toolbar.addWidget(pair_btn)
            layout.addLayout(toolbar)
            self.radiometric_canvas = RadiometricCanvas()
            layout.addWidget(self.radiometric_canvas, 1)
            metrics = QHBoxLayout()
            self.cursor_temperature = QLabel("Cursor: —")
            self.roi_label = QLabel("ROI: drag on image")
            metrics.addWidget(self.cursor_temperature)
            metrics.addSpacing(30)
            metrics.addWidget(self.roi_label, 1)
            layout.addLayout(metrics)
            self.viewer_source.currentIndexChanged.connect(self.select_viewer_source)
            self.palette.currentTextChanged.connect(self.render_current_artifact)
            self.range_min.editingFinished.connect(self.render_current_artifact)
            self.range_max.editingFinished.connect(self.render_current_artifact)
            self.isotherm.editingFinished.connect(self.render_current_artifact)
            self.radiometric_canvas.cursorMoved.connect(self.on_temperature_cursor)
            self.radiometric_canvas.roiSelected.connect(self.on_roi)
            pair_btn.clicked.connect(self.pair_visible)

        def _analyze_page(self):
            layout = self._page("Analyze", "Analyze Inspection", "Canonical radiometric quality gate → contextual detection → geolocation → deduplication pipeline.")
            form_box = QGroupBox("Configuration")
            form = QFormLayout(form_box)
            self.profile_combo = QComboBox()
            for profile in available_profiles():
                self.profile_combo.addItem(profile.name, profile.profile_id)
            self.adapter_combo = QComboBox()
            self.adapter_combo.addItem("Auto detect", None)
            for adapter in session.workflow.registry.adapters:
                self.adapter_combo.addItem(f"{adapter.vendor} — {adapter.name}", adapter.name)
            self.emissivity = QLineEdit("0.95")
            self.distance = QLineEdit("5.0")
            self.humidity = QLineEdit("0.50")
            self.reflected = QLineEdit("20.0")
            for label, widget in (
                ("Profile", self.profile_combo),
                ("Adapter", self.adapter_combo),
                ("Emissivity", self.emissivity),
                ("Distance (m)", self.distance),
                ("Humidity", self.humidity),
                ("Reflected temp (°C)", self.reflected),
            ):
                form.addRow(label, widget)
            layout.addWidget(form_box)
            actions = QHBoxLayout()
            self.run_button = QPushButton("Analyze Inspection")
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.setEnabled(False)
            actions.addWidget(self.run_button)
            actions.addWidget(self.cancel_button)
            actions.addStretch(1)
            layout.addLayout(actions)
            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.processing_log = QTextEdit()
            self.processing_log.setReadOnly(True)
            layout.addWidget(self.progress)
            layout.addWidget(self.processing_log, 1)
            self.run_button.clicked.connect(self.start_analysis)
            self.cancel_button.clicked.connect(self.cancel_analysis)

        def _processing_page(self):
            layout = self._page("Processing", "Processing Center", "Persistent run history, terminal state, warnings, failures, and output-package provenance.")
            refresh_btn = QPushButton("Refresh History")
            refresh_btn.clicked.connect(self.refresh_processing_history)
            layout.addWidget(refresh_btn, 0, Qt.AlignLeft)
            self.history_model = RowsModel(
                [("Finished", "finished"), ("Project", "project"), ("Status", "status"), ("Sources", "sources"), ("Rejected", "rejected"), ("Findings", "findings"), ("Critical", "critical")]
            )
            self.history_table = QTableView()
            self.history_table.setModel(self.history_model)
            self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.history_table.clicked.connect(self.inspect_history)
            layout.addWidget(self.history_table, 1)

        def _findings_page(self):
            layout = self._page("Findings", "Findings", "Virtualized canonical finding register with severity, confidence, ΔT, provenance, and lifecycle state.")
            self.finding_model = RowsModel(
                [("ID", "id"), ("Class", "class"), ("Severity", "severity"), ("Confidence", "confidence"), ("Max °C", "max"), ("ΔT °C", "delta"), ("Status", "status"), ("Source", "source")]
            )
            self.finding_table = QTableView()
            self.finding_table.setModel(self.finding_model)
            self.finding_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.finding_table.clicked.connect(self.inspect_finding)
            layout.addWidget(self.finding_table, 1)
            status_bar = QHBoxLayout()
            self.finding_status = QComboBox()
            for status in FindingStatus:
                self.finding_status.addItem(status.value.replace("_", " ").title(), status)
            apply_btn = QPushButton("Apply Status")
            status_bar.addWidget(QLabel("Lifecycle"))
            status_bar.addWidget(self.finding_status)
            status_bar.addWidget(apply_btn)
            status_bar.addStretch(1)
            layout.addLayout(status_bar)
            apply_btn.clicked.connect(self.apply_finding_status)

        def _compare_page(self):
            layout = self._page("Compare", "Compare", "Thermal↔visible opacity/swipe review and previous-inspection finding comparison.")
            actions = QHBoxLayout()
            self.compare_source = QComboBox()
            self.compare_mode = QComboBox()
            self.compare_mode.addItems(["Opacity", "Swipe", "Side by side"])
            self.compare_slider = QSlider(Qt.Horizontal)
            self.compare_slider.setRange(0, 100)
            self.compare_slider.setValue(50)
            previous_btn = QPushButton("Load Previous Findings…")
            actions.addWidget(self.compare_source, 1)
            actions.addWidget(self.compare_mode)
            actions.addWidget(self.compare_slider, 1)
            actions.addWidget(previous_btn)
            layout.addLayout(actions)
            self.compare_canvas = RadiometricCanvas()
            layout.addWidget(self.compare_canvas, 1)
            self.compare_summary = QTextEdit()
            self.compare_summary.setReadOnly(True)
            self.compare_summary.setMaximumHeight(150)
            layout.addWidget(self.compare_summary)
            self.compare_source.currentIndexChanged.connect(self.render_compare)
            self.compare_mode.currentTextChanged.connect(self.render_compare)
            self.compare_slider.valueChanged.connect(self.render_compare)
            previous_btn.clicked.connect(self.load_previous_findings)

        def _reports_page(self):
            layout = self._page("Reports", "Reports", "Generate deterministic inspection packages and per-source report bundles.")
            package_btn = QPushButton("Generate Inspection Package…")
            bundle_btn = QPushButton("Export Per-source Reports…")
            layout.addWidget(package_btn, 0, Qt.AlignLeft)
            layout.addWidget(bundle_btn, 0, Qt.AlignLeft)
            self.report_status = QTextEdit()
            self.report_status.setReadOnly(True)
            layout.addWidget(self.report_status, 1)
            package_btn.clicked.connect(self.export_package)
            bundle_btn.clicked.connect(self.export_reports)

        def _exports_page(self):
            layout = self._page("Exports", "Exports", "Project output history recorded by the workspace.")
            self.exports_text = QTextEdit()
            self.exports_text.setReadOnly(True)
            layout.addWidget(self.exports_text, 1)

        def _analytics_page(self):
            layout = self._page("Analytics", "Analytics", "Portfolio and project-level operational metrics.")
            self.analytics = QLabel()
            self.analytics.setWordWrap(True)
            self.analytics.setStyleSheet("font-size:12pt;")
            layout.addWidget(self.analytics)
            layout.addStretch(1)

        def _profiles_page(self):
            layout = self._page("Profiles", "Inspection Profiles", "Versioned domain-specific detection and severity policies.")
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n\n".join(f"{profile.name} ({profile.profile_id}) v{profile.version}" for profile in available_profiles()))
            layout.addWidget(text, 1)

        def _settings_page(self):
            layout = self._page("Settings", "Settings", "Local application paths and runtime boundaries.")
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText(
                f"Version: {__version__}\nData directory: {config.data_dir}\n"
                f"DJI SDK directory: {config.dji_sdk_dir or 'not configured'}\n\n"
                "Customer datasets and vendor SDK binaries remain outside source control."
            )
            layout.addWidget(text, 1)

        def _sync_project_form(self):
            session.project.name = self.project_name.text().strip() or "Untitled inspection"
            session.project.client = self.project_client.text().strip()
            session.project.site = self.project_site.text().strip()
            session.project.location = self.project_location.text().strip()
            session.project.operator = self.project_operator.text().strip()
            session.project.asset_type = self.project_asset.text().strip()

        def _load_project_form(self):
            project = session.project
            self.project_name.setText(project.name)
            self.project_client.setText(project.client)
            self.project_site.setText(project.site)
            self.project_location.setText(project.location)
            self.project_operator.setText(project.operator)
            self.project_asset.setText(project.asset_type)
            index = self.profile_combo.findData(project.profile_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

        def new_project(self):
            session.project = Project(name="Untitled inspection")
            session.set_sources([])
            self.current_artifact = None
            self._load_project_form()
            self.refresh_all()

        def save_project(self):
            self._sync_project_form()
            path = catalog.save(session.project)
            self.footer.setText(f"Saved {path}")
            self.refresh_projects()

        def refresh_projects(self):
            projects = catalog.search(self.project_search.text())
            self.project_rows = projects
            rows = [
                {
                    "name": project.name,
                    "client": project.client,
                    "site": project.site,
                    "profile": project.profile_id,
                    "modified": project.modified_at,
                    "path": str(path),
                }
                for project, path in projects
            ]
            self.project_model.set_rows(rows)
            self.project_map.set_projects(projects)

        def open_selected_project(self):
            index = self.project_table.currentIndex()
            row = self.project_model.row(index)
            if row is None:
                return
            try:
                session.project = Project.load(row["path"])
            except Exception as exc:
                QMessageBox.critical(self, "Open Project", str(exc))
                return
            sources = [path for dataset in session.project.datasets for path in dataset.source_paths]
            session.set_sources(sources)
            self.current_artifact = None
            self._load_project_form()
            self.refresh_all()

        def add_data(self):
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Add thermal, visible, or geospatial data",
                "",
                "Imagery (*.tif *.tiff *.jpg *.jpeg *.png);;All files (*)",
            )
            if not paths:
                return
            existing = [str(path) for path in session.sources]
            new_paths = [path for path in paths if path not in existing]
            if not new_paths:
                return
            session.project.add_dataset(new_paths)
            session.set_sources([*existing, *new_paths])
            self.refresh_all()

        def remove_data(self):
            row = self.data_model.row(self.data_table.currentIndex())
            if row is None:
                return
            source = row["path"]
            for dataset in session.project.datasets:
                dataset.source_paths = [item for item in dataset.source_paths if item != source]
                dataset.image_count = len(dataset.source_paths)
            session.project.datasets = [item for item in session.project.datasets if item.source_paths]
            session.set_sources([item for item in session.sources if str(item) != source])
            self.refresh_all()

        def validate_data(self):
            row = self.data_model.row(self.data_table.currentIndex())
            if row is None:
                return
            path = Path(row["path"])
            if path.suffix.lower() in {".tif", ".tiff"}:
                try:
                    diagnostics = GenericGeoTiffAdapter().source_diagnostics(path)
                    message = "Radiometric candidate" if diagnostics["radiometric_candidate"] else "Display/GIS only"
                    message += f"\n{diagnostics.get('radiometric_reasons') or []}"
                except Exception as exc:
                    message = str(exc)
            else:
                message = "Native image candidate. Quantitative status is established only by a compatible radiometric decoder."
            self.inspector.setPlainText(message)

        def open_data_row(self, index):
            row = self.data_model.row(index)
            if row is None:
                return
            source = row["path"]
            viewer_index = self.viewer_source.findData(source)
            if viewer_index >= 0:
                self.viewer_source.setCurrentIndex(viewer_index)
                self.nav.setCurrentRow(self.page_index["Explore"])

        def _calibration(self):
            return ThermalCalibration(
                emissivity=float(self.emissivity.text()),
                distance_m=float(self.distance.text()),
                relative_humidity=float(self.humidity.text()),
                reflected_temperature_c=float(self.reflected.text()),
            )

        def start_analysis(self):
            try:
                self._sync_project_form()
                calibration = self._calibration()
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid calibration", str(exc))
                return
            if not session.sources:
                QMessageBox.warning(self, "Analyze", "Add at least one source first.")
                return
            self.processing_log.clear()
            self.progress.setValue(0)
            self.run_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.worker = InspectionWorker(
                calibration,
                self.adapter_combo.currentData(),
                self.profile_combo.currentData(),
            )
            self.worker.eventRaised.connect(self.on_processing_event)
            self.worker.completed.connect(self.on_analysis_complete)
            self.worker.failed.connect(self.on_analysis_failed)
            self.worker.start()

        def cancel_analysis(self):
            if self.worker is not None:
                self.worker.cancel()
                self.header_status.setText("Cancellation requested")

        def on_processing_event(self, event):
            self.processing_log.append(f"{event.stage.value}: {event.message}")
            if event.total:
                self.progress.setValue(int(round(event.completed / event.total * 100)))
            self.header_status.setText(event.stage.value.replace("_", " ").title())

        def on_analysis_complete(self, run, started_at):
            record = ProcessingHistoryRecord.from_run(run, started_at=started_at)
            history_store.save(record)
            self.run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress.setValue(100 if record.status == "complete" else self.progress.value())
            self.header_status.setText(record.status.replace("_", " ").title())
            self.current_artifact = run.artifacts[0] if run.artifacts else None
            self.refresh_all()
            self.nav.setCurrentRow(self.page_index["Findings"])

        def on_analysis_failed(self, message):
            self.run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.header_status.setText("Failed")
            self.processing_log.append(message)
            QMessageBox.critical(self, "Analysis failed", message)

        def refresh_processing_history(self):
            records = history_store.list_records(limit=500)
            self.history_model.set_rows(
                [
                    {
                        "finished": item.finished_at,
                        "project": item.project_name,
                        "status": item.status,
                        "sources": item.source_count,
                        "rejected": item.rejected_sources,
                        "findings": item.canonical_findings,
                        "critical": item.critical_findings,
                        "run_id": item.run_id,
                    }
                    for item in records
                ]
            )

        def inspect_history(self, index):
            row = self.history_model.row(index)
            if row is None:
                return
            record = history_store.get(row["run_id"])
            if record is not None:
                self.inspector.setPlainText(
                    "\n".join(
                        [
                            f"Run: {record.run_id}",
                            f"Status: {record.status}",
                            f"Started: {record.started_at}",
                            f"Finished: {record.finished_at}",
                            f"Sources: {record.source_count}",
                            f"Rejected: {record.rejected_sources}",
                            f"Findings: {record.canonical_findings}",
                            f"Package: {record.package_dir or 'not generated'}",
                            "",
                            *[f"{event['stage']}: {event['message']}" for event in record.events],
                        ]
                    )
                )

        def refresh_data(self):
            rows = []
            for dataset in session.project.datasets:
                for source in dataset.source_paths:
                    path = Path(source)
                    rows.append(
                        {
                            "source": path.name,
                            "type": dataset.data_type,
                            "radiometric": dataset.radiometric_status,
                            "size": path.stat().st_size if path.is_file() else 0,
                            "state": dataset.analysis_state,
                            "path": str(path),
                        }
                    )
            self.data_model.set_rows(rows)

        def refresh_findings(self):
            findings = session.last_run.canonical_findings if session.last_run else []
            self.finding_model.set_rows(
                [
                    {
                        "id": item.finding_id,
                        "class": item.classification,
                        "severity": item.severity.value,
                        "confidence": item.confidence.value,
                        "max": item.max_temperature_c,
                        "delta": item.delta_temperature_c,
                        "status": item.lifecycle_status.value,
                        "source": Path(item.source_path).name,
                        "object": item,
                    }
                    for item in findings
                ]
            )

        def inspect_finding(self, index):
            row = self.finding_model.row(index)
            if row is None:
                return
            finding = row["object"]
            self.inspector.setPlainText("\n".join(f"{key}: {value}" for key, value in finding_details(finding).items()))
            viewer_index = self.viewer_source.findData(finding.source_path)
            if viewer_index >= 0:
                self.viewer_source.setCurrentIndex(viewer_index)

        def apply_finding_status(self):
            row = self.finding_model.row(self.finding_table.currentIndex())
            if row is None:
                return
            finding = row["object"]
            finding.lifecycle_status = self.finding_status.currentData()
            finding.updated_at = datetime.now(UTC).isoformat()
            finding.audit_trail.append({"at": finding.updated_at, "event": "status_changed", "status": finding.lifecycle_status.value})
            self.refresh_findings()

        def _artifact_for_source(self, source):
            for artifact in session.artifacts:
                if artifact.result.source == source:
                    return artifact
            return None

        def refresh_viewer_sources(self):
            current = self.viewer_source.currentData()
            self.viewer_source.blockSignals(True)
            self.viewer_source.clear()
            self.compare_source.clear()
            for artifact in session.artifacts:
                source = artifact.result.source
                label = Path(source).name
                self.viewer_source.addItem(label, source)
                self.compare_source.addItem(label, source)
            self.viewer_source.blockSignals(False)
            if current:
                index = self.viewer_source.findData(current)
                if index >= 0:
                    self.viewer_source.setCurrentIndex(index)
            self.select_viewer_source()

        def select_viewer_source(self):
            source = self.viewer_source.currentData()
            self.current_artifact = self._artifact_for_source(source) if source else None
            self.render_current_artifact()

        def _float_or_none(self, widget):
            text = widget.text().strip()
            return None if not text else float(text)

        def render_current_artifact(self):
            if self.current_artifact is None:
                self.radiometric_canvas.clear()
                return
            try:
                rgb, limits = render_temperature(
                    self.current_artifact.frame.temperature_c,
                    palette=self.palette.currentText(),
                    minimum_c=self._float_or_none(self.range_min),
                    maximum_c=self._float_or_none(self.range_max),
                    isotherm_min_c=self._float_or_none(self.isotherm),
                )
            except ValueError as exc:
                self.footer.setText(str(exc))
                return
            self.radiometric_canvas.set_rgb(rgb)
            self.footer.setText(f"Viewer range {limits[0]:.1f}–{limits[1]:.1f} °C")

        def on_temperature_cursor(self, x, y):
            if self.current_artifact is None:
                return
            value = temperature_at(self.current_artifact.frame.temperature_c, int(x), int(y))
            qualifier = "preview " if self.current_artifact.frame.metadata.get("preview_only") else ""
            self.cursor_temperature.setText(
                "Cursor: —" if value is None else f"Cursor: {qualifier}{value:.2f} °C @ ({int(x)}, {int(y)})"
            )

        def on_roi(self, x0, y0, x1, y1):
            if self.current_artifact is None:
                return
            try:
                stats = roi_statistics(self.current_artifact.frame.temperature_c, int(x0), int(y0), int(x1), int(y1))
            except ValueError as exc:
                self.roi_label.setText(str(exc))
                return
            qualifier = "preview " if self.current_artifact.frame.metadata.get("preview_only") else ""
            self.roi_label.setText(
                f"ROI {qualifier}n={stats.valid_pixels:,} · min {stats.minimum_c:.1f} · mean {stats.mean_c:.1f} · max {stats.maximum_c:.1f} °C"
            )

        def pair_visible(self):
            source = self.viewer_source.currentData()
            if not source:
                return
            path, _ = QFileDialog.getOpenFileName(self, "Select visible image explicitly paired with this thermal source", "", "Images (*.jpg *.jpeg *.png *.tif *.tiff)")
            if not path:
                return
            self.visible_pairs[source] = path
            self.footer.setText(f"Explicit visible pair: {Path(path).name}")
            self.render_compare()

        def _read_visible(self, path):
            try:
                from PIL import Image
            except ImportError as exc:
                raise RuntimeError("Install the reporting extra to review visible imagery") from exc
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((1600, 1200))
                return np.asarray(image, dtype=np.uint8)

        def render_compare(self):
            source = self.compare_source.currentData()
            artifact = self._artifact_for_source(source) if source else None
            if artifact is None:
                self.compare_canvas.clear()
                return
            visible_path = self.visible_pairs.get(source)
            if not visible_path:
                self.compare_canvas.set_rgb(artifact.frame.display_rgb if artifact.frame.display_rgb is not None else render_temperature(artifact.frame.temperature_c)[0])
                self.compare_summary.setPlainText("Pair a visible image from Explore for thermal↔visible comparison.")
                return
            try:
                thermal = render_temperature(artifact.frame.temperature_c, palette=self.palette.currentText())[0]
                visible = self._read_visible(visible_path)
                thermal, visible = align_rgb_pair(thermal, visible)
                fraction = self.compare_slider.value() / 100.0
                mode = self.compare_mode.currentText()
                if mode == "Opacity":
                    output = blend_rgb(thermal, visible, fraction)
                elif mode == "Swipe":
                    output = swipe_rgb(thermal, visible, fraction)
                else:
                    output = np.concatenate([thermal, visible], axis=1)
                self.compare_canvas.set_rgb(output)
                self.compare_summary.setPlainText(
                    f"Thermal: {Path(source).name}\nVisible: {Path(visible_path).name}\nPairing authority: explicit user selection"
                )
            except Exception as exc:
                self.compare_summary.setPlainText(str(exc))

        def load_previous_findings(self):
            path, _ = QFileDialog.getOpenFileName(self, "Load previous findings JSON", "", "JSON (*.json)")
            if not path:
                return
            try:
                payload = read_findings_json(path)
                self.previous_findings = payload["findings"]
                from ..inspections.comparison import compare_finding_sets
                current = session.last_run.canonical_findings if session.last_run else []
                changes = compare_finding_sets(self.previous_findings, current)
                self.compare_summary.setPlainText("\n".join(f"{item.state.value}: {item.previous_id or '—'} → {item.current_id or '—'}" for item in changes))
            except Exception as exc:
                QMessageBox.critical(self, "Compare", str(exc))

        def export_package(self):
            output = QFileDialog.getExistingDirectory(self, "Inspection package destination")
            if not output:
                return
            try:
                destination = session.export_package(output)
                session.project.exports.append({"type": "inspection-package", "path": str(destination), "created_at": datetime.now(UTC).isoformat()})
                self.report_status.append(str(destination))
                self.refresh_exports()
            except Exception as exc:
                QMessageBox.critical(self, "Export", str(exc))

        def export_reports(self):
            output = QFileDialog.getExistingDirectory(self, "Report destination")
            if not output:
                return
            try:
                bundles = session.export(output)
                for bundle in bundles:
                    session.project.exports.append({"type": "report-bundle", "path": str(bundle.csv.parent), "created_at": datetime.now(UTC).isoformat()})
                self.report_status.append(f"Created {len(bundles)} report bundle(s) in {output}")
                self.refresh_exports()
            except Exception as exc:
                QMessageBox.critical(self, "Export", str(exc))

        def refresh_exports(self):
            self.exports_text.setPlainText("\n".join(f"{item.get('created_at', '')} · {item.get('type', '')} · {item.get('path', '')}" for item in session.project.exports) or "No exports recorded in this project.")

        def refresh_analytics(self):
            projects = [item[0] for item in catalog.list_projects()]
            findings = session.last_run.canonical_findings if session.last_run else []
            snapshot = summarize_workspace(projects or [session.project], findings, rejected_sources=len(session.last_run.failures) if session.last_run else 0)
            self.analytics.setText(
                f"Projects: {snapshot.projects}\nDatasets: {snapshot.datasets}\nFindings in current run: {snapshot.findings}\nCritical: {snapshot.critical_findings}\nAction required: {snapshot.action_required}\nRejected sources: {snapshot.rejected_sources}"
            )

        def refresh_all(self):
            self._load_project_form()
            self.project_header.setText(f"{session.project.name} · {session.project.site or 'No site'}")
            self.refresh_projects()
            self.refresh_data()
            self.refresh_findings()
            self.refresh_processing_history()
            self.refresh_viewer_sources()
            self.refresh_exports()
            self.refresh_analytics()
            findings = session.last_run.canonical_findings if session.last_run else []
            rejected = len(session.last_run.failures) if session.last_run else 0
            self.overview.setText(
                f"Datasets: {len(session.project.datasets)}\nSources: {len(session.sources)}\nCanonical findings: {len(findings)}\nRejected sources: {rejected}\nProfile: {session.project.profile_id}"
            )

    window = WorkspaceWindow()
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
