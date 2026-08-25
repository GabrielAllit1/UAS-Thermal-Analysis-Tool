from pathlib import Path

from uas_thermal.sensors.registry import default_registry


def test_registry_prefers_generic_geotiff_for_tiff():
    adapter = default_registry().select(Path("thermal.tif"))
    assert adapter.name == "generic-geotiff"
