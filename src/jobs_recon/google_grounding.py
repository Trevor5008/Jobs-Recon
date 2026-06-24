"""Optional Gemini / Vertex Google Search grounding client."""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from jobs_recon.search_discovery import (
    PROVIDER_GOOGLE_GROUNDING,
    DiscoveryCitation,
    DiscoveryResponse,
    classify_citations,
    normalize_grounded_response,
)

load_dotenv()

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
VERTEX_FLAG_ENV = "GOOGLE_GENAI_USE_VERTEXAI"
VERTEX_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
VERTEX_LOCATION_ENV = "GOOGLE_CLOUD_LOCATION"

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


# _truthy - returns True if the value is a truthy string
def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}

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

# google_grounding_configured - returns True if the Google Grounding configuration is valid
def google_grounding_configured() -> bool:
    try:
        get_google_grounding_config()
    except GoogleGroundingConfigError:
        return False
    return True

# _require_genai - returns the Google GenAI client and types
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

# _build_client - builds the Google GenAI client
def _build_client(config: GoogleGroundingConfig):
    genai, _types = _require_genai()
    if config.mode == "vertex":
        return genai.Client(
            vertexai=True,
            project=config.project,
            location=config.location,
        )
    return genai.Client(api_key=config.api_key)

# _metadata_to_dict - converts the Google GenAI metadata to a dictionary
def _metadata_to_dict(metadata) -> dict | None:
    if metadata is None:
        return None
    if hasattr(metadata, "model_dump"):
        return metadata.model_dump()
    if isinstance(metadata, dict):
        return metadata
    return None

# _citations_from_genai_response - extracts the citations from the Google GenAI response
def _citations_from_genai_response(response) -> list[DiscoveryCitation]:
    citations: list[DiscoveryCitation] = []
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return citations

    grounding_metadata = getattr(candidates[0], "grounding_metadata", None)
    if grounding_metadata is None:
        return citations

    chunks = getattr(grounding_metadata, "grounding_chunks", None) or []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web is None:
            continue
        url = getattr(web, "uri", None)
        if not isinstance(url, str) or not url.strip():
            continue
        title = getattr(web, "title", None)
        citations.append(
            DiscoveryCitation(
                url=url,
                title=title if isinstance(title, str) else None,
            )
        )

    return classify_citations(citations)

# discover_with_google_grounding - discovers the Google Grounding with the Google GenAI client
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
    citations = _citations_from_genai_response(response)
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
        citations=citations,
        grounding_metadata=grounding_metadata,
    )


# load_grounding_fixture - loads a saved grounded-response fixture
def load_grounding_fixture(path: str) -> dict:
    """Load a saved grounded-response fixture."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Grounding fixture must be a JSON object")
    return payload

# discover_from_fixture - normalizes a fixture payload for one prompt
def discover_from_fixture(prompt: str, payload: dict) -> DiscoveryResponse:
    """Normalize a fixture payload for one prompt."""
    return normalize_grounded_response(payload, prompt, provider=PROVIDER_GOOGLE_GROUNDING)
