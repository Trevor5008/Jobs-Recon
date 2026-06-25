"""Optional Gemini / Vertex Google Search grounding client."""

import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from jobs_recon.discovery.leads import enrich_lead
from jobs_recon.discovery.normalize import normalize_grounded_response
from jobs_recon.discovery.prompts import generate_discovery_prompts
from jobs_recon.discovery.providers.protocol import SearchDiscoveryProvider
from jobs_recon.discovery.types import (
    PROVIDER_GOOGLE_GROUNDING,
    DiscoveryLead,
    DiscoveryPrompt,
    DiscoveryResponse,
)
from jobs_recon.models import TargetBrief

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
VERTEX_FLAG_ENV = "GOOGLE_GENAI_USE_VERTEXAI"
VERTEX_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
VERTEX_LOCATION_ENV = "GOOGLE_CLOUD_LOCATION"
GOOGLE_APPLICATION_CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GoogleGroundingConfigError(ValueError):
    """Raised when Google Search grounding credentials are missing or invalid."""


@dataclass(frozen=True)
class GoogleGroundingConfig:
    mode: str
    model: str
    api_key: str | None = None
    project: str | None = None
    location: str | None = None


@dataclass
class GroundingConfigCheckResult:
    mode: str
    model: str
    ready: bool
    project: str | None = None
    location: str | None = None
    credentials_env: str | None = None
    credentials_file_exists: bool | None = None
    google_genai_available: bool = False
    issues: list[str] = field(default_factory=list)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_genai_available() -> bool:
    return importlib.util.find_spec("google.genai") is not None


def get_google_grounding_config() -> GoogleGroundingConfig:
    """Return grounding configuration or raise with a clear message."""
    model = os.environ.get(GEMINI_MODEL_ENV, DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL

    if _truthy(os.environ.get(VERTEX_FLAG_ENV)):
        project = os.environ.get(VERTEX_PROJECT_ENV, "").strip()
        location = os.environ.get(VERTEX_LOCATION_ENV, "us-central1").strip() or "us-central1"
        missing = []
        if not project:
            missing.append(VERTEX_PROJECT_ENV)
        if missing:
            joined = ", ".join(missing)
            raise GoogleGroundingConfigError(
                f"Missing required environment variable(s) for Vertex grounding: {joined}. "
                "Set them to run a live grounding check, or use --dry-run / --fixture."
            )
        return GoogleGroundingConfig(
            mode="vertex",
            model=model,
            project=project,
            location=location,
        )

    api_key = (
        os.environ.get(GEMINI_API_KEY_ENV, "").strip()
        or os.environ.get(GOOGLE_API_KEY_ENV, "").strip()
    )
    if not api_key:
        raise GoogleGroundingConfigError(
            f"Missing required environment variable: {GEMINI_API_KEY_ENV} "
            f"(or {GOOGLE_API_KEY_ENV}). Set one to run a live grounding check, "
            "or use --dry-run / --fixture."
        )

    return GoogleGroundingConfig(mode="gemini_api", model=model, api_key=api_key)


def google_grounding_configured() -> bool:
    try:
        get_google_grounding_config()
    except GoogleGroundingConfigError:
        return False
    return True


def check_google_grounding_config() -> GroundingConfigCheckResult:
    """Check live grounding readiness without making a model API call."""
    issues: list[str] = []
    genai_available = _is_genai_available()
    if not genai_available:
        issues.append(
            "google-genai is not installed. Install with: uv pip install -e '.[grounding]'"
        )

    model = os.environ.get(GEMINI_MODEL_ENV, DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    credentials_path = os.environ.get(GOOGLE_APPLICATION_CREDENTIALS_ENV, "").strip() or None
    credentials_exists: bool | None = None

    if _truthy(os.environ.get(VERTEX_FLAG_ENV)):
        project = os.environ.get(VERTEX_PROJECT_ENV, "").strip() or None
        location = os.environ.get(VERTEX_LOCATION_ENV, "us-central1").strip() or "us-central1"

        if not project:
            issues.append(f"Set {VERTEX_PROJECT_ENV} for Vertex grounding.")
        if not credentials_path:
            issues.append(
                f"Set {GOOGLE_APPLICATION_CREDENTIALS_ENV} to your local service account JSON path."
            )
        else:
            credentials_exists = Path(credentials_path).is_file()
            if not credentials_exists:
                issues.append(
                    f"{GOOGLE_APPLICATION_CREDENTIALS_ENV} is set but the file was not found."
                )

        ready = not issues
        return GroundingConfigCheckResult(
            mode="vertex",
            model=model,
            ready=ready,
            project=project,
            location=location,
            credentials_env=GOOGLE_APPLICATION_CREDENTIALS_ENV if credentials_path else None,
            credentials_file_exists=credentials_exists,
            google_genai_available=genai_available,
            issues=issues,
        )

    api_key_set = bool(
        os.environ.get(GEMINI_API_KEY_ENV, "").strip()
        or os.environ.get(GOOGLE_API_KEY_ENV, "").strip()
    )
    if not api_key_set:
        issues.append(
            f"Vertex mode is not enabled. Set {VERTEX_FLAG_ENV}=true for the recommended path, "
            f"or set {GEMINI_API_KEY_ENV} for Gemini API mode."
        )

    ready = not issues
    return GroundingConfigCheckResult(
        mode="gemini_api" if api_key_set else "unconfigured",
        model=model,
        ready=ready,
        google_genai_available=genai_available,
        issues=issues,
    )


def format_config_check_report(result: GroundingConfigCheckResult) -> str:
    """Render a human-readable config check without secret values."""
    lines = ["Google grounding config:", f"- mode: {result.mode}", f"- model: {result.model}"]

    if result.mode == "vertex":
        lines.append(f"- project: {result.project or '(not set)'}")
        lines.append(f"- location: {result.location or '(not set)'}")

    if result.credentials_env:
        if result.credentials_file_exists:
            lines.append(f"- {GOOGLE_APPLICATION_CREDENTIALS_ENV}: set, file exists")
        else:
            lines.append(f"- {GOOGLE_APPLICATION_CREDENTIALS_ENV}: set, file missing")
    elif result.mode == "vertex":
        lines.append(f"- {GOOGLE_APPLICATION_CREDENTIALS_ENV}: not set")

    lines.append(
        f"- google-genai: {'available' if result.google_genai_available else 'missing'}"
    )
    lines.append(f"Status: {'ready' if result.ready else 'not ready'}")

    if result.issues:
        lines.append("")
        lines.append("Next steps:")
        for issue in result.issues:
            lines.append(f"- {issue}")

    return "\n".join(lines)


def _require_genai():
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GoogleGroundingConfigError(
            "The google-genai package is required for live grounding. "
            "Install with: pip install 'jobs-recon[grounding]'"
        ) from exc
    return genai, types


def _build_client(config: GoogleGroundingConfig):
    genai, _types = _require_genai()
    if config.mode == "vertex":
        return genai.Client(
            vertexai=True,
            project=config.project,
            location=config.location,
        )
    return genai.Client(api_key=config.api_key)


def _metadata_to_dict(metadata) -> dict | None:
    if metadata is None:
        return None
    if hasattr(metadata, "model_dump"):
        return metadata.model_dump()
    if isinstance(metadata, dict):
        return metadata
    return None


def _leads_from_genai_response(response) -> list[DiscoveryLead]:
    leads: list[DiscoveryLead] = []
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return leads

    grounding_metadata = getattr(candidates[0], "grounding_metadata", None)
    if grounding_metadata is None:
        return leads

    chunks = getattr(grounding_metadata, "grounding_chunks", None) or []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web is None:
            continue
        url = getattr(web, "uri", None)
        if not isinstance(url, str) or not url.strip():
            continue
        title = getattr(web, "title", None)
        leads.append(
            enrich_lead(
                DiscoveryLead(
                    discovery_url=url,
                    title=title if isinstance(title, str) else None,
                )
            )
        )

    return leads


def discover_with_google_grounding(prompt: str) -> DiscoveryResponse:
    """Run one live Gemini / Vertex request with Google Search grounding."""
    config = get_google_grounding_config()
    genai, types = _require_genai()
    client = _build_client(config)

    response = client.models.generate_content(
        model=config.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    text = getattr(response, "text", "") or ""
    model = getattr(response, "model_version", None) or config.model
    leads = _leads_from_genai_response(response)
    grounding_metadata = None
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        grounding_metadata = _metadata_to_dict(
            getattr(candidates[0], "grounding_metadata", None)
        )

    return DiscoveryResponse(
        provider=PROVIDER_GOOGLE_GROUNDING,
        model=model if isinstance(model, str) else config.model,
        prompt=prompt,
        response_text=text,
        citations=leads,
        grounding_metadata=grounding_metadata,
    )


class GoogleGroundingProvider:
    name = PROVIDER_GOOGLE_GROUNDING

    def generate_queries(self, target: TargetBrief) -> list[DiscoveryPrompt]:
        return generate_discovery_prompts(target)

    def discover(self, prompt: DiscoveryPrompt) -> DiscoveryResponse:
        return discover_with_google_grounding(prompt.prompt)


def load_grounding_fixture(path: str) -> dict:
    """Load a saved grounded-response fixture."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Grounding fixture must be a JSON object")
    return payload


def discover_from_fixture(prompt: str, payload: dict) -> DiscoveryResponse:
    """Normalize a fixture payload for one prompt."""
    return normalize_grounded_response(payload, prompt, provider=PROVIDER_GOOGLE_GROUNDING)
