"""Licensing boundary.

The legacy HMAC implementation is intentionally not duplicated here. Future
production licensing should verify asymmetric signatures using a public key in
the client while private signing material remains offline.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LicenseStatus:
    valid: bool
    reason: str


def migration_status() -> LicenseStatus:
    return LicenseStatus(False, "asymmetric license verification migration not configured")
