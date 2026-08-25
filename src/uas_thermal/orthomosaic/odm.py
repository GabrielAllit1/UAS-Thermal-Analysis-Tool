from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from ..sensors.base import AdapterUnavailableError
from ..sensors.generic import GenericGeoTiffAdapter
from .base import OrthomosaicBackend, OrthomosaicRequest, OrthomosaicResult


class OpenDroneMapBackend(OrthomosaicBackend):
    """Optional local OpenDroneMap adapter for thermal photogrammetry.

    No executable, container, model, or dataset is downloaded automatically. The caller must install
    and configure an authorized ODM runtime. Quantitative status is granted only after the generated
    raster passes the application's radiometric adapter gate.
    """

    name = "opendronemap"

    def __init__(self, command: str | tuple[str, ...] | None = None):
        configured = command or os.environ.get("UAS_THERMAL_ODM_COMMAND", "")
        if isinstance(configured, str):
            self.command = tuple(shlex.split(configured)) if configured.strip() else ()
        else:
            self.command = tuple(configured)
        if not self.command:
            executable = shutil.which("odm")
            self.command = (executable,) if executable else ()

    def available(self) -> bool:
        if not self.command:
            return False
        executable = self.command[0]
        return Path(executable).is_file() or shutil.which(executable) is not None

    def can_process(self, request: OrthomosaicRequest) -> bool:
        supported = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
        return len(request.sources) >= 2 and all(path.suffix.lower() in supported for path in request.sources)

    @staticmethod
    def _stage_sources(sources: tuple[Path, ...], images_dir: Path) -> None:
        images_dir.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(sources):
            if not source.is_file():
                raise FileNotFoundError(source)
            destination = images_dir / f"{index:06d}_{source.name}"
            if destination.exists():
                continue
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)

    def process(self, request: OrthomosaicRequest) -> OrthomosaicResult:
        if not self.available():
            raise AdapterUnavailableError(
                "OpenDroneMap is not configured. Install ODM locally and set UAS_THERMAL_ODM_COMMAND "
                "to its command; the application never downloads or starts an unapproved runtime."
            )
        if not self.can_process(request):
            raise AdapterUnavailableError("OpenDroneMap thermal processing requires at least two image sources")
        if request.calibration_mode not in {"camera", "camera+sun"}:
            raise ValueError("thermal ODM processing requires camera or camera+sun radiometric calibration")

        request.output_dir.mkdir(parents=True, exist_ok=True)
        workspace = request.output_dir / "odm-workspace"
        dataset_name = "thermal"
        dataset = workspace / dataset_name
        self._stage_sources(request.sources, dataset / "images")

        command = [
            *self.command,
            "--project-path",
            str(workspace),
            dataset_name,
            "--radiometric-calibration",
            request.calibration_mode,
        ]
        if request.resolution is not None:
            command.extend(["--orthophoto-resolution", str(float(request.resolution))])
        completed = subprocess.run(
            command,
            cwd=request.output_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=None,
        )
        report_path = request.output_dir / "odm_processing.json"
        output_path = dataset / "odm_orthophoto" / "odm_orthophoto.tif"
        report = {
            "backend": self.name,
            "command": command,
            "returncode": completed.returncode,
            "source_count": len(request.sources),
            "calibration_mode": request.calibration_mode,
            "stdout_tail": completed.stdout[-12000:],
            "stderr_tail": completed.stderr[-12000:],
            "output": str(output_path),
        }
        if completed.returncode != 0 or not output_path.is_file():
            report["quantitative"] = False
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise RuntimeError(
                f"OpenDroneMap thermal processing failed (exit {completed.returncode}); "
                f"see {report_path}"
            )

        adapter = GenericGeoTiffAdapter()
        try:
            diagnostics = adapter.source_diagnostics(output_path)
            _, encoding = adapter.sample_temperature(output_path)
        except Exception as exc:
            report["quantitative"] = False
            report["validation_error"] = str(exc)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise AdapterUnavailableError(
                "ODM produced an orthophoto, but it did not pass the quantitative radiometric gate"
            ) from exc
        if not diagnostics.get("radiometric_candidate"):
            raise AdapterUnavailableError("ODM orthophoto was classified as display-only")

        final_path = request.output_dir / "thermal_orthomosaic.tif"
        if final_path.resolve() != output_path.resolve():
            shutil.copy2(output_path, final_path)
        report.update(
            {
                "quantitative": True,
                "validated_output": str(final_path),
                "diagnostics": diagnostics,
                "encoding": encoding,
                "claim_boundary": (
                    "Successful ODM processing proves this configured source/runtime path only. "
                    "It does not establish universal camera compatibility or field detection accuracy."
                ),
            }
        )
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return OrthomosaicResult(
            orthomosaic=final_path,
            backend=self.name,
            quantitative=True,
            temperature_unit="celsius",
            source_count=len(request.sources),
            processing_report=report_path,
            metadata={"diagnostics": diagnostics, "encoding": encoding},
        )
