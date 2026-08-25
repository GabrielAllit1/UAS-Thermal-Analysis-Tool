from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from uas_thermal.application.desktop import DesktopSession
from uas_thermal.application.workspace_ui_v4 import create_workspace_window


SIZES = ((1280, 720), (1440, 900), (1920, 1080))
PAGES = ("Autopilot", "Overview", "Explore", "Process", "Measurements")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("build/ui-qa"))
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    app, window = create_workspace_window(DesktopSession())
    window.show()
    for width, height in SIZES:
        window.resize(width, height)
        for page in PAGES:
            index = window.page_index[page]
            window.nav.setCurrentRow(index)
            app.processEvents()
            destination = args.output_dir / f"{page.lower()}-{width}x{height}.png"
            if not window.grab().save(str(destination), "PNG"):
                raise RuntimeError(f"failed to capture {destination}")
            if destination.stat().st_size <= 0:
                raise RuntimeError(f"empty visual QA capture: {destination}")
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
