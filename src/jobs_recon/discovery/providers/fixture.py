"""Manual fixture discovery provider."""

from jobs_recon.discovery.prompts import generate_discovery_prompts
from jobs_recon.discovery.providers.google import discover_from_fixture, load_grounding_fixture
from jobs_recon.discovery.providers.protocol import SearchDiscoveryProvider
from jobs_recon.discovery.types import (
    PROVIDER_MANUAL_FIXTURE,
    DiscoveryPrompt,
    DiscoveryResponse,
)
from jobs_recon.models import TargetBrief


class ManualFixtureProvider:
    name = PROVIDER_MANUAL_FIXTURE

    def __init__(self, fixture_path: str) -> None:
        self.fixture_path = fixture_path
        self._payload = load_grounding_fixture(fixture_path)

    def generate_queries(self, target: TargetBrief) -> list[DiscoveryPrompt]:
        return generate_discovery_prompts(target)

    def discover(self, prompt: DiscoveryPrompt) -> DiscoveryResponse:
        return discover_from_fixture(prompt.prompt, self._payload)
