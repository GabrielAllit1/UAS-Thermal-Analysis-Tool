import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QPushButton, QScrollArea

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.workspace_ui_v8 import create_workspace_window


def test_frontier_workspace_fits_laptop_width_without_horizontal_overflow():
    app, window = create_workspace_window(DesktopSession())
    window.resize(1024, 600)
    window.show()
    app.processEvents()

    assert window.minimumWidth() <= 880
    assert window.minimumHeight() <= 540
    assert window.nav.maximumWidth() <= 168
    assert not window.inspector.isVisible()

    scroll = window.findChild(QScrollArea, "autopilotScroll")
    assert scroll is not None
    assert scroll.widgetResizable()
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert scroll.widget().minimumWidth() == 0

    hero = window.findChild(QFrame, "missionLaunchCard")
    assert hero is not None and hero.isVisible()
    legacy = window.findChild(QFrame, "startMissionCard")
    assert legacy is not None and not legacy.isVisible()

    primary = window.findChild(QPushButton, "frontierPrimary")
    demo = window.findChild(QPushButton, "frontierDemo")
    assert primary is not None and primary.text() == "PROCESS FLIGHT FOLDER"
    assert demo is not None and demo.text() == "RUN GUIDED DEMO"

    if hasattr(window, "runtime_monitor"):
        window.runtime_monitor.close()
    window.close()
    app.processEvents()
