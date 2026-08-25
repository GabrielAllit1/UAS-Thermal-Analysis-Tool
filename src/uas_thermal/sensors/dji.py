from __future__ import annotations

import os
import sys
from ctypes import byref, c_float, c_int, c_int16, c_uint8, c_uint32, c_void_p, cdll
from pathlib import Path
from typing import Any

import numpy as np

from ..thermal.calibration import ThermalCalibration
from .base import AdapterUnavailableError, ThermalFrame, ThermalSensorAdapter

DIRP_SUCCESS = 0
DIRP_PSEUDO_COLOR = {
    "WHITEHOT": 0,
    "BLACKHOT": 1,
    "IRONRED": 2,
    "RAINBOW": 3,
    "MEDICAL": 4,
    "ARCTIC": 5,
    "TYRIAN": 6,
    "GLOWBOW": 7,
}


class DjiDirpAdapter(ThermalSensorAdapter):
    """DJI DIRP adapter migrated from the proven legacy decoder."""

    name = "dji-dirp"
    vendor = "DJI"
    support_level = "operational-with-sdk"

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
            raise AdapterUnavailableError(f"DJI DIRP {operation} failed with return code {ret}")

    def _load_library(self, library_path: Path):
        if hasattr(os, "add_dll_directory"):
            handle = os.add_dll_directory(str(library_path.parent))
            self._dll_handles.append(handle)
        try:
            return cdll.LoadLibrary(str(library_path))
        except OSError as exc:
            raise AdapterUnavailableError(
                f"Unable to load DJI DIRP runtime from {library_path}. Ensure all vendor DLL dependencies are present."
            ) from exc

    @staticmethod
    def _dimensions(path: Path) -> tuple[int, int]:
        try:
            import cv2
        except ImportError as exc:
            raise AdapterUnavailableError("Install the dji extra to decode DJI R-JPEG files") from exc
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Unable to read JPEG dimensions: {path}")
        height, width = image.shape[:2]
        return width, height

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        library_path = self.sdk_library()
        if library_path is None:
            raise AdapterUnavailableError(
                "DJI DIRP runtime not found. Set UAS_THERMAL_DJI_SDK_DIR or place the vendor runtime beside the packaged application."
            )
        lib = self._load_library(library_path)
        width, height = self._dimensions(path)
        jpeg_bytes = path.read_bytes()
        jpeg_buffer = (c_uint8 * len(jpeg_bytes)).from_buffer_copy(jpeg_bytes)
        handle = c_void_p()
        self._check(lib.dirp_create(byref(handle)), "dirp_create")
        try:
            self._check(lib.dirp_set_emissivity(handle, c_float(calibration.emissivity)), "set emissivity")
            self._check(lib.dirp_set_distance(handle, c_float(calibration.distance_m)), "set distance")
            self._check(
                lib.dirp_set_humidity(handle, c_float(calibration.relative_humidity)),
                "set humidity",
            )
            self._check(
                lib.dirp_set_reflected_temperature(
                    handle,
                    c_float(calibration.reflected_temperature_c),
                ),
                "set reflected temperature",
            )
            self._check(lib.dirp_process(handle, jpeg_buffer, c_uint32(len(jpeg_bytes))), "process")

            temp_buffer = (c_int16 * (width * height))()
            self._check(
                lib.dirp_get_temperature_data(handle, temp_buffer, c_int(width * height)),
                "get temperature data",
            )
            temperature_c = (
                np.ctypeslib.as_array(temp_buffer).astype(np.float32).reshape(height, width) / 10.0
            )

            rgb_buffer = (c_uint8 * (width * height * 3))()
            palette = DIRP_PSEUDO_COLOR.get(self.palette, DIRP_PSEUDO_COLOR["IRONRED"])
            self._check(
                lib.dirp_get_thermal_image(handle, rgb_buffer, c_int(palette), c_int(0)),
                "get thermal image",
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
                lib.dirp_destroy(handle)
