from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class InspectionProfile:
    profile_id: str
    name: str
    version: str = "1.0"
    minimum_delta_c: float = 8.0
    minimum_area_px: int = 25
    moderate_delta_c: float = 15.0
    critical_delta_c: float = 30.0
    absolute_threshold_c: float | None = None
    local_radii: tuple[int, ...] = (3, 7)
    minimum_scale_support: int = 1
    robust_z_threshold: float = 3.5
    edge_suppression: bool = True
    recommendation_minor: str = "Document and monitor during the next inspection cycle."
    recommendation_moderate: str = "Schedule targeted field inspection and trend the condition."
    recommendation_critical: str = "Prioritize field verification and corrective inspection."
    finding_label: str = "Thermal anomaly"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_PROFILES = {
    "generic-thermal": InspectionProfile("generic-thermal", "Generic Thermal Survey"),
    "electrical": InspectionProfile(
        "electrical",
        "Electrical",
        minimum_delta_c=6.0,
        moderate_delta_c=15.0,
        critical_delta_c=30.0,
        finding_label="Electrical thermal anomaly",
        recommendation_moderate="Inspect the associated electrical component and compare loading/phase conditions.",
        recommendation_critical="Prioritize electrical field verification and corrective action under an appropriate safety procedure.",
    ),
    "photovoltaic": InspectionProfile(
        "photovoltaic",
        "Photovoltaic",
        minimum_delta_c=5.0,
        minimum_area_px=16,
        moderate_delta_c=10.0,
        critical_delta_c=20.0,
        finding_label="PV thermal anomaly",
        recommendation_moderate="Inspect the affected module/string and correlate with electrical performance data where available.",
        recommendation_critical="Prioritize verification of the affected PV component and associated electrical connections.",
    ),
    "roof-envelope": InspectionProfile(
        "roof-envelope",
        "Roof / Building Envelope",
        minimum_delta_c=4.0,
        minimum_area_px=40,
        moderate_delta_c=8.0,
        critical_delta_c=15.0,
        finding_label="Building-envelope thermal anomaly",
        recommendation_moderate="Correlate the thermal pattern with roof/envelope construction and moisture verification methods.",
        recommendation_critical="Prioritize field investigation of the affected envelope area before repair decisions.",
    ),
    "mechanical": InspectionProfile(
        "mechanical",
        "Mechanical",
        minimum_delta_c=7.0,
        moderate_delta_c=15.0,
        critical_delta_c=30.0,
        finding_label="Mechanical thermal anomaly",
        recommendation_moderate="Inspect the associated mechanical component and compare against similar equipment under comparable load.",
    ),
    "pipeline": InspectionProfile(
        "pipeline",
        "Pipeline / Linear Infrastructure",
        minimum_delta_c=5.0,
        minimum_area_px=30,
        moderate_delta_c=12.0,
        critical_delta_c=25.0,
        finding_label="Linear-infrastructure thermal anomaly",
        recommendation_moderate="Inspect the localized condition and correlate with process state and adjacent segments.",
    ),
}


def get_profile(profile_id: str | None = None) -> InspectionProfile:
    key = (profile_id or "generic-thermal").strip().lower()
    if key not in _PROFILES:
        raise KeyError(f"unknown inspection profile: {profile_id!r}")
    return _PROFILES[key]


def available_profiles() -> tuple[InspectionProfile, ...]:
    return tuple(_PROFILES.values())
