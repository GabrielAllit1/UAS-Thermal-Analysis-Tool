import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QGroupBox, QPushButton

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.workspace_ui_v6 import create_workspace_window


def test_one_click_workspace_makes_folder_intake_the_primary_path():
    app, window = create_workspace_window(DesktopSession())
    app.processEvents()

    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    assert "SELECT FLIGHT FOLDER & RUN AUTOPILOT" in buttons
    assert "Select mission files instead" in buttons
    assert "Advanced controls" in buttons

    manual = next(
        box for box in window.findChildren(QGroupBox) if box.title() == "Autonomous mission plan"
    )
    assert not manual.isVisible()
    assert window.page_index["Autopilot"] == 0

    window.runtime_monitor.close()
    window.close()
    app.processEvents()
