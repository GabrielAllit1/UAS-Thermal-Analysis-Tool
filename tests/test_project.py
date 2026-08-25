from uas_thermal.application.projects import Project


def test_project_report_metadata_is_vendor_neutral():
    project = Project(
        name="Solar inspection",
        site="Site A",
        client="Owner",
        sensor_vendor="FLIR / Teledyne",
        sensor_model="Example",
    )
    metadata = project.report_metadata()
    assert metadata["name"] == "Solar inspection"
    assert metadata["site"] == "Site A"
    assert metadata["sensor_vendor"] == "FLIR / Teledyne"
    assert "DJI" not in str(metadata)
