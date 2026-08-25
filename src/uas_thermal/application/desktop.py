from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..reporting.bundle import ReportBundle, write_report_bundle
from ..thermal.calibration import ThermalCalibration
from .projects import Project
from .workflows import AnalysisArtifact, AnalysisWorkflow


@dataclass(slots=True)
class DesktopSession:
    workflow: AnalysisWorkflow = field(default_factory=AnalysisWorkflow.default)
    project: Project = field(default_factory=lambda: Project(name="Untitled inspection"))
    sources: list[Path] = field(default_factory=list)
    artifacts: list[AnalysisArtifact] = field(default_factory=list)

    def set_sources(self, sources: list[str | Path]) -> None:
        self.sources = [Path(source) for source in sources]
        self.artifacts.clear()

    def analyze(
        self,
        calibration: ThermalCalibration,
        adapter_name: str | None = None,
    ) -> list[AnalysisArtifact]:
        if not self.sources:
            raise ValueError("Select at least one thermal source before analysis")
        self.artifacts = self.workflow.analyze_many(
            self.sources,
            calibration=calibration,
            adapter_name=adapter_name,
            project=self.project,
        )
        return self.artifacts

    def export(self, output_dir: str | Path) -> list[ReportBundle]:
        if not self.artifacts:
            raise ValueError("Analyze thermal sources before exporting reports")
        bundles = []
        for artifact in self.artifacts:
            bundles.append(
                write_report_bundle(
                    artifact.result,
                    output_dir,
                    stem=Path(artifact.result.source).stem,
                )
            )
        return bundles


def launch() -> int:
    try:
        from PyQt5.QtCore import QThread, Qt, pyqtSignal
        from PyQt5.QtGui import QImage, QPixmap
        from PyQt5.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("Install the desktop extra to launch the Windows UI") from exc

    import sys

    from ..geospatial.display import read_display_raster
    from ..sensors.generic import GenericGeoTiffAdapter

    session = DesktopSession()

    class AnalysisThread(QThread):
        completed = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, calibration: ThermalCalibration, adapter_name: str | None):
            super().__init__()
            self.calibration = calibration
            self.adapter_name = adapter_name

        def run(self) -> None:
            try:
                self.completed.emit(session.analyze(self.calibration, self.adapter_name))
            except Exception as exc:
                self.failed.emit(str(exc))

    class PreviewThread(QThread):
        completed = pyqtSignal(object, object)
        failed = pyqtSignal(str)

        def __init__(self, source: Path):
            super().__init__()
            self.source = source

        def run(self) -> None:
            try:
                display = read_display_raster(self.source, max_edge=1600)
                diagnostics = GenericGeoTiffAdapter().source_diagnostics(self.source)
                self.completed.emit(display, diagnostics)
            except Exception as exc:
                self.failed.emit(str(exc))

    class ThermalWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("UAS Thermal Analysis")
            self.resize(1280, 820)
            self.setStyleSheet(
                "QMainWindow{background:#15181d;} QWidget{color:#e8edf2;font-size:11pt;}"
                "QGroupBox{border:1px solid #3d4652;border-radius:8px;margin-top:10px;padding:10px;}"
                "QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 4px;}"
                "QLineEdit,QComboBox,QTableWidget{background:#20252c;border:1px solid #3d4652;border-radius:5px;padding:5px;}"
                "QPushButton{background:#2c79c7;border:0;border-radius:6px;padding:8px 14px;font-weight:600;}"
                "QPushButton:disabled{background:#3b4149;color:#777;}"
            )
            central = QWidget()
            self.setCentralWidget(central)
            root = QHBoxLayout(central)
            controls = QVBoxLayout()
            content = QVBoxLayout()
            root.addLayout(controls, 0)
            root.addLayout(content, 1)

            project_box = QGroupBox("Inspection project")
            project_form = QFormLayout(project_box)
            self.project_name = QLineEdit(session.project.name)
            self.site = QLineEdit()
            self.client = QLineEdit()
            self.operator = QLineEdit()
            self.asset_type = QLineEdit()
            self.sensor_model = QLineEdit()
            for label, widget in (
                ("Project", self.project_name),
                ("Site", self.site),
                ("Client", self.client),
                ("Operator", self.operator),
                ("Asset type", self.asset_type),
                ("Sensor model", self.sensor_model),
            ):
                project_form.addRow(label, widget)
            controls.addWidget(project_box)

            source_box = QGroupBox("Sources")
            source_layout = QVBoxLayout(source_box)
            self.source_label = QLabel("No files selected")
            self.source_status = QLabel("Status: not classified")
            self.source_status.setWordWrap(True)
            select_sources = QPushButton("Select imagery")
            select_sources.clicked.connect(self.choose_sources)
            self.preview_button = QPushButton("Preview / classify selected")
            self.preview_button.setEnabled(False)
            self.preview_button.clicked.connect(self.preview_selected_source)
            self.adapter = QComboBox()
            self.adapter.addItem("Auto detect", None)
            for adapter in session.workflow.registry.adapters:
                self.adapter.addItem(f"{adapter.vendor} — {adapter.name}", adapter.name)
            source_layout.addWidget(self.source_label)
            source_layout.addWidget(self.source_status)
            source_layout.addWidget(select_sources)
            source_layout.addWidget(self.preview_button)
            source_layout.addWidget(self.adapter)
            controls.addWidget(source_box)

            calibration_box = QGroupBox("Radiometric calibration")
            calibration_form = QFormLayout(calibration_box)
            self.emissivity = QLineEdit("0.95")
            self.distance = QLineEdit("5.0")
            self.humidity = QLineEdit("0.50")
            self.reflected = QLineEdit("20.0")
            calibration_form.addRow("Emissivity", self.emissivity)
            calibration_form.addRow("Distance (m)", self.distance)
            calibration_form.addRow("Humidity", self.humidity)
            calibration_form.addRow("Reflected temp (°C)", self.reflected)
            controls.addWidget(calibration_box)

            self.analyze_button = QPushButton("Analyze radiometry")
            self.analyze_button.setEnabled(False)
            self.analyze_button.clicked.connect(self.start_analysis)
            self.export_button = QPushButton("Export PDF / CSV / KML")
            self.export_button.setEnabled(False)
            self.export_button.clicked.connect(self.export_reports)
            controls.addWidget(self.analyze_button)
            controls.addWidget(self.export_button)
            controls.addStretch(1)

            self.preview = QLabel("Select imagery to preview or analyze")
            self.preview.setAlignment(Qt.AlignCenter)
            self.preview.setMinimumHeight(420)
            self.preview.setStyleSheet(
                "background:#0d0f12;border:1px solid #303741;border-radius:8px;"
            )
            content.addWidget(self.preview, 3)
            self.results = QTableWidget(0, 6)
            self.results.setHorizontalHeaderLabels(
                ["Source", "Severity", "Max °C", "ΔT °C", "Latitude", "Longitude"]
            )
            content.addWidget(self.results, 2)

        def choose_sources(self) -> None:
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select thermal or geospatial imagery",
                "",
                "Supported imagery (*.tif *.tiff *.jpg *.jpeg)",
            )
            if not paths:
                return
            session.set_sources(paths)
            self.source_label.setText(f"{len(paths)} file(s) selected")
            self.source_status.setText("Status: selected · classification pending")
            self.analyze_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.export_button.setEnabled(False)
            if len(paths) == 1 and Path(paths[0]).suffix.lower() in {".tif", ".tiff"}:
                self.preview_selected_source()

        def preview_selected_source(self) -> None:
            if not session.sources:
                return
            source = session.sources[0]
            if source.suffix.lower() not in {".tif", ".tiff"}:
                self.source_status.setText(
                    "Status: radiometric/native image candidate · analyze to decode temperatures"
                )
                return
            self.preview_button.setEnabled(False)
            self.source_status.setText("Status: reading bounded preview and classifying…")
            self.preview_worker = PreviewThread(source)
            self.preview_worker.completed.connect(self.on_preview_completed)
            self.preview_worker.failed.connect(self.on_preview_failed)
            self.preview_worker.start()

        def _set_preview_rgb(self, rgb) -> None:
            height, width, _ = rgb.shape
            image = QImage(
                rgb.data,
                width,
                height,
                width * 3,
                QImage.Format_RGB888,
            ).copy()
            self.preview.setPixmap(
                QPixmap.fromImage(image).scaled(
                    self.preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        def on_preview_completed(self, display, diagnostics) -> None:
            self.preview_button.setEnabled(True)
            self._set_preview_rgb(display.rgb)
            radiometric = bool(diagnostics.get("radiometric_candidate"))
            tiled = bool(diagnostics.get("requires_tiled_processing"))
            if radiometric:
                mode = "Radiometric candidate"
                self.analyze_button.setEnabled(not tiled)
            else:
                mode = "Display / GIS only"
                if len(session.sources) == 1:
                    self.analyze_button.setEnabled(False)
            suffix = " · tiled processing required" if tiled else ""
            reasons = diagnostics.get("radiometric_reasons") or []
            reason_text = " · " + "; ".join(reasons) if reasons else ""
            self.source_status.setText(f"Status: {mode}{suffix}{reason_text}")

        def on_preview_failed(self, message: str) -> None:
            self.preview_button.setEnabled(True)
            self.source_status.setText(f"Status: preview unavailable · {message}")

        def _sync_project(self) -> None:
            session.project.name = self.project_name.text().strip() or "Untitled inspection"
            session.project.site = self.site.text().strip()
            session.project.client = self.client.text().strip()
            session.project.operator = self.operator.text().strip()
            session.project.asset_type = self.asset_type.text().strip()
            session.project.sensor_model = self.sensor_model.text().strip()

        def _calibration(self) -> ThermalCalibration:
            return ThermalCalibration(
                emissivity=float(self.emissivity.text()),
                distance_m=float(self.distance.text()),
                relative_humidity=float(self.humidity.text()),
                reflected_temperature_c=float(self.reflected.text()),
            )

        def start_analysis(self) -> None:
            try:
                self._sync_project()
                calibration = self._calibration()
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid calibration", str(exc))
                return
            self.analyze_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.worker = AnalysisThread(calibration, self.adapter.currentData())
            self.worker.completed.connect(self.on_completed)
            self.worker.failed.connect(self.on_failed)
            self.worker.start()

        def on_completed(self, artifacts) -> None:
            self.results.setRowCount(0)
            for artifact in artifacts:
                result = artifact.result
                for finding in result.findings:
                    row = self.results.rowCount()
                    self.results.insertRow(row)
                    values = (
                        Path(result.source).name,
                        finding.severity.value,
                        f"{finding.max_temperature_c:.1f}",
                        f"{finding.delta_temperature_c:.1f}",
                        "" if finding.latitude is None else f"{finding.latitude:.6f}",
                        "" if finding.longitude is None else f"{finding.longitude:.6f}",
                    )
                    for column, value in enumerate(values):
                        self.results.setItem(row, column, QTableWidgetItem(value))
            if artifacts and artifacts[0].frame.display_rgb is not None:
                self._set_preview_rgb(artifacts[0].frame.display_rgb)
            else:
                count = sum(len(artifact.result.findings) for artifact in artifacts)
                self.preview.setText(f"Analysis complete · {count} thermal finding(s)")
            self.source_status.setText("Status: radiometric analysis complete")
            self.analyze_button.setEnabled(True)
            self.export_button.setEnabled(bool(artifacts))

        def on_failed(self, message: str) -> None:
            self.analyze_button.setEnabled(True)
            QMessageBox.critical(self, "Analysis failed", message)

        def export_reports(self) -> None:
            output_dir = QFileDialog.getExistingDirectory(self, "Select report output folder")
            if not output_dir:
                return
            try:
                bundles = session.export(output_dir)
            except Exception as exc:
                QMessageBox.critical(self, "Export failed", str(exc))
                return
            QMessageBox.information(
                self,
                "Reports exported",
                f"Created report bundles for {len(bundles)} source(s) in:\n{output_dir}",
            )

    app = QApplication.instance() or QApplication(sys.argv)
    window = ThermalWindow()
    window.show()
    return app.exec_()
