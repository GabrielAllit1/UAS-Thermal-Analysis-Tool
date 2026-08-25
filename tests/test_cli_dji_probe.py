from __future__ import annotations

import json
from pathlib import Path

from uas_thermal.cli import build_parser, main


def test_dji_probe_parser_defaults() -> None:
    args = build_parser().parse_args(["dji-probe", "sample.jpg"])
    assert args.command == "dji-probe"
    assert args.source == Path("sample.jpg")
    assert args.emissivity == 0.95
    assert args.distance_m == 5.0
    assert args.humidity == 0.50
    assert args.reflected_c == 20.0
    assert args.palette == "IRONRED"


def test_dji_probe_missing_source_returns_machine_readable_error(tmp_path, capsys) -> None:
    missing = tmp_path / "missing.jpg"
    assert main(["dji-probe", str(missing)]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["ok"] is False
    assert "source not found" in payload["error"]
