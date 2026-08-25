from uas_thermal.inspections.profiles import available_profiles, get_profile


def test_initial_profiles_are_versioned_and_share_one_contract():
    profiles = available_profiles()
    assert {item.profile_id for item in profiles} >= {
        "generic-thermal",
        "electrical",
        "photovoltaic",
        "roof-envelope",
        "mechanical",
        "pipeline",
    }
    assert all(item.version for item in profiles)
    assert get_profile("electrical").critical_delta_c > get_profile("electrical").moderate_delta_c
