from uas_thermal.cli import build_parser


def test_process_parser_defaults_and_local_ai_option():
    args = build_parser().parse_args(
        [
            "process",
            "thermal_a.tif",
            "thermal_b.tif",
            "--output-dir",
            "out",
            "--profile",
            "construction",
            "--stitch",
            "on",
            "--orthomosaic-backend",
            "native-geotiff",
            "--ai",
            "auto",
            "--palette",
            "ironbow",
            "--span-c",
            "20",
            "--level-c",
            "40",
        ]
    )

    assert args.command == "process"
    assert args.profile == "construction"
    assert args.stitch == "on"
    assert args.orthomosaic_backend == "native-geotiff"
    assert args.ai == "auto"
    assert args.span_c == 20.0
    assert args.level_c == 40.0


def test_runtime_status_commands_are_registered():
    parser = build_parser()
    assert parser.parse_args(["ai-models"]).command == "ai-models"
    assert parser.parse_args(["orthomosaic-status"]).command == "orthomosaic-status"
