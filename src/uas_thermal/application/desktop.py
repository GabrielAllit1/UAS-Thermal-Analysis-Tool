"""Desktop UI boundary.

The legacy PyQt5 desktop remains the production UI during the v0.2 migration.
This module is the stable destination for the replacement UI so application code
can move without coupling thermal algorithms to Qt.
"""


def launch() -> int:
    raise RuntimeError(
        "The modular desktop shell is not enabled yet. Use the legacy root main.py while UI parity is migrated."
    )
