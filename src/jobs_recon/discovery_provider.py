"""Provider-neutral search discovery interface."""

from typing import Protocol

# TODO: remove this module once Google search is implemented
from jobs_recon.google_grounding import (
    GoogleGroundingConfigError,
    discover_from_fixture,
    discover_with_google_grounding,
    load_grounding_fixture,
)
# TODO: remove this module once Google search is implemented
from jobs_recon.models import TargetBrief
# TODO: remove this module once Google search is implemented
from jobs_recon.search_discovery import (
    PROVIDER_GOOGLE_GROUNDING,
    PROVIDER_MANUAL_FIXTURE,
    DiscoveryPrompt,
    DiscoveryResponse,
    generate_discovery_prompts,
    normalize_grounded_response,
)

# TODO: remove this class once Google search is implemented
class SearchDiscoveryProvider(Protocol):
    name: str

    def generate_queries(self, target: TargetBrief) -> list[DiscoveryPrompt]:
        ...

    def discover(self, prompt: DiscoveryPrompt) -> DiscoveryResponse:
        ...


# TODO: remove this class once Google search is implemented
class GoogleGroundingProvider:
    name = PROVIDER_GOOGLE_GROUNDING

    def generate_queries(self, target: TargetBrief) -> list[DiscoveryPrompt]:
        return generate_discovery_prompts(target)

    def discover(self, prompt: DiscoveryPrompt) -> DiscoveryResponse:
        return discover_with_google_grounding(prompt.prompt)

# TODO: remove this class once Google search is implemented
class ManualFixtureProvider:
    name = PROVIDER_MANUAL_FIXTURE

    def __init__(self, fixture_path: str) -> None:
        self.fixture_path = fixture_path
        self._payload = load_grounding_fixture(fixture_path)

    def generate_queries(self, target: TargetBrief) -> list[DiscoveryPrompt]:
        return generate_discovery_prompts(target)

    def discover(self, prompt: DiscoveryPrompt) -> DiscoveryResponse:
        return discover_from_fixture(prompt.prompt, self._payload)

# TODO: remove this function once Google search is implemented
def get_provider(name: str, *, fixture_path: str | None = None) -> SearchDiscoveryProvider:
    key = name.strip().lower().replace("-", "_")
    if key in {PROVIDER_GOOGLE_GROUNDING, "google_grounding", "google-grounding"}:
        return GoogleGroundingProvider()
    if key in {PROVIDER_MANUAL_FIXTURE, "manual_fixture", "fixture"}:
        if not fixture_path:
            raise ValueError("fixture_path is required for the manual_fixture provider")
        return ManualFixtureProvider(fixture_path)
    raise ValueError(
        f"Unknown discovery provider {name!r}. Known providers: google_grounding, manual_fixture"
    )

# TODO: remove this list once Google search is implemented
__all__ = [
    "GoogleGroundingConfigError",
    "GoogleGroundingProvider",
    "ManualFixtureProvider",
    "SearchDiscoveryProvider",
    "get_provider",
    "normalize_grounded_response",
]
