from __future__ import annotations

from datetime import UTC, datetime

from .models import Finding, FindingStatus


def transition_finding(
    finding: Finding,
    status: FindingStatus,
    *,
    actor: str = "user",
    note: str = "",
) -> Finding:
    """Update operational state without mutating algorithmic evidence."""

    previous = finding.lifecycle_status
    if previous is status:
        return finding
    timestamp = datetime.now(UTC).isoformat()
    finding.audit_trail.append(
        {
            "timestamp": timestamp,
            "actor": actor,
            "event": "lifecycle_status_changed",
            "from": previous.value,
            "to": status.value,
            "note": note,
        }
    )
    finding.lifecycle_status = status
    finding.updated_at = timestamp
    return finding
