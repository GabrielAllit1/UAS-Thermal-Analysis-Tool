from uas_thermal.validation.external_sources import SOURCES, get_source


def test_external_validation_sources_have_unique_ids_and_claim_boundaries():
    ids = [source.source_id for source in SOURCES]
    assert len(ids) == len(set(ids))
    assert get_source("dji-tsdk-v18").download_url == ""
    kanderfirn = get_source("kanderfirn-2021")
    assert kanderfirn.license == "CC BY 4.0"
    assert kanderfirn.checksum_algorithm == "md5"
    assert len(kanderfirn.checksum) == 32
