from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Any

from ..ai.enrichment import enrich_finding
from ..ai.ollama import OllamaProvider
from ..ai.provider import LocalAIModel
from ..inspections.profiles import InspectionProfile, get_profile
from ..orthomosaic import OrthomosaicRequest, OrthomosaicResult, OrthomosaicService
from ..platform.config import AppConfig
from ..reporting.annotations import write_finding_evidence
from ..reporting.deliverable import write_client_deliverable
from ..thermal.calibration import ThermalCalibration
from ..thermal.presentation import ThermalStyle
from .orchestrator import AutonomousInspectionOrchestrator, InspectionRun
from .projects import Project


@dataclass(frozen=True, slots=True)
class UniversalProcessingPlan:
    stitch_mode: str = "auto"
    orthomosaic_backend: str = "auto"
    ai_mode: str = "off"
    thermal_style: ThermalStyle = field(default_factory=ThermalStyle)
    keep_working_files: bool = True

    def __post_init__(self) -> None:
        if self.stitch_mode not in {"auto", "on", "off"}:
            raise ValueError("stitch_mode must be auto, on, or off")
        if not self.ai_mode.strip():
            raise ValueError("ai_mode must be off, auto, or a local model name")


@dataclass(slots=True)
class UniversalProcessingResult:
    project: Project
    run: InspectionRun
    deliverable_dir: Path
    orthomosaic: OrthomosaicResult | None = None
    ai_model: str = ""
    ai_provider: str = ""
    ai_enriched_findings: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.report_metadata(),
            "status": self.run.status.value,
            "summary": asdict(self.run.summary),
            "deliverable_dir": str(self.deliverable_dir),
            "orthomosaic": None if self.orthomosaic is None else {
                "path": str(self.orthomosaic.orthomosaic),
                "backend": self.orthomosaic.backend,
                "quantitative": self.orthomosaic.quantitative,
                "temperature_unit": self.orthomosaic.temperature_unit,
            },
            "ai": {
                "provider": self.ai_provider,
                "model": self.ai_model,
                "enriched_findings": self.ai_enriched_findings,
            },
            "warnings": self.warnings,
        }


class UniversalThermalProcessor:
    """End-to-end post-processing authority from thermal sources to shareable deliverable.

    Orthomosaic creation is optional and backend-driven. Quantitative analysis always returns through
    AutonomousInspectionOrchestrator. Local AI enrichment is optional and cannot mutate quantitative
    authority fields.
    """

    def __init__(
        self,
        *,
        orchestrator: AutonomousInspectionOrchestrator | None = None,
        orthomosaics: OrthomosaicService | None = None,
        config: AppConfig | None = None,
    ):
        self.orchestrator = orchestrator or AutonomousInspectionOrchestrator()
        self.orthomosaics = orthomosaics or OrthomosaicService()
        self.config = config or AppConfig.from_env()

    @staticmethod
    def _should_stitch(sources: list[Path], plan: UniversalProcessingPlan) -> bool:
        if plan.stitch_mode == "off":
            return False
        if plan.stitch_mode == "on":
            return True
        return len(sources) > 1

    @staticmethod
    def _select_ai_model(models: tuple[LocalAIModel, ...], mode: str) -> LocalAIModel | None:
        if mode == "off" or not models:
            return None
        if mode != "auto":
            for model in models:
                if model.name == mode:
                    return model
            return None
        vision = [model for model in models if model.supports_vision]
        return vision[0] if vision else models[0]

    def _enrich(
        self,
        run: InspectionRun,
        working_dir: Path,
        mode: str,
        warnings: list[str],
        on_event: Callable[[str], None] | None = None,
    ) -> tuple[str, str, int]:
        if mode == "off" or not run.canonical_findings:
            return "", "", 0
        provider = OllamaProvider(self.config.ollama_base_url)
        if not provider.available():
            warnings.append("Local AI requested but Ollama is not reachable; deterministic deliverable continued")
            return "", "", 0
        try:
            models = provider.list_models()
        except RuntimeError as exc:
            warnings.append(f"Unable to enumerate local AI models: {exc}")
            return provider.name, "", 0
        selected = self._select_ai_model(models, mode)
        if selected is None:
            warnings.append(f"Requested local AI model {mode!r} is not installed")
            return provider.name, "", 0

        artifact_by_source = {
            str(Path(artifact.result.source)): artifact
            for artifact in run.artifacts
        }
        evidence_root = working_dir / "ai-evidence"
        enriched = 0
        for finding in run.canonical_findings:
            artifact = artifact_by_source.get(str(Path(finding.source_path)))
            images: tuple[Path, ...] = ()
            if artifact is not None and selected.supports_vision:
                try:
                    evidence = write_finding_evidence(
                        artifact.frame,
                        finding,
                        evidence_root / (finding.finding_id or "finding"),
                    )
                    images = (evidence["crop"],)
                except Exception as exc:
                    warnings.append(
                        f"AI evidence image unavailable for {finding.finding_id}: {type(exc).__name__}: {exc}"
                    )
            try:
                enrich_finding(
                    finding,
                    provider,
                    model=selected.name,
                    project_context=run.project.report_metadata(),
                    image_paths=images,
                )
                enriched += 1
                if on_event:
                    on_event(f"AI enriched {finding.finding_id or 'finding'} with {selected.name}")
            except Exception as exc:
                warnings.append(
                    f"AI enrichment failed for {finding.finding_id}: {type(exc).__name__}: {exc}"
                )
        return provider.name, selected.name, enriched

    def process(
        self,
        project: Project,
        sources: list[str | Path],
        output_dir: str | Path,
        *,
        calibration: ThermalCalibration | None = None,
        profile: InspectionProfile | None = None,
        plan: UniversalProcessingPlan | None = None,
        adapter_name: str | None = None,
        on_event: Callable[[str], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> UniversalProcessingResult:
        active_plan = plan or UniversalProcessingPlan()
        active_profile = profile or get_profile(project.profile_id)
        calibration = calibration or ThermalCalibration()
        input_paths = [Path(source).expanduser().resolve() for source in sources]
        if not input_paths:
            raise ValueError("Universal processing requires at least one source")
        missing = [str(path) for path in input_paths if not path.is_file()]
        if missing:
            raise FileNotFoundError("Missing thermal sources: " + ", ".join(missing))

        output_root = Path(output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        working_dir = output_root / "_processing"
        working_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        orthomosaic: OrthomosaicResult | None = None
        analysis_sources = input_paths

        if self._should_stitch(input_paths, active_plan):
            if on_event:
                on_event("Building quantitative thermal orthomosaic")
            request = OrthomosaicRequest(
                sources=tuple(input_paths),
                output_dir=working_dir / "orthomosaic",
                project_name=project.name,
                calibration_mode="camera",
                metadata={
                    "project_id": project.project_id,
                    "profile_id": active_profile.profile_id,
                },
            )
            try:
                orthomosaic = self.orthomosaics.process(
                    request,
                    preferred=active_plan.orthomosaic_backend,
                )
            except Exception:
                if active_plan.stitch_mode == "on":
                    raise
                warnings.append(
                    "Automatic stitching was unavailable for these sources; processing continued "
                    "against the original radiometric inputs"
                )
            else:
                if not orthomosaic.quantitative:
                    raise RuntimeError("Orthomosaic backend returned a non-quantitative raster")
                analysis_sources = [orthomosaic.orthomosaic]
                adapter_name = "generic-geotiff"

        if on_event:
            on_event("Running canonical radiometric analysis")
        run = self.orchestrator.analyze_inspection(
            project,
            analysis_sources,
            calibration=calibration,
            adapter_name=adapter_name,
            profile=active_profile,
            output_dir=None,
            is_cancelled=is_cancelled,
        )
        if not run.artifacts:
            details = "; ".join(f"{item.source}: {item.error}" for item in run.failures)
            raise RuntimeError("No quantitative source completed analysis" + (f": {details}" if details else ""))

        if on_event:
            on_event("Running optional local AI interpretation")
        ai_provider, ai_model, enriched = self._enrich(
            run,
            working_dir,
            active_plan.ai_mode,
            warnings,
            on_event,
        )

        if on_event:
            on_event("Generating client and engineering deliverable")
        deliverable = write_client_deliverable(
            run,
            output_root,
            orthomosaic=orthomosaic,
            style=active_plan.thermal_style,
            processing_metadata={
                "provider": ai_provider,
                "model": ai_model,
                "enriched_findings": enriched,
                "warnings": warnings,
            },
        )
        run.package_dir = deliverable
        return UniversalProcessingResult(
            project=project,
            run=run,
            deliverable_dir=deliverable,
            orthomosaic=orthomosaic,
            ai_model=ai_model,
            ai_provider=ai_provider,
            ai_enriched_findings=enriched,
            warnings=warnings,
        )
