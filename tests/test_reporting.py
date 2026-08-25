import csv
import xml.etree.ElementTree as ET

from uas_thermal.inspections.models import Finding, InspectionResult, Severity
from uas_thermal.reporting.csv_report import write_csv
from uas_thermal.reporting.kml_report import write_kml
from uas_thermal.thermal.statistics import TemperatureStatistics


def result_fixture():
    stats = TemperatureStatistics(20, 50, 25, 22, 2, 30, 100)
    finding = Finding(
        10,
        20,
        50,
        50,
        45,
        20,
        30,
        Severity.CRITICAL,
        latitude=28.0,
        longitude=-82.0,
    )
    return InspectionResult(
        "thermal.tif",
        "generic-geotiff",
        stats,
        [finding],
        project={"name": "Demo", "site": "Site A", "client": "Owner"},
    )


def test_csv_contains_project_context(tmp_path):
    path = write_csv(result_fixture(), tmp_path / "report.csv")
    with path.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["project_name"] == "Demo"
    assert row["site"] == "Site A"
    assert row["adapter"] == "generic-geotiff"


def test_kml_uses_project_name(tmp_path):
    path = write_kml(result_fixture(), tmp_path / "report.kml")
    root = ET.parse(path).getroot()
    namespace = {"k": "http://www.opengis.net/kml/2.2"}
    assert root.find(".//k:name", namespace).text == "Demo"
