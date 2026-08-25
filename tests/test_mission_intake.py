from pathlib import Path

from uas_thermal.application.mission_intake import infer_profile_id, scan_mission_folder
from uas_thermal.sensors.registry import AdapterRegistry


class _TiffAdapter:
    name = "test-tiff"
    vendor = "test"
    support_level = "operational"

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in {".tif", ".tiff"}


class _ContractOnlyJpeg:
    name = "contract-jpeg"
    vendor = "test"
    support_level = "contract-only"

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in {".jpg", ".jpeg"}


def test_mission_intake_recursively_separates_quantitative_candidates_and_context(tmp_path):
    root = tmp_path / "Solar Farm Alpha"
    nested = root / "flight-001"
    nested.mkdir(parents=True)
    thermal = nested / "thermal_001.tif"
    visible = nested / "visible_001.jpg"
    gis = root / "boundary.kml"
    thermal.write_bytes(b"thermal")
    visible.write_bytes(b"visible")
    gis.write_text("<kml/>", encoding="utf-8")

    intake = scan_mission_folder(
        root,
        registry=AdapterRegistry([_TiffAdapter(), _ContractOnlyJpeg()]),
    )

    assert intake.ready
    assert intake.profile_id == "photovoltaic"
    assert intake.project_name == "Solar Farm Alpha"
    assert intake.analysis_sources == (thermal.resolve(),)
    assert visible.resolve() in intake.context_files
    assert gis.resolve() in intake.context_files
    assert intake.image_count == 2


def test_mission_intake_does_not_promote_contract_only_adapter(tmp_path):
    root = tmp_path / "mission"
    root.mkdir()
    image = root / "thermal.jpg"
    image.write_bytes(b"jpeg")

    intake = scan_mission_folder(root, registry=AdapterRegistry([_ContractOnlyJpeg()]))

    assert intake.analysis_sources == ()
    assert image.resolve() in intake.context_files
    assert not intake.ready


def test_profile_inference_falls_back_to_generic_for_ambiguous_mission(tmp_path):
    source = tmp_path / "mission-001.tif"
    source.write_bytes(b"x")
    assert infer_profile_id(tmp_path, (source,)) == "generic-thermal"
