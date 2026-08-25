from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from uas_thermal.application.desktop import launch


app = QApplication.instance() or QApplication([])
QTimer.singleShot(250, app.quit)
raise SystemExit(launch())
