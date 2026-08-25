import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QFrame, QPushButton

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.workspace_ui_v5 import create_workspace_window


def test_frontier_workspace_promotes_autopilot_and_retires_blocking_refresh_copy():
    app, window = create_workspace_window(DesktopSession())
    app.processEvents()

    assert window.page_index["Autopilot"] == 0
    assert window.nav.item(0).text() == "AUTOPILOT"
    assert window.findChild(QFrame, "commandBar") is not None

    button_texts = {button.text() for button in window.findChildren(QPushButton)}
    assert "Refresh Runtime Status" not in button_texts
    assert "Refresh Local Models" not in button_texts
    assert "Scan Local Stack" not in button_texts
    assert "Rescan now" in button_texts

    window.runtime_monitor.close()
    window.close()
    app.processEvents()
