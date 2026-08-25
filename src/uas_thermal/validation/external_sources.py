from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalValidationSource:
    source_id: str
    title: str
    landing_url: str
    license: str
    redistribution: str
    purpose: tuple[str, ...]
    download_url: str = ""
    checksum_algorithm: str = ""
    checksum: str = ""
    notes: str = ""


SOURCES: tuple[ExternalValidationSource, ...] = (
    ExternalValidationSource(
        source_id="dji-tsdk-v18",
        title="DJI Thermal SDK v1.8 test dataset",
        landing_url="https://enterprise.dji.com/mavic-3-enterprise/downloads",
        license="DJI TSDK License.txt / vendor terms",
        redistribution="Do not redistribute through this repository; obtain directly from DJI.",
        purpose=(
            "DIRP ABI/runtime validation",
            "vendor-supplied R-JPEG decode tests",
            "temperature-matrix parity checks",
        ),
        notes=(
            "DJI states that the TSDK package contains several R-JPEG samples for testing. "
            "Review and accept the bundled License.txt before use."
        ),
    ),
    ExternalValidationSource(
        source_id="kanderfirn-2021",
        title="Kanderfirn UAV infrared thermography dataset",
        landing_url="https://zenodo.org/records/10008937",
        license="CC BY 4.0",
        redistribution="Permitted with attribution; keep the 1.3 GB archive outside the repo.",
        purpose=(
            "radiometric GeoTIFF validation",
            "large-raster tiled analysis",
            "thermal/visible geospatial comparison",
            "in-situ temperature reference comparison",
        ),
        download_url=(
            "https://zenodo.org/records/10008937/files/"
            "Messmer_%26_Groos_2023_The_Cryosphere.zip?download=1"
        ),
        checksum_algorithm="md5",
        checksum="a3e591d3cb2188ebbb97c716ba023391",
        notes=(
            "Includes radiometric FLIR Vue Pro R 640 imagery, radiometric and visual orthophotos, "
            "surface-temperature rasters, EXIF position tables, and in-situ temperature data."
        ),
    ),
    ExternalValidationSource(
        source_id="mavic3t-lithuania-forest",
        title="DJI Mavic 3 Thermal flights over Lithuanian forests #4",
        landing_url="https://zenodo.org/records/17311327",
        license="Not clearly declared on the record page",
        redistribution="Do not redistribute or automate acquisition until rights are reviewed.",
        purpose=(
            "thermal/visible review UX",
            "timestamp/GPS pairing research",
            "Mavic 3 Thermal modality coverage",
        ),
        notes=(
            "The record describes selected JPG thermal/visual images plus MP4/SRT metadata. "
            "Do not assume the JPGs are original radiometric R-JPEG files."
        ),
    ),
)


def get_source(source_id: str) -> ExternalValidationSource:
    for source in SOURCES:
        if source.source_id == source_id:
            return source
    raise KeyError(f"unknown external validation source: {source_id}")
