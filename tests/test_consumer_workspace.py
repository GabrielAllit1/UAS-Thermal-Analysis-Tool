import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.workspace_ui_v10 import create_workspace_window


def _close(app, window):
    if hasattr(window, "runtime_monitor"):
        window.runtime_monitor.close()
    window.close()
    app.processEvents()


def test_consumer_home_is_simple_and_laptop_safe():
    app, window = create_workspace_window(DesktopSession())
    window.resize(1024, 600)
    window.show()
    app.processEvents()

    assert window.nav.item(window.page_index["Autopilot"]).text() == "Home"
    assert window.nav.item(window.page_index["Analyze"]).isHidden()
    assert window.nav.item(window.page_index["Processing"]).isHidden()
    assert window.nav.item(window.page_index["Measurements"]).isHidden()
    assert not window.inspector.isVisible()

    scroll = window.findChild(QScrollArea, "consumerHomeScroll")
    assert scroll is not None
    assert scroll.widgetResizable()
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert scroll.widget().minimumWidth() == 0

    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    assert "Choose mission folder" in buttons
    assert "Run guided example" in buttons
    assert "Advanced tools" in buttons

    launch = window.findChild(QFrame, "launchSurface")
    assert launch is not None
    assert window.consumer_launch_actions_stacked is True
    primary = buttons["Choose mission folder"]
    secondary = buttons["Run guided example"]
    assert primary.geometry().left() == secondary.geometry().left()
    assert primary.geometry().right() <= launch.contentsRect().right()
    assert secondary.geometry().right() <= launch.contentsRect().right()

    _close(app, window)


def test_consumer_result_prioritizes_visual_evidence_and_deliverables(tmp_path):
    app, window = create_workspace_window(DesktopSession())
    root = tmp_path / "deliverable"
    preview = root / "maps" / "annotated_thermal_overview.png"
    preview.parent.mkdir(parents=True)
    image = QImage(640, 360, QImage.Format_RGB32)
    image.fill(0x102030)
    assert image.save(str(preview), "PNG")
    (root / "report").mkdir()
    (root / "viewer").mkdir()
    (root / "report" / "inspection_report.pdf").write_bytes(b"%PDF-demo")
    (root / "viewer" / "index.html").write_text("<html></html>", encoding="utf-8")

    findings = [
        SimpleNamespace(severity=SimpleNamespace(value="critical")),
        SimpleNamespace(severity=SimpleNamespace(value="moderate")),
        SimpleNamespace(severity=SimpleNamespace(value="minor")),
    ]
    result = SimpleNamespace(
        deliverable_dir=root,
        run=SimpleNamespace(canonical_findings=findings),
    )
    window.present_consumer_result(result)
    window.resize(1366, 768)
    window.show()
    app.processEvents()

    assert window.consumer_home_stack.currentWidget() is window.consumer_complete_page
    total = window.findChild(QLabel, "findingTotal")
    assert total is not None and total.text() == "3"
    result_image = window.findChild(QLabel, "resultImage")
    assert result_image is not None and result_image.pixmap() is not None

    visible_buttons = {button.text() for button in window.findChildren(QPushButton) if button.isVisible()}
    assert "Review findings" in visible_buttons
    assert "Open inspection report" in visible_buttons
    assert "Open client viewer" in visible_buttons
    assert "Open deliverable folder" in visible_buttons

    _close(app, window)
