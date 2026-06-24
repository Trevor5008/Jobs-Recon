"""Target-aware discovery prompts and source URL classification."""

from dataclasses import dataclass, field
from urllib.parse import urlparse

from jobs_recon.models import TargetBrief

PROVIDER_GOOGLE_GROUNDING = "google_grounding"
PROVIDER_MANUAL_FIXTURE = "manual_fixture"

SOURCE_TYPE_ATS = "ats"
SOURCE_TYPE_EMPLOYER = "employer"
SOURCE_TYPE_AGGREGATOR = "aggregator"
SOURCE_TYPE_SEARCH_SURFACE = "search_surface"
SOURCE_TYPE_IRRELEVANT = "irrelevant"
SOURCE_TYPE_UNKNOWN = "unknown"

PREFERRED_SOURCE_TYPES = (SOURCE_TYPE_ATS, SOURCE_TYPE_EMPLOYER)
DEPRIORITIZED_SOURCE_TYPES = (
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_SEARCH_SURFACE,
    SOURCE_TYPE_IRRELEVANT,
)

CANONICAL_ATS_GUIDANCE = (
    "Prefer canonical employer career pages and public ATS pages such as Greenhouse, "
    "Lever, Ashby, Workable, SmartRecruiters, BambooHR, JazzHR, or Workday. Avoid "
    "treating LinkedIn, Indeed, Handshake, or Google Jobs panels as canonical sources. "
    "Return source URLs where possible."
)

ATS_DOMAIN_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("greenhouse.io",),
    ("boards.greenhouse.io",),
    ("jobs.lever.co",),
    ("ashbyhq.com",),
    ("workable.com",),
    ("smartrecruiters.com",),
    ("bamboohr.com",),
    ("jazzhr.com",),
    ("myworkdayjobs.com",),
)

AGGREGATOR_DOMAIN_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("linkedin.com", "jobs"),
    ("indeed.com",),
    ("glassdoor.com",),
    ("ziprecruiter.com",),
    ("dice.com",),
    ("joinhandshake.com",),
    ("app.joinhandshake.com",),
)

SEARCH_SURFACE_DOMAIN_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("google.com", "search"),
    ("google.com", "about", "careers", "search"),
    ("jobs.google.com",),
)

SITE_SPECIFIC_PROMPTS: tuple[tuple[str, str], ...] = (
    ("Greenhouse (greenhouse.io / boards.greenhouse.io)", "Greenhouse ATS discovery"),
    ("Lever (jobs.lever.co)", "Lever ATS discovery"),
    ("Ashby (ashbyhq.com)", "Ashby ATS discovery"),
    ("Workable (workable.com)", "Workable ATS discovery"),
)


@dataclass(frozen=True)
class DiscoveryPrompt:
    prompt: str
    label: str


@dataclass
class DiscoveryCitation:
    url: str
    title: str | None = None
    snippet: str | None = None
    source_type: str = SOURCE_TYPE_UNKNOWN


@dataclass
class DiscoveryResponse:
    provider: str
    model: str | None
    prompt: str
    response_text: str
    citations: list[DiscoveryCitation] = field(default_factory=list)
    grounding_metadata: dict | None = None
    timestamp: str | None = None


@dataclass
class DiscoveryFeasibilityRun:
    target_name: str
    target_summary: str
    target_path: str | None
    prompts: list[DiscoveryPrompt] = field(default_factory=list)
    responses: list[DiscoveryResponse] = field(default_factory=list)
    mode: str = "dry-run"
    provider: str = PROVIDER_GOOGLE_GROUNDING


def summarize_target(target: TargetBrief) -> str:
    """Build a short target summary for provenance in reports."""
    lines = [f"Name: {target.name}"]
    if target.role_family:
        lines.append(f"Role family: {target.role_family}")
    if target.title_keywords:
        lines.append(f"Title keywords: {', '.join(target.title_keywords)}")
    if target.locations:
        lines.append(f"Locations: {', '.join(target.locations)}")
    if target.seniority:
        lines.append(f"Seniority: {', '.join(target.seniority)}")
    if target.required_skills:
        lines.append(f"Required skills: {', '.join(target.required_skills)}")
    return "; ".join(lines)


def generate_discovery_prompts(target: TargetBrief) -> list[DiscoveryPrompt]:
    """Build deterministic grounded-search prompts from a target brief."""
    title_keywords = ", ".join(target.title_keywords) or "AI/software roles"
    locations = ", ".join(target.locations) or "any listed location"
    seniority = ", ".join(target.seniority) or "entry-level, junior, or intern"

    prompts: list[DiscoveryPrompt] = [
        DiscoveryPrompt(
            prompt=(
                f"Find current public job postings for {seniority} AI/software roles "
                f"matching titles such as {title_keywords} around {locations}. "
                f"{CANONICAL_ATS_GUIDANCE}"
            ),
            label="General grounded discovery prompt",
        )
    ]

    for platform, label in SITE_SPECIFIC_PROMPTS:
        prompts.append(
            DiscoveryPrompt(
                prompt=(
                    f"Find current public job postings for {title_keywords} on {platform} "
                    f"around {locations}, focusing on {seniority} roles. "
                    f"{CANONICAL_ATS_GUIDANCE}"
                ),
                label=label,
            )
        )

    return prompts


def _normalized_host(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


def _path_segments(url: str) -> tuple[str, ...]:
    parsed = urlparse(url)
    return tuple(segment.casefold() for segment in parsed.path.split("/") if segment)


def _host_matches_pattern(host: str, pattern: tuple[str, ...]) -> bool:
    if not pattern:
        return False
    if len(pattern) == 1:
        return host == pattern[0] or host.endswith(f".{pattern[0]}")
    if host != pattern[0] and not host.endswith(f".{pattern[0]}"):
        return False
    return True


def _path_matches_pattern(path_segments: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
    if len(pattern) <= 1:
        return True
    required = pattern[1:]
    joined = "/".join(path_segments)
    return all(segment in joined for segment in required)


def classify_result_url(url: str) -> str:
    """Classify a candidate URL by likely source type. Conservative when unsure."""
    if not url.strip():
        return SOURCE_TYPE_IRRELEVANT

    host = _normalized_host(url)
    path_segments = _path_segments(url)

    if not host:
        return SOURCE_TYPE_UNKNOWN

    for pattern in SEARCH_SURFACE_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern) and _path_matches_pattern(path_segments, pattern):
            return SOURCE_TYPE_SEARCH_SURFACE

    for pattern in AGGREGATOR_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern) and _path_matches_pattern(path_segments, pattern):
            return SOURCE_TYPE_AGGREGATOR

    for pattern in ATS_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern):
            return SOURCE_TYPE_ATS

    if host.endswith(".com") or host.endswith(".io") or host.endswith(".co"):
        return SOURCE_TYPE_EMPLOYER

    return SOURCE_TYPE_UNKNOWN


def classify_citations(citations: list[DiscoveryCitation]) -> list[DiscoveryCitation]:
    for citation in citations:
        citation.source_type = classify_result_url(citation.url)
    return citations


def _citation_from_mapping(data: dict) -> DiscoveryCitation | None:
    url = data.get("url") or data.get("uri") or data.get("link")
    if not isinstance(url, str) or not url.strip():
        return None
    title = data.get("title")
    snippet = data.get("snippet")
    return DiscoveryCitation(
        url=url,
        title=title if isinstance(title, str) else None,
        snippet=snippet if isinstance(snippet, str) else None,
    )


def _extract_grounding_metadata(payload: dict) -> dict | None:
    metadata = payload.get("grounding_metadata") or payload.get("groundingMetadata")
    return metadata if isinstance(metadata, dict) else None


def _citations_from_grounding_metadata(metadata: dict) -> list[DiscoveryCitation]:
    chunks = metadata.get("grounding_chunks") or metadata.get("groundingChunks") or []
    if not isinstance(chunks, list):
        return []

    citations: list[DiscoveryCitation] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web")
        if not isinstance(web, dict):
            continue
        citation = _citation_from_mapping(web)
        if citation is not None:
            citations.append(citation)
    return citations


def _response_text_from_payload(payload: dict) -> str:
    if isinstance(payload.get("response_text"), str):
        return payload["response_text"]

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""

    first = candidates[0]
    if not isinstance(first, dict):
        return ""

    content = first.get("content")
    if not isinstance(content, dict):
        return ""

    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""

    text_parts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text_parts.append(part["text"])
    return "\n".join(text_parts)


def normalize_grounded_response(
    payload: dict,
    prompt: str,
    *,
    provider: str = PROVIDER_GOOGLE_GROUNDING,
    model: str | None = None,
    timestamp: str | None = None,
) -> DiscoveryResponse:
    """Normalize fixture or Gemini API JSON into a DiscoveryResponse."""
    if not isinstance(payload, dict):
        raise ValueError("Grounded response payload must be a JSON object")

    response_text = _response_text_from_payload(payload)
    grounding_metadata = _extract_grounding_metadata(payload)

    citations: list[DiscoveryCitation] = []
    raw_citations = payload.get("citations")
    if isinstance(raw_citations, list):
        for item in raw_citations:
            if isinstance(item, dict):
                citation = _citation_from_mapping(item)
                if citation is not None:
                    citations.append(citation)

    if not citations and grounding_metadata is not None:
        citations = _citations_from_grounding_metadata(grounding_metadata)

    classify_citations(citations)

    resolved_model = payload.get("model")
    if not isinstance(resolved_model, str):
        resolved_model = model

    resolved_timestamp = payload.get("timestamp")
    if not isinstance(resolved_timestamp, str):
        resolved_timestamp = timestamp

    return DiscoveryResponse(
        provider=provider,
        model=resolved_model,
        prompt=prompt,
        response_text=response_text,
        citations=citations,
        grounding_metadata=grounding_metadata,
        timestamp=resolved_timestamp,
    )


def all_citations(responses: list[DiscoveryResponse]) -> list[DiscoveryCitation]:
    citations: list[DiscoveryCitation] = []
    for response in responses:
        citations.extend(response.citations)
    return citations


def promising_citations(citations: list[DiscoveryCitation]) -> list[DiscoveryCitation]:
    """Prefer canonical ATS/employer URLs over aggregators and search surfaces."""
    preferred = [citation for citation in citations if citation.source_type in PREFERRED_SOURCE_TYPES]
    if preferred:
        return preferred
    return [
        citation
        for citation in citations
        if citation.source_type not in DEPRIORITIZED_SOURCE_TYPES
    ]
