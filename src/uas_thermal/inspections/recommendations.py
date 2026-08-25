from __future__ import annotations

from .models import Finding, Severity
from .profiles import InspectionProfile


def maintenance_recommendation(
    finding: Finding,
    profile: InspectionProfile | None = None,
) -> str:
    if profile is not None:
        if finding.severity is Severity.CRITICAL:
            return profile.recommendation_critical
        if finding.severity is Severity.MODERATE:
            return profile.recommendation_moderate
        return profile.recommendation_minor
    if finding.severity is Severity.CRITICAL:
        return "Prioritize field verification and corrective inspection."
    if finding.severity is Severity.MODERATE:
        return "Schedule targeted inspection, compare adjacent assets, and trend the finding over time."
    return "Document and monitor the finding; re-evaluate during the next inspection cycle."
