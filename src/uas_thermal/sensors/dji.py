from __future__ import annotations

import os
import sys
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_char,
    c_float,
    c_int32,
    c_uint32,
    c_uint8,
    c_void_p,
    cdll,
    sizeof,
)
from pathlib import Path
from typing import Any

import numpy as np

from ..thermal.calibration import ThermalCalibration
from .base import AdapterUnavailableError, ThermalFrame, ThermalSensorAdapter

DIRP_SUCCESS = 0
DIRP_ERRORS = {
    -1: "memory allocation failed",
    -2: "null pointer",
    -3: "invalid parameters",
    -4: "invalid RAW payload",
    -5: "invalid R-JPEG header",
    -6: "invalid curve LUT",
    -7: "R-JPEG parse failed",
    -8: "buffer size mismatch",
    -9: "invalid handle",
    -10: "invalid input format",
    -11: "invalid output format",
    -12: "unsupported function",
    -13: "runtime not ready",
    -14: "SDK activation failed",
    -15: "invalid SDK ini configuration",
    -16: "invalid dependent DJI DLL",
}

# DJI Thermal SDK dirp_pseudo_color_e values.
DIRP_PSEUDO_COLOR = {
    "WHITEHOT": 0,
    "FULGURITE": 1,
    "IRONRED": 2,
    "HOTIRON": 3,
    "MEDICAL": 4,
    "ARCTIC": 5,
    "RAINBOW1": 6,
    "RAINBOW2": 7,
    "TINT": 8,
    "BLACKHOT": 9,
    # Compatibility alias retained for the legacy UI vocabulary.
    "RAINBOW": 6,
}


class _DirpResolution(Structure):
    _pack_ = 1
    _fields_ = [("width", c_int32), ("height", c_int32)]


class _DirpMeasurementParams(Structure):
    _pack_ = 1
    _fields_ = [
        ("distance", c_float),
        ("humidity", c_float),
        ("emissivity", c_float),
        ("reflection", c_float),
    ]


class _DirpApiVersion(Structure):
    _pack_ = 1
    _fields_ = [("api", c_uint32), ("magic", c_char * 8)]


class DjiDirpAdapter(ThermalSensorAdapter):
    """DJI Thermal SDK adapter for radiometric R-JPEG imagery."""

    name = "dji-dirp"
    vendor = "DJI"
    support_level = "operational-with-sdk"

    _required_symbols = (
        "dirp_create_from_rjpeg",
        "dirp_destroy",
        "dirp_get_rjpeg_resolution",
        "dirp_set_measurement_params",
        "dirp_set_pseudo_color",
        "dirp_measure_ex",
        "dirp_process",
    )

    def __init__(self, palette: str = "IRONRED") -> None:
        self.palette = palette.upper()
        self._dll_handles: list[Any] = []

    def sdk_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if configured := os.environ.get("UAS_THERMAL_DJI_SDK_DIR"):
            candidates.append(Path(configured))
        if bundle_dir := getattr(sys, "_MEIPASS", None):
            candidates.append(Path(bundle_dir))
        candidates.append(Path(sys.executable).resolve().parent)
        candidates.append(Path.cwd())
        candidates.append(Path(__file__).resolve().parents[3])
        unique: list[Path] = []
        for candidate in candidates:
            resolved = candidate.expanduser().resolve()
            if resolved not in unique:
                unique.append(resolved)
        return unique

    def sdk_library(self) -> Path | None:
        for directory in self.sdk_candidates():
            candidate = directory / "libdirp.dll"
            if candidate.is_file():
                return candidate
        return None

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in {".jpg", ".jpeg"} and self.sdk_library() is not None

    @staticmethod
    def _check(ret: int, operation: str) -> None:
        if ret != DIRP_SUCCESS:
            detail = DIRP_ERRORS.get(ret, f"unknown return code {ret}")
            raise AdapterUnavailableError(f"DJI DIRP {operation} failed ({ret}: {detail})")

    def _load_library(self, library_path: Path):
        if hasattr(os, "add_dll_directory"):
            handle = os.add_dll_directory(str(library_path.parent))
            self._dll_handles.append(handle)
        try:
            return cdll.LoadLibrary(str(library_path))
        except OSError as exc:
            raise AdapterUnavailableError(
                f"Unable to load DJI DIRP runtime from {library_path}. "
                "Ensure libdirp.dll and all DJI dependent DLLs from the same SDK release are present."
            ) from exc

    @staticmethod
    def _require_function(lib, name: str):
        try:
            return getattr(lib, name)
        except AttributeError as exc:
            raise AdapterUnavailableError(
                f"DJI DIRP runtime is incompatible: required export {name!r} was not found. "
                "Use a complete DJI Thermal SDK runtime from one matching release."
            ) from exc

    def _bind_runtime(self, lib) -> dict[str, Any]:
        functions = {name: self._require_function(lib, name) for name in self._required_symbols}

        functions["dirp_create_from_rjpeg"].argtypes = [
            POINTER(c_uint8),
            c_int32,
            POINTER(c_void_p),
        ]
        functions["dirp_destroy"].argtypes = [c_void_p]
        functions["dirp_get_rjpeg_resolution"].argtypes = [c_void_p, POINTER(_DirpResolution)]
        functions["dirp_set_measurement_params"].argtypes = [
            c_void_p,
            POINTER(_DirpMeasurementParams),
        ]
        functions["dirp_set_pseudo_color"].argtypes = [c_void_p, c_int32]
        functions["dirp_measure_ex"].argtypes = [c_void_p, POINTER(c_float), c_int32]
        functions["dirp_process"].argtypes = [c_void_p, POINTER(c_uint8), c_int32]
        for function in functions.values():
            function.restype = c_int32
        return functions

    def sdk_diagnostics(self) -> dict[str, Any]:
        """Return non-secret runtime diagnostics without requiring an R-JPEG handle."""
        library_path = self.sdk_library()
        result: dict[str, Any] = {
            "sdk_library": None if library_path is None else str(library_path),
            "sdk_api_version": None,
            "sdk_magic": None,
        }
        if library_path is None:
            return result

        try:
            lib = self._load_library(library_path)
        except AdapterUnavailableError as exc:
            result["sdk_load_error"] = str(exc)
            return result

        get_api_version = getattr(lib, "dirp_get_api_version", None)
        if get_api_version is None:
            result["sdk_api_version_error"] = "dirp_get_api_version export not found"
            return result

        get_api_version.argtypes = [POINTER(_DirpApiVersion)]
        get_api_version.restype = c_int32
        version = _DirpApiVersion()
        ret = int(get_api_version(byref(version)))
        if ret != DIRP_SUCCESS:
            result["sdk_api_version_error"] = DIRP_ERRORS.get(ret, f"return code {ret}")
            return result

        result["sdk_api_version"] = int(version.api)
        result["sdk_magic"] = bytes(version.magic).split(b"\x00", 1)[0].decode(
            "ascii", errors="replace"
        )
        return result

    @staticmethod
    def source_diagnostics(path: Path) -> dict[str, Any]:
        """Return cheap source facts useful when DIRP rejects a JPEG."""
        data = path.read_bytes()
        name = path.name.lower()
        return {
            "file_size_bytes": len(data),
            "jpeg_signature": len(data) >= 4 and data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9",
            "export_like_filename": "_export_" in name or "export-" in name,
        }

    @staticmethod
    def _measurement_params(calibration: ThermalCalibration) -> _DirpMeasurementParams:
        humidity_percent = calibration.relative_humidity * 100.0
        if not 1.0 <= calibration.distance_m <= 25.0:
            raise ValueError("DJI Thermal SDK distance must be between 1 and 25 meters")
        if not 20.0 <= humidity_percent <= 100.0:
            raise ValueError("DJI Thermal SDK humidity must be between 20% and 100%")
        if not -40.0 <= calibration.reflected_temperature_c <= 500.0:
            raise ValueError("DJI Thermal SDK reflected temperature must be between -40 and 500 °C")
        return _DirpMeasurementParams(
            distance=calibration.distance_m,
            humidity=humidity_percent,
            emissivity=calibration.emissivity,
            reflection=calibration.reflected_temperature_c,
        )

    def _palette_code(self) -> int:
        try:
            return DIRP_PSEUDO_COLOR[self.palette]
        except KeyError as exc:
            supported = ", ".join(sorted(DIRP_PSEUDO_COLOR))
            raise ValueError(f"Unsupported DJI palette {self.palette!r}. Supported: {supported}") from exc

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        library_path = self.sdk_library()
        if library_path is None:
            raise AdapterUnavailableError(
                "DJI DIRP runtime not found. Set UAS_THERMAL_DJI_SDK_DIR or place the "
                "vendor runtime beside the packaged application."
            )

        lib = self._load_library(library_path)
        functions = self._bind_runtime(lib)
        measurement = self._measurement_params(calibration)
        palette = self._palette_code()

        jpeg_bytes = path.read_bytes()
        if not jpeg_bytes:
            raise ValueError(f"DJI R-JPEG source is empty: {path}")
        jpeg_buffer = (c_uint8 * len(jpeg_bytes)).from_buffer_copy(jpeg_bytes)
        handle = c_void_p()

        create_ret = int(
            functions["dirp_create_from_rjpeg"](
                jpeg_buffer,
                c_int32(len(jpeg_bytes)),
                byref(handle),
            )
        )
        if create_ret != DIRP_SUCCESS:
            detail = DIRP_ERRORS.get(create_ret, f"unknown return code {create_ret}")
            if create_ret == -7:
                raise AdapterUnavailableError(
                    "DJI DIRP create R-JPEG handle failed (-7: R-JPEG parse failed). "
                    "The runtime loaded correctly but rejected this file as a compatible radiometric "
                    "R-JPEG. Use the original camera R-JPEG rather than an exported/derived JPEG, "
                    "or install a DJI Thermal SDK release compatible with the camera/firmware."
                )
            raise AdapterUnavailableError(
                f"DJI DIRP create R-JPEG handle failed ({create_ret}: {detail})"
            )
        if not handle.value:
            raise AdapterUnavailableError("DJI DIRP created a null R-JPEG handle")

        try:
            resolution = _DirpResolution()
            self._check(
                functions["dirp_get_rjpeg_resolution"](handle, byref(resolution)),
                "get R-JPEG resolution",
            )
            width = int(resolution.width)
            height = int(resolution.height)
            if width <= 0 or height <= 0:
                raise AdapterUnavailableError(
                    f"DJI DIRP returned invalid R-JPEG resolution {width}x{height}"
                )

            self._check(
                functions["dirp_set_measurement_params"](handle, byref(measurement)),
                "set measurement parameters",
            )
            self._check(
                functions["dirp_set_pseudo_color"](handle, c_int32(palette)),
                "set pseudo color",
            )

            pixel_count = width * height
            temp_buffer = (c_float * pixel_count)()
            self._check(
                functions["dirp_measure_ex"](
                    handle,
                    temp_buffer,
                    c_int32(sizeof(temp_buffer)),
                ),
                "measure temperature",
            )
            temperature_c = (
                np.ctypeslib.as_array(temp_buffer)
                .astype(np.float32, copy=True)
                .reshape(height, width)
            )

            rgb_buffer = (c_uint8 * (pixel_count * 3))()
            self._check(
                functions["dirp_process"](
                    handle,
                    rgb_buffer,
                    c_int32(sizeof(rgb_buffer)),
                ),
                "render pseudo-color image",
            )
            display_rgb = np.ctypeslib.as_array(rgb_buffer).reshape(height, width, 3).copy()

            return ThermalFrame(
                temperature_c=temperature_c,
                display_rgb=display_rgb,
                source=path,
                metadata={
                    "vendor": self.vendor,
                    "adapter": self.name,
                    "sdk_library": str(library_path),
                    "sdk_api": "dirp_create_from_rjpeg/dirp_measure_ex",
                    "width": width,
                    "height": height,
                    "palette": self.palette,
                    "calibration": {
                        "emissivity": calibration.emissivity,
                        "distance_m": calibration.distance_m,
                        "relative_humidity": calibration.relative_humidity,
                        "reflected_temperature_c": calibration.reflected_temperature_c,
                    },
                },
            )
        finally:
            if handle.value:
                functions["dirp_destroy"](handle)
