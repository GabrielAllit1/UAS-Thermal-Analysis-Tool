from __future__ import annotations


def create_workspace_window(session):
    """Apply the final responsive composition rules to the v0.12 consumer workspace.

    v9 owns the three-state Home experience. This thin layer corrects the last Windows visual-QA
    defect: two side-by-side launch actions can exceed the available content width once the navigation
    rail and scrollbar are present on 1024px-class displays. The actions are intentionally stacked so
    the primary workflow remains obvious and fully visible at every supported width.
    """

    from PyQt5.QtWidgets import QFrame, QLabel, QPushButton

    from .workspace_ui_v9 import create_workspace_window as create_v9_workspace

    app, window = create_v9_workspace(session)

    launch = window.findChild(QFrame, "launchSurface")
    if launch is None or launch.layout() is None:
        raise RuntimeError("Consumer mission launch surface is incomplete")

    launch_buttons = launch.findChildren(QPushButton)
    primary = next(
        (button for button in launch_buttons if button.text() == "Choose mission folder"),
        None,
    )
    secondary = next(
        (button for button in launch_buttons if button.text() == "Run guided example"),
        None,
    )
    if primary is None or secondary is None:
        raise RuntimeError("Consumer mission launch actions are incomplete")

    layout = launch.layout()
    layout.removeWidget(primary)
    layout.removeWidget(secondary)
    layout.addWidget(primary, 1, 0, 1, 2)
    layout.addWidget(secondary, 2, 0, 1, 2)

    # Keep the local-first trust line below both actions after recomposition.
    trust = next(
        (label for label in launch.findChildren(QLabel) if label.objectName() == "trustLine"),
        None,
    )
    if trust is not None:
        layout.removeWidget(trust)
        layout.addWidget(trust, 3, 0, 1, 2)

    primary.setMinimumWidth(0)
    secondary.setMinimumWidth(0)
    window.consumer_launch_actions_stacked = True
    return app, window


def launch_workspace(session) -> int:
    app, window = create_workspace_window(session)
    window.show()
    return app.exec_()
