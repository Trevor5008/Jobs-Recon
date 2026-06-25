"""Provider-neutral search discovery interface."""

from typing import Protocol

from jobs_recon.discovery.types import DiscoveryPrompt, DiscoveryResponse
from jobs_recon.models import TargetBrief


class SearchDiscoveryProvider(Protocol):
    name: str

    def generate_queries(self, target: TargetBrief) -> list[DiscoveryPrompt]:
        ...

    def discover(self, prompt: DiscoveryPrompt) -> DiscoveryResponse:
        ...
