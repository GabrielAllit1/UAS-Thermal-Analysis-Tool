# External validation datasets

The repository does not commit customer inspection data, vendor SDK binaries, or large third-party datasets. External validation fixtures are acquired locally and referenced through environment variables or explicit paths.

## DJI Thermal SDK v1.8 test dataset

Official source: <https://enterprise.dji.com/mavic-3-enterprise/downloads>

DJI describes the Thermal SDK as a Windows/Linux SDK for processing R-JPEG infrared images and temperature measurements. The current Mavic 3 Enterprise download page lists TSDK v1.8 and states that the package includes `License.txt`, API documentation, sample build scripts, and a `dataset` containing several R-JPEG samples for testing.

Use this source for:

- proving the installed DIRP runtime can create handles from vendor-supplied R-JPEGs;
- validating image dimensions, finite temperature matrices, palette rendering, and calibration parameter handling;
- comparing application output against DJI's own tools/test utilities where an authoritative expected result is available.

Do **not** copy DJI SDK binaries or test images into this repository. Download the SDK directly from DJI, review/accept `License.txt`, keep it outside source control, and point local tests at the extracted fixture directory.

This source validates the DJI runtime boundary. It does not by itself prove field anomaly-detection accuracy or thermographer-equivalent diagnosis.

## Kanderfirn UAV infrared thermography dataset

Source: <https://zenodo.org/records/10008937>

DOI: `10.5281/zenodo.10008937`

License: CC BY 4.0. Attribution is required.

The archive includes visual and thermal UAV imagery, FLIR Vue Pro R 640 radiometric thermal images, visual and radiometric thermal orthophotos, surface-temperature rasters in Celsius, EXIF position tables, emissivity maps, and in-situ temperature measurements. The Zenodo archive is approximately 1.3 GB and publishes MD5 `a3e591d3cb2188ebbb97c716ba023391`.

Use this source for:

- quantitative GeoTIFF adapter validation;
- full-raster versus tiled-analysis parity on manageable subsets;
- very-large-raster bounded-memory testing;
- CRS/affine finding projection;
- thermal/visible geospatial review;
- comparison of mapped temperatures with supplied in-situ measurements.

The archive should remain in a local validation-data directory rather than Git. CC BY 4.0 permits reuse with attribution, but the repository should avoid carrying a 1.3 GB fixture.

## DJI Mavic 3 Thermal Lithuanian forest dataset

Source: <https://zenodo.org/records/17311327>

DOI: `10.5281/zenodo.17311327`

The record describes Mavic 3 Thermal visual/thermal data, including MP4, SRT metadata and selected JPG thermal/visual images. It is useful for thermal-visible review, synchronized metadata experiments, and Mavic 3 Thermal modality coverage.

The record page does not clearly declare a reusable license. Do not redistribute it or make it an automated dependency until rights are confirmed. The selected JPGs are also not assumed to be original radiometric R-JPEG files; they must pass the radiometric source gate before any quantitative claim.

## Claim boundary

External fixtures are evidence, not certification. A release may claim a decoder or tiled workflow passed a named fixture only when the fixture, software version, calibration assumptions, expected values, tolerances, and test output are recorded. Field detection accuracy requires representative labeled inspections or controlled ground truth. Thermographer equivalence requires a separate professionally designed validation program and is not inferred from software test coverage.
