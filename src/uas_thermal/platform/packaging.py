from __future__ import annotations

from pathlib import Path


VENDOR_BINARY_PATTERNS = ("*.dll", "*.lib")


def validate_release_tree(root: str | Path) -> list[Path]:
    """Return disallowed source-tree artifacts that should not be committed/released accidentally."""
    base = Path(root)
    blocked: list[Path] = []
    for pattern in VENDOR_BINARY_PATTERNS:
        blocked.extend(base.rglob(pattern))
    blocked.extend(base.rglob("secure_key.dat"))
    blocked.extend(base.rglob("license_key_log.csv"))
    return blocked
