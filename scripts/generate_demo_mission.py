from __future__ import annotations

import argparse
from pathlib import Path

from uas_thermal.validation.demo_mission import materialize_demo_mission


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the bundled synthetic Solar Farm Demo mission."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Parent directory for Solar_Farm_Demo; default is the application data directory.",
    )
    args = parser.parse_args()
    root = materialize_demo_mission(args.output_dir)
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
