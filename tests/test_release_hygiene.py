from pathlib import Path

from uas_thermal.platform.packaging import safe_path_component, validate_release_tree


def test_repository_release_tree_contains_no_blocked_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    assert validate_release_tree(root) == []


def test_release_hygiene_detects_sensitive_files_and_vendor_binaries(tmp_path) -> None:
    (tmp_path / "secure_key.dat").write_text("secret", encoding="utf-8")
    (tmp_path / ".env.production").write_text("TOKEN=secret", encoding="utf-8")
    (tmp_path / "private.pem").write_text("secret", encoding="utf-8")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "dirp.dll").write_bytes(b"binary")

    blocked = {path.relative_to(tmp_path).as_posix() for path in validate_release_tree(tmp_path)}

    assert blocked == {
        ".env.production",
        "private.pem",
        "secure_key.dat",
        "vendor/dirp.dll",
    }


def test_safe_path_component_blocks_traversal_invalid_and_reserved_names() -> None:
    assert safe_path_component("../../inspection:01?*") == "inspection_01"
    assert safe_path_component("CON") == "_CON"
    assert safe_path_component("  client   survey  ") == "client survey"
    assert safe_path_component("...") == "inspection"
