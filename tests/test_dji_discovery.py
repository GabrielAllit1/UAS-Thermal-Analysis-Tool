from uas_thermal.sensors.dji import DjiDirpAdapter


def test_dji_sdk_discovery_uses_environment(monkeypatch, tmp_path):
    library = tmp_path / "libdirp.dll"
    library.write_bytes(b"placeholder")
    monkeypatch.setenv("UAS_THERMAL_DJI_SDK_DIR", str(tmp_path))
    adapter = DjiDirpAdapter()
    assert adapter.sdk_library() == library
    assert all("GAllit" not in str(candidate) for candidate in adapter.sdk_candidates())
