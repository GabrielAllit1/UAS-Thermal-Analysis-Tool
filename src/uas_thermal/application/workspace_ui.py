from __future__ import annotations

from pathlib import Path


def launch_workspace(session) -> int:
    """Launch the project-centric thermal operations workspace.

    Qt is imported lazily so headless analysis, CLI, and CI do not require a desktop runtime.
    """

    try:
        from PyQt5.QtCore import QThread, Qt, pyqtSignal
        from PyQt5.QtGui import QImage, QPainter, QPen, QPixmap
        from PyQt5.QtWidgets import (
            QApplication,
            QCheckBox,
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
            QSplitter,
            QStackedWidget,
            QTableWidget,
            QTableWidgetItem,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("Install the desktop extra to launch the Windows UI") from exc

    import sys

    from ..geospatial.display import read_display_raster
    from ..geospatial.overlays import finding_to_display_point
    from ..inspections.comparison import compare_finding_sets
    from ..inspections.models import FindingStatus
    from ..inspections.profiles import available_profiles
    from ..reporting.json_report import read_findings_json
    from ..sensors.generic import GenericGeoTiffAdapter
    from ..thermal.calibration import ThermalCalibration
    from .projects import Project
    from .workspace import SelectionState, finding_details, summarize_workspace

    severity_color = {
        "critical": "#dc2626",
        "moderate": "#ea8a00",
        "minor": "#eab308",
    }

    class RasterCanvas(QLabel):
        clicked = pyqtSignal(float, float)

        def __init__(self):
            super().__init__("No geospatial layer selected")
            self.setAlignment(Qt.AlignCenter)
            self.setMinimumSize(600, 420)
            self.setFrameShape(QFrame.StyledPanel)
            self._image = None
            self._points = []
            self._source_size = None

        def set_rgb(self, rgb, points=None):
            height, width, _ = rgb.shape
            image = QImage(rgb.data, width, height, width * 3, QImage.Format_RGB888).copy()
            self._image = QPixmap.fromImage(image)
            self._source_size = (width, height)
            self._points = points or []
            self.update()

        def clear_raster(self, message="No geospatial layer selected"):
            self._image = None
            self._source_size = None
            self._points = []
            self.setText(message)
            self.update()

        def _target_rect(self):
            if self._image is None:
                return None
            scaled = self._image.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            return x, y, scaled

        def paintEvent(self, event):
            if self._image is None:
                super().paintEvent(event)
                return
            painter = QPainter(self)
            target = self._target_rect()
            if target is None:
                return
            x0, y0, scaled = target
            painter.drawPixmap(x0, y0, scaled)
            source_w, source_h = self._source_size
            sx = scaled.width() / source_w
            sy = scaled.height() / source_h
            for point in self._points:
                x = x0 + point.x * sx
                y = y0 + point.y * sy
                color = severity_color.get(point.severity, "#38bdf8")
                painter.setPen(QPen(Qt.white, 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(int(x) - 7, int(y) - 7, 14, 14)
                painter.setPen(QPen(__import__("PyQt5.QtGui", fromlist=["QColor"]).QColor(color), 4))
                painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
            painter.end()

        def mousePressEvent(self, event):
            target = self._target_rect()
            if target is None or self._source_size is None:
                return super().mousePressEvent(event)
            x0, y0, scaled = target
            if not (x0 <= event.x() < x0 + scaled.width() and y0 <= event.y() < y0 + scaled.height()):
                return
            source_w, source_h = self._source_size
            x = (event.x() - x0) * source_w / scaled.width()
            y = (event.y() - y0) * source_h / scaled.height()
            self.clicked.emit(x, y)

    class InspectionWorker(QThread):
        event = pyqtSignal(object)
        completed = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, calibration, adapter_name, profile_id):
            super().__init__()
            self.calibration = calibration
            self.adapter_name = adapter_name
            self.profile_id = profile_id
            self._cancelled = False

        def cancel(self):
            self._cancelled = True

        def run(self):
            try:
                run = session.analyze_inspection(
                    self.calibration,
                    adapter_name=self.adapter_name,
                    profile_id=self.profile_id,
                    on_event=self.event.emit,
                    is_cancelled=lambda: self._cancelled,
                )
                self.completed.emit(run)
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    class WorkspaceWindow(QMainWindow):
        NAV_ITEMS = (
            "Projects",
            "Overview",
            "Data",
            "Explore",
            "Analyze",
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
            self.setWindowTitle("UAS Thermal Analysis — Thermal Intelligence Workspace")
            self.resize(1520, 920)
            self.selection = SelectionState()
            self.display_raster = None
            self.worker = None
            self.previous_findings = []
            self._build_shell()
            self._apply_theme()
            self.refresh_all()

        def _apply_theme(self):
            self.setStyleSheet(
                "QMainWindow,QWidget{background:#11161c;color:#e8edf2;font-size:10pt;}"
                "QFrame#header{background:#18202a;border-bottom:1px solid #2d3845;}"
                "QListWidget{background:#151c24;border:0;border-right:1px solid #2d3845;padding:8px;}"
                "QListWidget::item{padding:10px 12px;margin:2px;border-radius:5px;}"
                "QListWidget::item:selected{background:#26394d;color:#fff;}"
                "QGroupBox{border:1px solid #303c49;border-radius:6px;margin-top:10px;padding:10px;}"
                "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;color:#aebdca;}"
                "QLineEdit,QComboBox,QTextEdit,QTableWidget{background:#18202a;border:1px solid #344250;border-radius:4px;padding:5px;}"
                "QHeaderView::section{background:#202a35;color:#cbd5df;padding:7px;border:0;border-right:1px solid #344250;}"
                "QPushButton{background:#276aa8;border:0;border-radius:4px;padding:8px 13px;font-weight:600;}"
                "QPushButton:hover{background:#327ab9;} QPushButton:disabled{background:#303943;color:#72808c;}"
                "QProgressBar{border:1px solid #344250;border-radius:4px;text-align:center;background:#18202a;}"
                "QProgressBar::chunk{background:#2f7fbf;}"
            )

        def _build_shell(self):
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
            self.project_header.setStyleSheet("color:#9fb0bf;")
            header_layout.addWidget(title)
            header_layout.addSpacing(22)
            header_layout.addWidget(self.project_header)
            header_layout.addStretch(1)
            self.header_status = QLabel("Ready")
            header_layout.addWidget(self.header_status)
            root.addWidget(header)

            splitter = QSplitter(Qt.Horizontal)
            self.nav = QListWidget()
            self.nav.setMaximumWidth(190)
            self.nav.setMinimumWidth(165)
            for name in self.NAV_ITEMS:
                self.nav.addItem(QListWidgetItem(name))
            self.nav.currentRowChanged.connect(self._change_page)
            splitter.addWidget(self.nav)

            self.pages = QStackedWidget()
            self.page_by_name = {}
            self._create_pages()
            splitter.addWidget(self.pages)

            inspector = QFrame()
            inspector.setMinimumWidth(280)
            inspector.setMaximumWidth(390)
            inspector_layout = QVBoxLayout(inspector)
            inspector_layout.addWidget(QLabel("CONTEXT INSPECTOR"))
            self.inspector_title = QLabel("No selection")
            self.inspector_title.setStyleSheet("font-size:13pt;font-weight:700;")
            self.inspector_body = QTextEdit()
            self.inspector_body.setReadOnly(True)
            inspector_layout.addWidget(self.inspector_title)
            inspector_layout.addWidget(self.inspector_body, 1)
            splitter.addWidget(inspector)
            splitter.setStretchFactor(1, 1)
            root.addWidget(splitter, 1)

            status = QFrame()
            status_layout = QHBoxLayout(status)
            self.footer_status = QLabel("Ready")
            self.coordinate_status = QLabel("")
            status_layout.addWidget(self.footer_status)
            status_layout.addStretch(1)
            status_layout.addWidget(self.coordinate_status)
            root.addWidget(status)
            self.nav.setCurrentRow(1)

        def _page(self, name, title, subtitle):
            page = QWidget()
            layout = QVBoxLayout(page)
            heading = QLabel(title)
            heading.setStyleSheet("font-size:18pt;font-weight:700;")
            sub = QLabel(subtitle)
            sub.setStyleSheet("color:#91a2b1;")
            sub.setWordWrap(True)
            layout.addWidget(heading)
            layout.addWidget(sub)
            self.pages.addWidget(page)
            self.page_by_name[name] = (page, layout)
            return page, layout

        def _create_pages(self):
            self._build_projects_page()
            self._build_overview_page()
            self._build_data_page()
            self._build_explore_page()
            self._build_analyze_page()
            self._build_findings_page()
            self._build_compare_page()
            self._build_reports_page()
            self._build_exports_page()
            self._build_analytics_page()
            self._build_profiles_page()
            self._build_settings_page()

        def _build_projects_page(self):
            _, layout = self._page("Projects", "Projects", "Create, open, and maintain inspection project context without altering original survey data.")
            form_box = QGroupBox("Project")
            form = QFormLayout(form_box)
            self.project_name = QLineEdit()
            self.project_client = QLineEdit()
            self.project_site = QLineEdit()
            self.project_location = QLineEdit()
            self.project_operator = QLineEdit()
            self.project_asset = QLineEdit()
            self.project_description = QTextEdit()
            self.project_description.setMaximumHeight(80)
            for label, widget in (
                ("Project name", self.project_name),
                ("Client", self.project_client),
                ("Site", self.project_site),
                ("Location", self.project_location),
                ("Operator", self.project_operator),
                ("Asset type", self.project_asset),
                ("Description", self.project_description),
            ):
                form.addRow(label, widget)
            layout.addWidget(form_box)
            actions = QHBoxLayout()
            new_btn = QPushButton("New Project")
            open_btn = QPushButton("Open Project")
            save_btn = QPushButton("Save Project")
            new_btn.clicked.connect(self.new_project)
            open_btn.clicked.connect(self.open_project)
            save_btn.clicked.connect(self.save_project)
            actions.addWidget(new_btn)
            actions.addWidget(open_btn)
            actions.addWidget(save_btn)
            actions.addStretch(1)
            layout.addLayout(actions)
            layout.addStretch(1)

        def _build_overview_page(self):
            _, layout = self._page("Overview", "Project Overview", "Current data health, findings, thermal priorities, and processing state.")
            self.overview_metrics = QLabel()
            self.overview_metrics.setStyleSheet("font-size:12pt;line-height:150%;")
            self.overview_metrics.setWordWrap(True)
            layout.addWidget(self.overview_metrics)
            primary = QPushButton("Analyze Inspection")
            primary.clicked.connect(lambda: self.nav.setCurrentRow(self.NAV_ITEMS.index("Analyze")))
            layout.addWidget(primary, 0, Qt.AlignLeft)
            layout.addStretch(1)

        def _build_data_page(self):
            _, layout = self._page("Data", "Data", "Manage radiometric, visible, orthomosaic, and GIS inputs. Removing an item from this list never deletes the source file.")
            actions = QHBoxLayout()
            add_btn = QPushButton("Add Data")
            remove_btn = QPushButton("Remove from Project")
            validate_btn = QPushButton("Validate / Classify")
            add_btn.clicked.connect(self.add_data)
            remove_btn.clicked.connect(self.remove_data)
            validate_btn.clicked.connect(self.validate_data)
            actions.addWidget(add_btn)
            actions.addWidget(validate_btn)
            actions.addWidget(remove_btn)
            actions.addStretch(1)
            layout.addLayout(actions)
            self.data_table = QTableWidget(0, 5)
            self.data_table.setHorizontalHeaderLabels(["Source", "Type", "Radiometric status", "Size", "State"])
            self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            layout.addWidget(self.data_table, 1)

        def _build_explore_page(self):
            _, layout = self._page("Explore", "Explore", "Map-first geospatial context with bounded raster rendering and synchronized finding/source selection.")
            body = QSplitter(Qt.Horizontal)
            layers = QWidget()
            layer_layout = QVBoxLayout(layers)
            layer_layout.addWidget(QLabel("LAYERS"))
            self.layer_ortho = QCheckBox("Display / orthomosaic")
            self.layer_findings = QCheckBox("Findings")
            self.layer_findings.setChecked(True)
            self.layer_ortho.setChecked(True)
            self.layer_findings.stateChanged.connect(self.refresh_explore)
            self.layer_ortho.stateChanged.connect(self.refresh_explore)
            layer_layout.addWidget(self.layer_ortho)
            layer_layout.addWidget(self.layer_findings)
            layer_layout.addSpacing(10)
            layer_layout.addWidget(QLabel("SOURCE FRAMES"))
            self.source_list = QListWidget()
            self.source_list.currentRowChanged.connect(self.select_source_row)
            layer_layout.addWidget(self.source_list, 1)
            body.addWidget(layers)
            self.map_canvas = RasterCanvas()
            self.map_canvas.clicked.connect(self.on_canvas_clicked)
            body.addWidget(self.map_canvas)
            body.setStretchFactor(1, 1)
            layout.addWidget(body, 1)

        def _build_analyze_page(self):
            _, layout = self._page("Analyze", "Analyze Inspection", "Run the canonical quality gate → contextual detector → characterization → geolocation → deduplication pipeline.")
            options = QGroupBox("Inspection configuration")
            form = QFormLayout(options)
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
                ("Inspection profile", self.profile_combo),
                ("Sensor adapter", self.adapter_combo),
                ("Emissivity", self.emissivity),
                ("Distance (m)", self.distance),
                ("Relative humidity", self.humidity),
                ("Reflected temperature (°C)", self.reflected),
            ):
                form.addRow(label, widget)
            layout.addWidget(options)
            action_row = QHBoxLayout()
            self.analyze_btn = QPushButton("Analyze Inspection")
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setEnabled(False)
            self.analyze_btn.clicked.connect(self.start_inspection)
            self.cancel_btn.clicked.connect(self.cancel_inspection)
            action_row.addWidget(self.analyze_btn)
            action_row.addWidget(self.cancel_btn)
            action_row.addStretch(1)
            layout.addLayout(action_row)
            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.processing_text = QLabel("No analysis has run.")
            self.processing_text.setWordWrap(True)
            layout.addWidget(self.progress)
            layout.addWidget(self.processing_text)
            layout.addStretch(1)

        def _build_findings_page(self):
            _, layout = self._page("Findings", "Findings", "Filter, prioritize, and inspect canonical thermal evidence. Severity and confidence remain separate.")
            filters = QHBoxLayout()
            self.finding_search = QLineEdit()
            self.finding_search.setPlaceholderText("Search ID, classification, source…")
            self.finding_severity = QComboBox()
            self.finding_severity.addItems(["All severities", "critical", "moderate", "minor"])
            self.finding_search.textChanged.connect(self.refresh_findings)
            self.finding_severity.currentTextChanged.connect(self.refresh_findings)
            filters.addWidget(self.finding_search, 1)
            filters.addWidget(self.finding_severity)
            layout.addLayout(filters)
            self.findings_table = QTableWidget(0, 8)
            self.findings_table.setHorizontalHeaderLabels(["ID", "Classification", "Severity", "Confidence", "Max °C", "ΔT °C", "Source", "Status"])
            self.findings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.findings_table.itemSelectionChanged.connect(self.select_finding_row)
            layout.addWidget(self.findings_table, 1)
            status_row = QHBoxLayout()
            self.status_combo = QComboBox()
            for status in FindingStatus:
                self.status_combo.addItem(status.value.replace("_", " ").title(), status)
            set_status = QPushButton("Set Finding Status")
            set_status.clicked.connect(self.change_finding_status)
            status_row.addWidget(self.status_combo)
            status_row.addWidget(set_status)
            status_row.addStretch(1)
            layout.addLayout(status_row)

        def _build_compare_page(self):
            _, layout = self._page("Compare", "Compare", "Compare current canonical findings against a prior machine-readable inspection. Quantitative matching requires compatible geolocation.")
            actions = QHBoxLayout()
            load_btn = QPushButton("Load Prior findings.json")
            load_btn.clicked.connect(self.load_previous_findings)
            self.compare_label = QLabel("No prior inspection loaded")
            actions.addWidget(load_btn)
            actions.addWidget(self.compare_label)
            actions.addStretch(1)
            layout.addLayout(actions)
            self.compare_table = QTableWidget(0, 5)
            self.compare_table.setHorizontalHeaderLabels(["State", "Current", "Previous", "ΔΔT °C", "ΔMax °C"])
            self.compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(self.compare_table, 1)

        def _build_reports_page(self):
            _, layout = self._page("Reports", "Reports", "Generate reusable inspection artifacts from canonical findings and traceable evidence.")
            self.report_status = QLabel("No inspection package generated")
            button = QPushButton("Generate Full Thermal Inspection Package")
            button.clicked.connect(self.generate_package)
            layout.addWidget(button, 0, Qt.AlignLeft)
            layout.addWidget(self.report_status)
            layout.addStretch(1)

        def _build_exports_page(self):
            _, layout = self._page("Exports", "Exports", "PDF, CSV, JSON, GeoJSON/KML when coordinates exist, annotated imagery, crops, and manifest.")
            self.exports_list = QListWidget()
            layout.addWidget(self.exports_list, 1)

        def _build_analytics_page(self):
            _, layout = self._page("Analytics", "Analytics", "Operational thermal-inspection intelligence derived only from actual project state.")
            self.analytics_label = QLabel()
            self.analytics_label.setStyleSheet("font-size:12pt;")
            self.analytics_label.setWordWrap(True)
            layout.addWidget(self.analytics_label)
            layout.addStretch(1)

        def _build_profiles_page(self):
            _, layout = self._page("Profiles", "Inspection Profiles", "Versioned domain interpretation on top of one vendor-neutral quantitative engine.")
            self.profile_table = QTableWidget(0, 6)
            self.profile_table.setHorizontalHeaderLabels(["Profile", "Version", "Min ΔT", "Min area", "Moderate ΔT", "Critical ΔT"])
            self.profile_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            for profile in available_profiles():
                row = self.profile_table.rowCount()
                self.profile_table.insertRow(row)
                values = (profile.name, profile.version, profile.minimum_delta_c, profile.minimum_area_px, profile.moderate_delta_c, profile.critical_delta_c)
                for column, value in enumerate(values):
                    self.profile_table.setItem(row, column, QTableWidgetItem(str(value)))
            layout.addWidget(self.profile_table, 1)

        def _build_settings_page(self):
            _, layout = self._page("Settings", "Settings", "Runtime and quantitative-boundary information.")
            text = QLabel(
                "Quantitative authority: original radiometric sources decoded to ThermalFrame.\n"
                "Presentation authority: DisplayRaster / orthomosaic / GIS context.\n\n"
                "Automated reports are not thermographer certification. Source radiometry, calibration assumptions, and georeferencing determine quantitative validity."
            )
            text.setWordWrap(True)
            layout.addWidget(text)
            layout.addStretch(1)

        def _change_page(self, row):
            if row < 0:
                return
            name = self.NAV_ITEMS[row]
            page, _ = self.page_by_name[name]
            self.pages.setCurrentWidget(page)
            if name == "Explore":
                self.refresh_explore()
            elif name == "Findings":
                self.refresh_findings()
            elif name in {"Overview", "Analytics", "Exports"}:
                self.refresh_all()

        def _sync_project_from_form(self):
            project = session.project
            project.name = self.project_name.text().strip() or "Untitled inspection"
            project.client = self.project_client.text().strip()
            project.site = self.project_site.text().strip()
            project.location = self.project_location.text().strip()
            project.operator = self.project_operator.text().strip()
            project.asset_type = self.project_asset.text().strip()
            project.description = self.project_description.toPlainText().strip()
            project.touch()

        def _sync_form_from_project(self):
            project = session.project
            self.project_name.setText(project.name)
            self.project_client.setText(project.client)
            self.project_site.setText(project.site)
            self.project_location.setText(project.location)
            self.project_operator.setText(project.operator)
            self.project_asset.setText(project.asset_type)
            self.project_description.setPlainText(project.description)
            index = self.profile_combo.findData(project.profile_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

        def new_project(self):
            session.project = Project(name="Untitled inspection")
            session.set_sources([])
            self.selection.clear()
            self._sync_form_from_project()
            self.refresh_all()

        def open_project(self):
            path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "UAS Thermal Project (*.json)")
            if not path:
                return
            try:
                session.project = Project.load(path)
                sources = [source for dataset in session.project.datasets for source in dataset.source_paths]
                session.set_sources(sources)
            except Exception as exc:
                QMessageBox.critical(self, "Open Project Failed", str(exc))
                return
            self._sync_form_from_project()
            self.refresh_all()

        def save_project(self):
            self._sync_project_from_form()
            path, _ = QFileDialog.getSaveFileName(self, "Save project", f"{session.project.name}.uasproject.json", "UAS Thermal Project (*.json)")
            if not path:
                return
            try:
                session.project.save(path)
            except Exception as exc:
                QMessageBox.critical(self, "Save Project Failed", str(exc))
                return
            self.footer_status.setText(f"Saved project: {path}")

        def add_data(self):
            paths, _ = QFileDialog.getOpenFileNames(self, "Add thermal / visible / geospatial data", "", "Supported data (*.tif *.tiff *.jpg *.jpeg *.png *.kml *.geojson);;All files (*)")
            if not paths:
                return
            current = [str(path) for path in session.sources]
            current.extend(path for path in paths if path not in current)
            session.set_sources(current)
            session.project.add_dataset(paths, name=Path(paths[0]).parent.name)
            self.refresh_all()

        def remove_data(self):
            row = self.data_table.currentRow()
            if row < 0 or row >= len(session.sources):
                return
            session.sources.pop(row)
            session.artifacts.clear()
            session.last_run = None
            self.refresh_all()

        def validate_data(self):
            for row, source in enumerate(session.sources):
                status = "native candidate"
                state = "ready"
                if source.suffix.lower() in {".tif", ".tiff"}:
                    try:
                        diagnostics = GenericGeoTiffAdapter().source_diagnostics(source)
                        status = "radiometric candidate" if diagnostics.get("radiometric_candidate") else "display / GIS only"
                        state = "tiled preview" if diagnostics.get("requires_tiled_processing") else "ready"
                    except Exception as exc:
                        status = "validation failed"
                        state = str(exc)
                self.data_table.setItem(row, 2, QTableWidgetItem(status))
                self.data_table.setItem(row, 4, QTableWidgetItem(state))

        def _calibration(self):
            return ThermalCalibration(
                emissivity=float(self.emissivity.text()),
                distance_m=float(self.distance.text()),
                relative_humidity=float(self.humidity.text()),
                reflected_temperature_c=float(self.reflected.text()),
            )

        def start_inspection(self):
            if not session.sources:
                QMessageBox.information(self, "No Data", "Add at least one radiometric source before analysis.")
                return
            try:
                self._sync_project_from_form()
                calibration = self._calibration()
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Calibration", str(exc))
                return
            self.analyze_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.progress.setValue(0)
            self.worker = InspectionWorker(calibration, self.adapter_combo.currentData(), self.profile_combo.currentData())
            self.worker.event.connect(self.on_processing_event)
            self.worker.completed.connect(self.on_inspection_complete)
            self.worker.failed.connect(self.on_inspection_failed)
            self.worker.start()

        def cancel_inspection(self):
            if self.worker is not None:
                self.worker.cancel()
                self.processing_text.setText("Cancellation requested; the current atomic source operation will finish safely.")

        def on_processing_event(self, event):
            text = f"{event.stage.value.replace('_', ' ').title()} — {event.message}"
            if event.source:
                text += f"\n{event.source}"
            self.processing_text.setText(text)
            self.header_status.setText(event.stage.value.replace("_", " ").title())
            if event.total:
                self.progress.setValue(round(100 * event.completed / event.total))

        def on_inspection_complete(self, run):
            self.analyze_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress.setValue(100)
            self.processing_text.setText(
                f"Complete — {run.summary.canonical_findings} canonical finding(s); "
                f"{run.summary.images_rejected} rejected source(s)."
            )
            self.header_status.setText("Analysis complete")
            self.refresh_all()
            if run.failures:
                QMessageBox.warning(
                    self,
                    "Inspection Completed With Rejections",
                    "Some sources were isolated and excluded. Open Analyze or Data for details.",
                )

        def on_inspection_failed(self, message):
            self.analyze_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.header_status.setText("Analysis failed")
            QMessageBox.critical(self, "Analysis Failed", message)

        def current_findings(self):
            return [] if session.last_run is None else session.last_run.canonical_findings

        def refresh_all(self):
            self._sync_form_from_project()
            self.project_header.setText(f"{session.project.name}  ·  {session.project.site or 'No site'}")
            self.source_list.clear()
            for source in session.sources:
                self.source_list.addItem(source.name)
            self.data_table.setRowCount(0)
            for source in session.sources:
                row = self.data_table.rowCount()
                self.data_table.insertRow(row)
                size = f"{source.stat().st_size / (1024**2):,.2f} MB" if source.is_file() else "missing"
                data_type = "GeoTIFF" if source.suffix.lower() in {".tif", ".tiff"} else "Image"
                for column, value in enumerate((source.name, data_type, "not validated", size, "not processed")):
                    self.data_table.setItem(row, column, QTableWidgetItem(value))
            findings = self.current_findings()
            rejected = 0 if session.last_run is None else len(session.last_run.failures)
            analytics = summarize_workspace([session.project], findings, rejected_sources=rejected)
            critical = analytics.critical_findings
            highest = max((item.max_temperature_c for item in findings), default=None)
            highest_delta = max((item.delta_temperature_c for item in findings), default=None)
            self.overview_metrics.setText(
                f"<b>DATA</b><br/>Sources: {len(session.sources)} &nbsp;&nbsp; Rejected: {rejected}<br/><br/>"
                f"<b>FINDINGS</b><br/>Total: {len(findings)} &nbsp;&nbsp; Critical: {critical}<br/><br/>"
                f"<b>THERMAL</b><br/>Highest temperature: {'—' if highest is None else f'{highest:.1f} °C'}<br/>"
                f"Highest local ΔT: {'—' if highest_delta is None else f'{highest_delta:+.1f} °C'}"
            )
            self.analytics_label.setText(
                f"Projects: {analytics.projects}\nDatasets: {analytics.datasets}\nFindings: {analytics.findings}\n"
                f"Critical findings: {analytics.critical_findings}\nAction required: {analytics.action_required}\n"
                f"Rejected sources: {analytics.rejected_sources}"
            )
            self.refresh_findings()
            self.refresh_exports()

        def refresh_findings(self):
            if not hasattr(self, "findings_table"):
                return
            query = self.finding_search.text().strip().lower()
            severity = self.finding_severity.currentText()
            rows = []
            for finding in self.current_findings():
                haystack = " ".join([finding.finding_id, finding.classification, finding.source_path]).lower()
                if query and query not in haystack:
                    continue
                if severity != "All severities" and finding.severity.value != severity:
                    continue
                rows.append(finding)
            self._visible_findings = rows
            self.findings_table.setRowCount(0)
            for finding in rows:
                row = self.findings_table.rowCount()
                self.findings_table.insertRow(row)
                values = (
                    finding.finding_id,
                    finding.classification or finding.finding_type,
                    finding.severity.value,
                    finding.confidence.value,
                    f"{finding.max_temperature_c:.1f}",
                    f"{finding.delta_temperature_c:+.1f}",
                    Path(finding.source_path).name if finding.source_path else "",
                    finding.lifecycle_status.value,
                )
                for column, value in enumerate(values):
                    self.findings_table.setItem(row, column, QTableWidgetItem(str(value)))

        def select_finding_row(self):
            row = self.findings_table.currentRow()
            if row < 0 or row >= len(getattr(self, "_visible_findings", [])):
                return
            finding = self._visible_findings[row]
            self.selection.select_finding(finding)
            self.inspector_title.setText(finding.finding_id or "Finding")
            details = finding_details(finding)
            self.inspector_body.setPlainText("\n".join(f"{key}: {value}" for key, value in details.items()))

        def change_finding_status(self):
            row = self.findings_table.currentRow()
            if row < 0 or row >= len(getattr(self, "_visible_findings", [])):
                return
            from ..inspections.lifecycle import transition_finding

            finding = self._visible_findings[row]
            transition_finding(finding, self.status_combo.currentData())
            self.refresh_findings()

        def select_source_row(self, row):
            if 0 <= row < len(session.sources):
                source = session.sources[row]
                self.selection.selected_source = str(source)
                self.inspector_title.setText(source.name)
                self.inspector_body.setPlainText(str(source))
                if source.suffix.lower() in {".tif", ".tiff"}:
                    self.load_display_source(source)

        def load_display_source(self, source):
            try:
                self.display_raster = read_display_raster(source, max_edge=1800)
            except Exception as exc:
                self.map_canvas.clear_raster(f"Preview unavailable: {exc}")
                return
            self.refresh_explore()

        def refresh_explore(self):
            if not hasattr(self, "map_canvas"):
                return
            if self.display_raster is None:
                display_candidates = [source for source in session.sources if source.suffix.lower() in {".tif", ".tiff"}]
                if display_candidates:
                    try:
                        self.display_raster = read_display_raster(display_candidates[0], max_edge=1800)
                    except Exception:
                        self.display_raster = None
            if self.display_raster is None or not self.layer_ortho.isChecked():
                self.map_canvas.clear_raster("No active display / GIS raster")
                return
            points = []
            if self.layer_findings.isChecked():
                for finding in self.current_findings():
                    point = finding_to_display_point(finding, self.display_raster)
                    if point is not None:
                        points.append(point)
            self.map_canvas.set_rgb(self.display_raster.rgb, points)

        def on_canvas_clicked(self, x, y):
            self.coordinate_status.setText(f"Display pixel {x:.0f}, {y:.0f}")

        def load_previous_findings(self):
            path, _ = QFileDialog.getOpenFileName(self, "Load prior findings", "", "Findings JSON (*.json)")
            if not path:
                return
            try:
                self.previous_findings = read_findings_json(path)
            except Exception as exc:
                QMessageBox.critical(self, "Compare Load Failed", str(exc))
                return
            self.compare_label.setText(f"Loaded {len(self.previous_findings)} prior finding(s)")
            self.refresh_compare()

        def refresh_compare(self):
            self.compare_table.setRowCount(0)
            if not self.previous_findings or session.last_run is None:
                return
            changes = compare_finding_sets(self.previous_findings, self.current_findings())
            for change in changes:
                row = self.compare_table.rowCount()
                self.compare_table.insertRow(row)
                values = (
                    change.state.value,
                    change.current_id or "—",
                    change.previous_id or "—",
                    "—" if change.delta_t_change_c is None else f"{change.delta_t_change_c:+.1f}",
                    "—" if change.max_temperature_change_c is None else f"{change.max_temperature_change_c:+.1f}",
                )
                for column, value in enumerate(values):
                    self.compare_table.setItem(row, column, QTableWidgetItem(value))

        def generate_package(self):
            if session.last_run is None or not session.last_run.artifacts:
                QMessageBox.information(self, "No Analysis", "Analyze the inspection before generating a report package.")
                return
            output = QFileDialog.getExistingDirectory(self, "Select inspection package output folder")
            if not output:
                return
            try:
                package = session.export_package(output)
            except Exception as exc:
                QMessageBox.critical(self, "Package Generation Failed", str(exc))
                return
            self.report_status.setText(f"Generated: {package}")
            self.refresh_exports()

        def refresh_exports(self):
            if not hasattr(self, "exports_list"):
                return
            self.exports_list.clear()
            if session.last_run is None or session.last_run.package_dir is None:
                self.exports_list.addItem("No generated inspection package")
                return
            root = Path(session.last_run.package_dir)
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    self.exports_list.addItem(str(path.relative_to(root)))

    app = QApplication.instance() or QApplication(sys.argv)
    window = WorkspaceWindow()
    window.show()
    return app.exec_()
