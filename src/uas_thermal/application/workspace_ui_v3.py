from __future__ import annotations

from pathlib import Path


def create_workspace_window(session):
    """Extend the v0.6 workspace with universal processing and local-AI controls."""

    from PyQt5.QtCore import QThread, Qt, pyqtSignal
    from PyQt5.QtWidgets import (
        QFileDialog,
        QComboBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
    )

    from ..ai.ollama import OllamaProvider
    from ..inspections.profiles import get_profile
    from ..orthomosaic import OrthomosaicService
    from ..platform.config import AppConfig
    from ..thermal.measurements import (
        circle_statistics,
        ellipse_statistics,
        line_statistics,
        polygon_statistics,
        rectangle_statistics,
        spot_delta,
        spot_statistics,
    )
    from ..thermal.presentation import ThermalStyle, automatic_style, available_palettes
    from .universal_pipeline import UniversalProcessingPlan, UniversalThermalProcessor
    from .workspace_ui_v2 import create_workspace_window as create_v2_workspace

    app, window = create_v2_workspace(session)
    config = AppConfig.from_env()
    window.setWindowTitle(window.windowTitle().replace("0.6", "0.7"))
    window.universal_worker = None
    window.measurements = []

    # --- Thermal tuning: visual-only Span / Level controls -----------------
    explore_page = window.pages.widget(window.page_index["Explore"])
    explore_layout = explore_page.layout()
    tuning_box = QGroupBox("Thermal tuning (visual only - measurements are unchanged)")
    tuning_layout = QHBoxLayout(tuning_box)
    span_edit = QLineEdit()
    span_edit.setPlaceholderText("Span C")
    span_edit.setMaximumWidth(110)
    level_edit = QLineEdit()
    level_edit.setPlaceholderText("Level C")
    level_edit.setMaximumWidth(110)
    apply_tuning = QPushButton("Apply Span / Level")
    auto_tuning = QPushButton("Auto Tune")
    tuning_layout.addWidget(QLabel("Span"))
    tuning_layout.addWidget(span_edit)
    tuning_layout.addWidget(QLabel("Level"))
    tuning_layout.addWidget(level_edit)
    tuning_layout.addWidget(apply_tuning)
    tuning_layout.addWidget(auto_tuning)
    tuning_layout.addStretch(1)
    explore_layout.insertWidget(2, tuning_box)
    window.thermal_span = span_edit
    window.thermal_level = level_edit
    iron_index = window.palette.findText("ironbow")
    if iron_index >= 0:
        window.palette.setCurrentIndex(iron_index)

    def apply_span_level():
        try:
            span = float(span_edit.text())
            level = float(level_edit.text())
            style = ThermalStyle(palette=window.palette.currentText(), span_c=span, level_c=level)
            low, high = style.limits()
        except ValueError as exc:
            window.footer.setText(str(exc))
            return
        window.range_min.setText(f"{low:.6f}")
        window.range_max.setText(f"{high:.6f}")
        window.render_current_artifact()

    def auto_tune():
        if window.current_artifact is None:
            return
        style = automatic_style(
            window.current_artifact.frame.temperature_c,
            palette=window.palette.currentText(),
        )
        low, high = style.limits()
        if low is None or high is None:
            return
        span_edit.setText(f"{high - low:.2f}")
        level_edit.setText(f"{(high + low) / 2.0:.2f}")
        window.range_min.setText(f"{low:.6f}")
        window.range_max.setText(f"{high:.6f}")
        window.render_current_artifact()

    apply_tuning.clicked.connect(apply_span_level)
    auto_tuning.clicked.connect(auto_tune)

    # --- Quantitative measurement workspace --------------------------------
    measurements_layout = window._page(
        "Measurements",
        "Temperature Measurements",
        (
            "Spot (4x4 average), delta, rectangle, circle, ellipse, line and polygon statistics. "
            "Measurement tools read the temperature matrix; palette and Span/Level never change them."
        ),
    )
    window.nav.addItem("Measurements")
    measure_form_box = QGroupBox("Add measurement")
    measure_form = QFormLayout(measure_form_box)
    measure_kind = QComboBox()
    measure_kind.addItems(["Spot", "Rectangle", "Circle", "Ellipse", "Line", "Polygon"])
    measure_geometry = QLineEdit()
    measure_geometry.setPlaceholderText("Spot x,y | Rect x0,y0,x1,y1 | Polygon x,y;x,y;x,y")
    measure_label = QLineEdit()
    measure_label.setPlaceholderText("Optional label")
    measure_form.addRow("Tool", measure_kind)
    measure_form.addRow("Geometry", measure_geometry)
    measure_form.addRow("Label", measure_label)
    measurements_layout.addWidget(measure_form_box)
    measure_actions = QHBoxLayout()
    add_measure = QPushButton("Add Measurement")
    delta_geometry = QLineEdit()
    delta_geometry.setPlaceholderText("Spot delta: x1,y1;x2,y2")
    delta_button = QPushButton("Calculate Delta")
    measure_actions.addWidget(add_measure)
    measure_actions.addSpacing(20)
    measure_actions.addWidget(delta_geometry, 1)
    measure_actions.addWidget(delta_button)
    measurements_layout.addLayout(measure_actions)
    measurement_table = QTableWidget(0, 7)
    measurement_table.setHorizontalHeaderLabels(
        ["Label", "Tool", "Min C", "Mean C", "Max C", "P95 C", "Pixels"]
    )
    measurement_table.horizontalHeader().setStretchLastSection(True)
    measurements_layout.addWidget(measurement_table, 1)
    measure_note = QLabel(
        "For downsampled large-raster previews, area tools describe the preview matrix. Exact "
        "full-resolution spot access remains available through the tiled quantitative backend."
    )
    measure_note.setWordWrap(True)
    measure_note.setStyleSheet("color:#94a6b5;")
    measurements_layout.addWidget(measure_note)

    def current_matrix():
        if window.current_artifact is None:
            raise ValueError("Select an analyzed radiometric source in Explore first")
        return window.current_artifact.frame.temperature_c

    def parse_numbers(text):
        return [float(item.strip()) for item in text.split(",") if item.strip()]

    def append_measurement(tool, stats, label):
        row = measurement_table.rowCount()
        measurement_table.insertRow(row)
        values = [
            label or f"M-{row + 1:03d}",
            tool,
            f"{stats.minimum_c:.2f}",
            f"{stats.mean_c:.2f}",
            f"{stats.maximum_c:.2f}",
            f"{stats.p95_c:.2f}",
            f"{stats.valid_pixels:,}",
        ]
        for column, value in enumerate(values):
            measurement_table.setItem(row, column, QTableWidgetItem(str(value)))
        window.measurements.append(
            {
                "label": values[0],
                "tool": tool,
                "geometry": measure_geometry.text(),
                "minimum_c": stats.minimum_c,
                "mean_c": stats.mean_c,
                "maximum_c": stats.maximum_c,
                "p95_c": stats.p95_c,
                "valid_pixels": stats.valid_pixels,
            }
        )

    def add_measurement():
        try:
            matrix = current_matrix()
            kind = measure_kind.currentText()
            geometry = measure_geometry.text().strip()
            if kind == "Polygon":
                points = [tuple(parse_numbers(point)) for point in geometry.split(";") if point.strip()]
                if any(len(point) != 2 for point in points):
                    raise ValueError("Polygon format: x,y;x,y;x,y")
                stats = polygon_statistics(matrix, points)
            else:
                values = parse_numbers(geometry)
                if kind == "Spot" and len(values) == 2:
                    stats = spot_statistics(matrix, round(values[0]), round(values[1]))
                elif kind == "Rectangle" and len(values) == 4:
                    stats = rectangle_statistics(matrix, *map(round, values))
                elif kind == "Circle" and len(values) == 3:
                    stats = circle_statistics(matrix, *values)
                elif kind == "Ellipse" and len(values) == 4:
                    stats = ellipse_statistics(matrix, *values)
                elif kind == "Line" and len(values) in {4, 5}:
                    width = values[4] if len(values) == 5 else 1.5
                    stats = line_statistics(matrix, *values[:4], width_px=width)
                else:
                    raise ValueError("Geometry does not match the selected measurement tool")
            append_measurement(kind, stats, measure_label.text().strip())
        except Exception as exc:
            QMessageBox.warning(window, "Measurement", str(exc))

    def calculate_delta():
        try:
            matrix = current_matrix()
            points = [parse_numbers(item) for item in delta_geometry.text().split(";")]
            if len(points) != 2 or any(len(point) != 2 for point in points):
                raise ValueError("Spot delta format: x1,y1;x2,y2")
            delta = spot_delta(
                matrix,
                (round(points[0][0]), round(points[0][1])),
                (round(points[1][0]), round(points[1][1])),
            )
            window.footer.setText(f"Spot delta: {delta:+.2f} C (second minus first)")
        except Exception as exc:
            QMessageBox.warning(window, "Spot Delta", str(exc))

    add_measure.clicked.connect(add_measurement)
    delta_button.clicked.connect(calculate_delta)

    # --- Universal automated processing workspace --------------------------
    process_layout = window._page(
        "Process",
        "Universal Thermal Processing",
        (
            "Ingest -> optional thermal orthomosaic -> quantitative analysis -> optional local AI "
            "interpretation -> annotations -> client/engineering deliverable."
        ),
    )
    window.nav.addItem("Process")
    process_box = QGroupBox("Automation plan")
    process_form = QFormLayout(process_box)
    stitch_combo = QComboBox()
    stitch_combo.addItems(["auto", "on", "off"])
    backend_combo = QComboBox()
    backend_combo.addItems(["auto", "native-geotiff", "opendronemap"])
    ai_combo = QComboBox()
    ai_combo.addItem("Off", "off")
    ai_combo.addItem("Auto-select local model", "auto")
    process_palette = QComboBox()
    process_palette.addItems(list(available_palettes()))
    iron_process_index = process_palette.findText("ironbow")
    if iron_process_index >= 0:
        process_palette.setCurrentIndex(iron_process_index)
    process_span = QLineEdit()
    process_span.setPlaceholderText("Auto")
    process_level = QLineEdit()
    process_level.setPlaceholderText("Auto")
    output_edit = QLineEdit(str(config.data_dir / "deliverables"))
    output_row = QHBoxLayout()
    output_row.addWidget(output_edit, 1)
    browse_output = QPushButton("Browse...")
    output_row.addWidget(browse_output)
    process_form.addRow("Stitch thermal orthomosaic", stitch_combo)
    process_form.addRow("Orthomosaic backend", backend_combo)
    process_form.addRow("Local AI", ai_combo)
    process_form.addRow("Deliverable palette", process_palette)
    process_form.addRow("Span C", process_span)
    process_form.addRow("Level C", process_level)
    process_form.addRow("Output", output_row)
    process_layout.addWidget(process_box)
    process_actions = QHBoxLayout()
    refresh_ai = QPushButton("Refresh Local Models")
    process_button = QPushButton("Process Project")
    process_actions.addWidget(refresh_ai)
    process_actions.addWidget(process_button)
    process_actions.addStretch(1)
    process_layout.addLayout(process_actions)
    process_log = QTextEdit()
    process_log.setReadOnly(True)
    process_layout.addWidget(process_log, 1)

    class UniversalWorker(QThread):
        eventRaised = pyqtSignal(str)
        completed = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, processor, project, sources, output, calibration, profile, plan):
            super().__init__()
            self.processor = processor
            self.project = project
            self.sources = sources
            self.output = output
            self.calibration = calibration
            self.profile = profile
            self.plan = plan

        def run(self):
            try:
                result = self.processor.process(
                    self.project,
                    self.sources,
                    self.output,
                    calibration=self.calibration,
                    profile=self.profile,
                    plan=self.plan,
                    on_event=self.eventRaised.emit,
                )
                self.completed.emit(result)
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def refresh_local_models():
        ai_combo.clear()
        ai_combo.addItem("Off", "off")
        ai_combo.addItem("Auto-select local model", "auto")
        provider = OllamaProvider(config.ollama_base_url)
        if not provider.available():
            process_log.append(f"Ollama unavailable at {config.ollama_base_url}")
            return
        try:
            models = provider.list_models()
        except Exception as exc:
            process_log.append(str(exc))
            return
        for model in models:
            capability = "vision" if model.supports_vision else "text"
            suffix = f" - {model.parameter_size}" if model.parameter_size else ""
            ai_combo.addItem(f"{model.name} [{capability}]{suffix}", model.name)
        process_log.append(f"Found {len(models)} local Ollama model(s)")

    def browse_process_output():
        selected = QFileDialog.getExistingDirectory(window, "Thermal deliverable output directory")
        if selected:
            output_edit.setText(selected)

    def process_project():
        try:
            window._sync_project_form()
            if not session.sources:
                raise ValueError("Add thermal source data before processing")
            span_text = process_span.text().strip()
            level_text = process_level.text().strip()
            span = float(span_text) if span_text else None
            level = float(level_text) if level_text else None
            style = ThermalStyle(
                palette=process_palette.currentText(),
                span_c=span,
                level_c=level,
            )
            plan = UniversalProcessingPlan(
                stitch_mode=stitch_combo.currentText(),
                orthomosaic_backend=backend_combo.currentText(),
                ai_mode=ai_combo.currentData(),
                thermal_style=style,
            )
            calibration = window._calibration()
            profile = get_profile(window.profile_combo.currentData())
            output = Path(output_edit.text()).expanduser()
        except Exception as exc:
            QMessageBox.warning(window, "Process Project", str(exc))
            return
        process_button.setEnabled(False)
        process_log.clear()
        window.header_status.setText("Processing project")
        window.universal_worker = UniversalWorker(
            UniversalThermalProcessor(),
            session.project,
            list(session.sources),
            output,
            calibration,
            profile,
            plan,
        )
        window.universal_worker.eventRaised.connect(process_log.append)

        def complete(result):
            process_button.setEnabled(True)
            session.last_run = result.run
            session.artifacts = list(result.run.artifacts)
            session.project.exports.append(
                {
                    "type": "universal-thermal-deliverable",
                    "path": str(result.deliverable_dir),
                }
            )
            window.header_status.setText("Complete")
            process_log.append(f"Deliverable: {result.deliverable_dir}")
            if result.ai_model:
                process_log.append(
                    f"AI: {result.ai_provider}/{result.ai_model} enriched "
                    f"{result.ai_enriched_findings} finding(s)"
                )
            for warning in result.warnings:
                process_log.append(f"Warning: {warning}")
            window.refresh_all()
            window.footer.setText(f"Universal deliverable created: {result.deliverable_dir}")

        def failed(message):
            process_button.setEnabled(True)
            window.header_status.setText("Processing failed")
            process_log.append(message)
            QMessageBox.critical(window, "Universal Processing", message)

        window.universal_worker.completed.connect(complete)
        window.universal_worker.failed.connect(failed)
        window.universal_worker.start()

    refresh_ai.clicked.connect(refresh_local_models)
    browse_output.clicked.connect(browse_process_output)
    process_button.clicked.connect(process_project)

    # --- Runtime readiness on Settings -------------------------------------
    settings_page = window.pages.widget(window.page_index["Settings"])
    settings_layout = settings_page.layout()
    runtime_box = QGroupBox("Local processing runtimes")
    runtime_layout = QFormLayout(runtime_box)
    ollama_status = QLabel("Not checked")
    ortho_status = QLabel("Not checked")
    runtime_layout.addRow("Ollama", ollama_status)
    runtime_layout.addRow("Orthomosaic", ortho_status)
    runtime_refresh = QPushButton("Refresh Runtime Status")
    runtime_layout.addRow(runtime_refresh)
    settings_layout.insertWidget(2, runtime_box)

    def refresh_runtime_status():
        provider = OllamaProvider(config.ollama_base_url)
        if provider.available():
            try:
                models = provider.list_models()
                vision = sum(model.supports_vision for model in models)
                ollama_status.setText(
                    f"Ready - {len(models)} model(s), {vision} vision-capable @ {config.ollama_base_url}"
                )
            except Exception as exc:
                ollama_status.setText(f"Reachable, model scan failed: {exc}")
        else:
            ollama_status.setText(f"Not reachable @ {config.ollama_base_url}")
        statuses = OrthomosaicService().status()
        ortho_status.setText(
            ", ".join(
                f"{item['name']}={'ready' if item['available'] else 'unavailable'}"
                for item in statuses
            )
        )

    runtime_refresh.clicked.connect(refresh_runtime_status)
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
