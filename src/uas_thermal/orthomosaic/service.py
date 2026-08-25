from __future__ import annotations

from ..sensors.base import AdapterUnavailableError
from .base import OrthomosaicBackend, OrthomosaicRequest, OrthomosaicResult
from .native import NativeGeoTiffMosaicBackend
from .odm import OpenDroneMapBackend


class OrthomosaicService:
    def __init__(self, backends: tuple[OrthomosaicBackend, ...] | None = None):
        self.backends = backends or (
            NativeGeoTiffMosaicBackend(),
            OpenDroneMapBackend(),
        )

    def status(self) -> list[dict[str, object]]:
        return [
            {
                "name": backend.name,
                "available": backend.available(),
            }
            for backend in self.backends
        ]

    def select(
        self,
        request: OrthomosaicRequest,
        preferred: str | None = None,
    ) -> OrthomosaicBackend:
        if preferred and preferred != "auto":
            for backend in self.backends:
                if backend.name == preferred:
                    if not backend.available():
                        raise AdapterUnavailableError(
                            f"Orthomosaic backend {preferred!r} is configured but unavailable"
                        )
                    if not backend.can_process(request):
                        raise AdapterUnavailableError(
                            f"Orthomosaic backend {preferred!r} cannot process these sources"
                        )
                    return backend
            raise AdapterUnavailableError(f"Unknown orthomosaic backend: {preferred!r}")
        for backend in self.backends:
            if backend.available() and backend.can_process(request):
                return backend
        raise AdapterUnavailableError(
            "No quantitative orthomosaic backend is available for these sources. Georeferenced "
            "radiometric GeoTIFFs can use native-geotiff; raw thermal image collections require an "
            "installed photogrammetry backend such as OpenDroneMap."
        )

    def process(
        self,
        request: OrthomosaicRequest,
        *,
        preferred: str | None = None,
    ) -> OrthomosaicResult:
        return self.select(request, preferred).process(request)
