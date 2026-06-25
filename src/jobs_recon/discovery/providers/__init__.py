"""Discovery provider registry and public exports."""

from jobs_recon.discovery.normalize import normalize_grounded_response
from jobs_recon.discovery.providers.fixture import ManualFixtureProvider
from jobs_recon.discovery.providers.google import (
    GoogleGroundingConfigError,
    GoogleGroundingProvider,
)
from jobs_recon.discovery.providers.protocol import SearchDiscoveryProvider
from jobs_recon.discovery.types import PROVIDER_GOOGLE_GROUNDING, PROVIDER_MANUAL_FIXTURE


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


__all__ = [
    "GoogleGroundingConfigError",
    "GoogleGroundingProvider",
    "ManualFixtureProvider",
    "SearchDiscoveryProvider",
    "get_provider",
    "normalize_grounded_response",
]
