from __future__ import annotations

from .models import Finding, Severity


def maintenance_recommendation(finding: Finding) -> str:
    if finding.severity is Severity.CRITICAL:
        return "Prioritize field verification and corrective inspection."
    if finding.severity is Severity.MODERATE:
        return "Schedule targeted inspection, compare adjacent assets, and trend the finding over time."
    return "Document and monitor the finding; re-evaluate during the next inspection cycle."
