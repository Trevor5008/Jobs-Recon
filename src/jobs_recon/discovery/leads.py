"""URL classification, lead enrichment, and citation helpers."""

from urllib.parse import urlparse

from jobs_recon.discovery.types import (
    ACTIONABILITY_CANONICAL_CANDIDATE,
    ACTIONABILITY_MANUAL_REVIEW,
    ACTIONABILITY_MANUAL_REVIEW_ONLY,
    ACTIONABILITY_NOT_ACTIONABLE,
    ACTIONABILITY_SEARCH_SURFACE_ONLY,
    AGGREGATOR_DOMAIN_PATTERNS,
    ATS_DOMAIN_PATTERNS,
    AVAILABILITY_ACTIVE,
    AVAILABILITY_AGGREGATOR_ONLY,
    AVAILABILITY_INACTIVE,
    AVAILABILITY_LOGIN_GATED,
    AVAILABILITY_UNCERTAIN,
    DEPRIORITIZED_SOURCE_TYPES,
    PREFERRED_SOURCE_TYPES,
    SEARCH_SURFACE_DOMAIN_PATTERNS,
    SOURCE_FAMILY_ATS,
    SOURCE_FAMILY_DICE,
    SOURCE_FAMILY_EMPLOYER,
    SOURCE_FAMILY_GOOGLE_JOBS,
    SOURCE_FAMILY_GOOGLE_SEARCH,
    SOURCE_FAMILY_LINKEDIN,
    SOURCE_FAMILY_UNKNOWN,
    SOURCE_FAMILY_VERTEX_REDIRECT,
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_ATS,
    SOURCE_TYPE_EMPLOYER,
    SOURCE_TYPE_IRRELEVANT,
    SOURCE_TYPE_SEARCH_SURFACE,
    SOURCE_TYPE_UNKNOWN,
    VERTEX_REDIRECT_HOST,
    VERTEX_REDIRECT_PATH_PREFIX,
    DiscoveryLead,
    DiscoveryResponse,
)


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


def is_vertex_redirect_url(url: str) -> bool:
    """Vertex grounding citations often use redirect wrappers, not canonical posting URLs."""
    if not url.strip():
        return False
    parsed = urlparse(url)
    host = _normalized_host(url)
    if host != VERTEX_REDIRECT_HOST:
        return False
    return parsed.path.startswith(VERTEX_REDIRECT_PATH_PREFIX)


def display_domain_for_url(url: str) -> str | None:
    host = _normalized_host(url)
    return host or None


def display_domain_for_lead(lead: DiscoveryLead) -> str | None:
    if lead.canonical_posting_url:
        return display_domain_for_url(lead.canonical_posting_url)
    if is_vertex_redirect_url(lead.discovery_url):
        return lead.title or VERTEX_REDIRECT_HOST
    return display_domain_for_url(lead.discovery_url)


def classify_result_url(url: str) -> str:
    """Classify a candidate URL by likely source type. Conservative when unsure."""
    if not url.strip():
        return SOURCE_TYPE_IRRELEVANT

    if is_vertex_redirect_url(url):
        return SOURCE_TYPE_UNKNOWN

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

    return SOURCE_TYPE_UNKNOWN


def infer_source_family(url: str) -> str:
    """Infer a recognizable source family from a URL."""
    if not url.strip():
        return SOURCE_FAMILY_UNKNOWN

    if is_vertex_redirect_url(url):
        return SOURCE_FAMILY_VERTEX_REDIRECT

    host = _normalized_host(url)
    path_segments = _path_segments(url)

    if not host:
        return SOURCE_FAMILY_UNKNOWN

    if host == "jobs.google.com" or host.endswith(".jobs.google.com"):
        return SOURCE_FAMILY_GOOGLE_JOBS

    for pattern in SEARCH_SURFACE_DOMAIN_PATTERNS:
        if not _host_matches_pattern(host, pattern) or not _path_matches_pattern(path_segments, pattern):
            continue
        if pattern[0] == "google.com" and len(pattern) >= 2 and pattern[1] == "search":
            return SOURCE_FAMILY_GOOGLE_SEARCH
        if pattern[0] == "jobs.google.com" or (
            pattern[0] == "google.com" and "careers" in pattern
        ):
            return SOURCE_FAMILY_GOOGLE_JOBS


    for pattern in (("linkedin.com", "jobs"),):
        if _host_matches_pattern(host, pattern) and _path_matches_pattern(path_segments, pattern):
            return SOURCE_FAMILY_LINKEDIN

    if host == "dice.com" or host.endswith(".dice.com"):
        return SOURCE_FAMILY_DICE

    for pattern in ATS_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern):
            return SOURCE_FAMILY_ATS

    source_type = classify_result_url(url)
    if source_type == SOURCE_TYPE_EMPLOYER:
        return SOURCE_FAMILY_EMPLOYER

    return SOURCE_FAMILY_UNKNOWN


def infer_actionability(lead: DiscoveryLead) -> str:
    """Infer how Jobs Recon should treat this lead without crawling."""
    if is_vertex_redirect_url(lead.discovery_url) and not lead.canonical_posting_url:
        return ACTIONABILITY_NOT_ACTIONABLE

    family = lead.source_family

    if family == SOURCE_FAMILY_VERTEX_REDIRECT:
        return ACTIONABILITY_NOT_ACTIONABLE
    if family == SOURCE_FAMILY_ATS:
        return ACTIONABILITY_CANONICAL_CANDIDATE
    if family == SOURCE_FAMILY_EMPLOYER:
        return ACTIONABILITY_MANUAL_REVIEW
    if family == SOURCE_FAMILY_DICE:
        return ACTIONABILITY_MANUAL_REVIEW
    if family == SOURCE_FAMILY_LINKEDIN:
        return ACTIONABILITY_MANUAL_REVIEW_ONLY
    if family in (SOURCE_FAMILY_GOOGLE_JOBS, SOURCE_FAMILY_GOOGLE_SEARCH):
        return ACTIONABILITY_SEARCH_SURFACE_ONLY
    return ACTIONABILITY_MANUAL_REVIEW


def recommendation_for_lead(lead: DiscoveryLead) -> str:
    """Return human-readable guidance for triaging this lead."""
    recommendations = {
        SOURCE_FAMILY_ATS: (
            "Preferred canonical candidate; manually verify the posting is active before import."
        ),
        SOURCE_FAMILY_EMPLOYER: (
            "Potential canonical employer lead; inspect manually for a full posting URL."
        ),
        SOURCE_FAMILY_DICE: (
            "Useful tech-board lead for manual triage; prefer employer or ATS URL before import."
        ),
        SOURCE_FAMILY_LINKEDIN: (
            "Use for manual awareness only; do not scrape or automate login."
        ),
        SOURCE_FAMILY_GOOGLE_JOBS: (
            "Search surface only; resolve to a canonical employer or ATS URL before import."
        ),
        SOURCE_FAMILY_GOOGLE_SEARCH: (
            "Search surface only; resolve to a canonical employer or ATS URL before import."
        ),
        SOURCE_FAMILY_VERTEX_REDIRECT: (
            "Grounding provenance wrapper only; resolve manually before treating as actionable."
        ),
        SOURCE_FAMILY_UNKNOWN: "Manual review required before import.",
    }
    return recommendations.get(lead.source_family, recommendations[SOURCE_FAMILY_UNKNOWN])


def infer_availability_status(lead: DiscoveryLead) -> str:
    """Infer availability without crawling. Grounded text alone is not enough for active."""
    if lead.availability_status != AVAILABILITY_UNCERTAIN:
        return lead.availability_status

    classification_url = lead.canonical_posting_url or (
        None if is_vertex_redirect_url(lead.discovery_url) else lead.discovery_url
    )
    source_type = classify_result_url(classification_url) if classification_url else SOURCE_TYPE_UNKNOWN

    if classification_url and source_type in PREFERRED_SOURCE_TYPES:
        return AVAILABILITY_UNCERTAIN

    if source_type == SOURCE_TYPE_AGGREGATOR or (
        not lead.canonical_posting_url
        and classify_result_url(lead.discovery_url) == SOURCE_TYPE_AGGREGATOR
    ):
        return AVAILABILITY_AGGREGATOR_ONLY

    if is_vertex_redirect_url(lead.discovery_url) and not lead.canonical_posting_url:
        return AVAILABILITY_UNCERTAIN

    return AVAILABILITY_UNCERTAIN


def enrich_lead(
    lead: DiscoveryLead,
    *,
    preserve_source_family: bool = False,
    preserve_actionability: bool = False,
    preserve_recommendation: bool = False,
) -> DiscoveryLead:
    """Attach domain, source type, availability, and triage fields."""
    classification_url = lead.canonical_posting_url or (
        None if is_vertex_redirect_url(lead.discovery_url) else lead.discovery_url
    )

    if classification_url:
        lead.source_type = classify_result_url(classification_url)
    elif is_vertex_redirect_url(lead.discovery_url):
        lead.source_type = SOURCE_TYPE_UNKNOWN
    else:
        lead.source_type = classify_result_url(lead.discovery_url)

    if not preserve_source_family:
        if is_vertex_redirect_url(lead.discovery_url) and not lead.canonical_posting_url:
            lead.source_family = SOURCE_FAMILY_VERTEX_REDIRECT
        else:
            family_url = lead.canonical_posting_url or lead.discovery_url
            lead.source_family = infer_source_family(family_url)

    lead.display_domain = display_domain_for_lead(lead)
    lead.availability_status = infer_availability_status(lead)

    if not preserve_actionability:
        lead.actionability = infer_actionability(lead)

    if not preserve_recommendation and lead.recommendation is None:
        lead.recommendation = recommendation_for_lead(lead)

    return lead


def enrich_leads(leads: list[DiscoveryLead]) -> list[DiscoveryLead]:
    for lead in leads:
        enrich_lead(lead)
    return leads


def classify_citations(citations: list[DiscoveryLead]) -> list[DiscoveryLead]:
    return enrich_leads(citations)


def all_citations(responses: list[DiscoveryResponse]) -> list[DiscoveryLead]:
    leads: list[DiscoveryLead] = []
    for response in responses:
        leads.extend(response.citations)
    return leads


def active_canonical_leads(leads: list[DiscoveryLead]) -> list[DiscoveryLead]:
    return [
        lead
        for lead in leads
        if lead.availability_status == AVAILABILITY_ACTIVE
        and lead.canonical_posting_url
        and lead.source_type in PREFERRED_SOURCE_TYPES
    ]


def promising_citations(leads: list[DiscoveryLead]) -> list[DiscoveryLead]:
    """Prefer active canonical ATS/employer leads; avoid redirect-only or aggregator echoes."""
    active = active_canonical_leads(leads)
    if active:
        return active

    canonical_preferred = [
        lead
        for lead in leads
        if lead.canonical_posting_url and lead.source_type in PREFERRED_SOURCE_TYPES
    ]
    if canonical_preferred:
        return canonical_preferred

    return [
        lead
        for lead in leads
        if lead.source_type in PREFERRED_SOURCE_TYPES and not is_vertex_redirect_url(lead.discovery_url)
    ]


def group_leads_by_availability(leads: list[DiscoveryLead]) -> dict[str, list[DiscoveryLead]]:
    grouped: dict[str, list[DiscoveryLead]] = {
        AVAILABILITY_ACTIVE: [],
        AVAILABILITY_AGGREGATOR_ONLY: [],
        AVAILABILITY_INACTIVE: [],
        AVAILABILITY_LOGIN_GATED: [],
        AVAILABILITY_UNCERTAIN: [],
    }
    for lead in leads:
        bucket = lead.availability_status
        if bucket not in grouped:
            bucket = AVAILABILITY_UNCERTAIN
        grouped[bucket].append(lead)
    return grouped
