from __future__ import annotations

from pathlib import Path
import re
import unicodedata


VENDOR_BINARY_PATTERNS = ("*.dll", "*.lib")
SENSITIVE_FILE_NAMES = (
    "secure_key.dat",
    "license_data.dat",
    "last_check.dat",
    "license_key_log.csv",
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    "id_rsa",
    "id_ed25519",
)
SENSITIVE_FILE_PATTERNS = ("*.pem", "*.key", "*.p12", "*.pfx")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_path_component(value: object, *, fallback: str = "inspection", max_length: int = 120) -> str:
    """Return one cross-platform filesystem component without changing source metadata.

    User-entered project and inspection identifiers are metadata, not trusted path fragments. This
    helper strips path traversal, Windows-reserved characters/names, control characters and trailing
    dot/space semantics while keeping a readable deterministic component for generated packages.
    """

    if max_length <= 0:
        raise ValueError("max_length must be positive")
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip()
    normalized = _INVALID_PATH_CHARS.sub("_", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    normalized = re.sub(r"_+", "_", normalized)
    if normalized in {"", ".", ".."}:
        normalized = fallback

    stem = normalized.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        normalized = f"_{normalized}"

    normalized = normalized[:max_length].rstrip(" .")
    return normalized or fallback


def validate_release_tree(root: str | Path) -> list[Path]:
    """Return source-tree artifacts that must not be committed or shipped accidentally."""

    base = Path(root)
    blocked: set[Path] = set()
    for pattern in VENDOR_BINARY_PATTERNS:
        blocked.update(base.rglob(pattern))
    for name in SENSITIVE_FILE_NAMES:
        blocked.update(path for path in base.rglob(name) if path.is_file())
    for pattern in SENSITIVE_FILE_PATTERNS:
        blocked.update(path for path in base.rglob(pattern) if path.is_file())
    return sorted(blocked)
