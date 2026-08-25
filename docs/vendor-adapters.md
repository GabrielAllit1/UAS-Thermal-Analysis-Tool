# Sensor adapter policy

UAS Thermal Analysis does not infer radiometric temperature from ordinary display imagery. A vendor is marked supported only when a tested decoder can produce a calibrated Celsius matrix from the source format.

| Adapter | Support | Requirement |
|---|---|---|
| Generic radiometric GeoTIFF | Foundation | Rasterio; source must contain numeric thermal values or explicit scale/offset |
| DJI DIRP | Legacy-compatible boundary | Local DIRP SDK; normalized frame extraction still being migrated |
| FLIR/Teledyne | Contract only | Tested radiometric decoder not yet integrated |
| Autel | Contract only | Tested radiometric decoder not yet integrated |

Future adapters must implement `ThermalSensorAdapter` and pass the same normalized-frame tests.
