import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QPushButton

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.workspace_ui_v7 import create_workspace_window


def test_demo_action_is_exposed_on_primary_autopilot_screen():
    app, window = create_workspace_window(DesktopSession())
    app.processEvents()

    assert window.page_index["Autopilot"] == 0
    texts = {button.text() for button in window.findChildren(QPushButton)}
    assert "SELECT FLIGHT FOLDER & RUN AUTOPILOT" in texts
    assert "RUN BUNDLED DEMO" in texts
    assert window.demo_mission_button.isEnabled()

    window.runtime_monitor.close()
    window.close()
    app.processEvents()
