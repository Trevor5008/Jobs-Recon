"""Target-aware search query generation and result URL classification."""

from dataclasses import dataclass, field
from urllib.parse import urlparse

from jobs_recon.models import TargetBrief

SEARCH_PROVIDER_GOOGLE = "google_custom_search_json"

SOURCE_TYPE_ATS = "ats"
SOURCE_TYPE_EMPLOYER = "employer"
SOURCE_TYPE_AGGREGATOR = "aggregator"
SOURCE_TYPE_GOOGLE_SURFACE = "google_jobs_or_search_surface"
SOURCE_TYPE_IRRELEVANT = "irrelevant"
SOURCE_TYPE_UNKNOWN = "unknown"

PREFERRED_SOURCE_TYPES = (SOURCE_TYPE_ATS, SOURCE_TYPE_EMPLOYER)
DEPRIORITIZED_SOURCE_TYPES = (
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_GOOGLE_SURFACE,
    SOURCE_TYPE_IRRELEVANT,
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

GOOGLE_SURFACE_DOMAIN_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("google.com", "search"),
    ("google.com", "about", "careers", "search"),
    ("jobs.google.com",),
)

SITE_SPECIFIC_DORKS: tuple[tuple[str, str], ...] = (
    ("greenhouse.io", "Greenhouse ATS postings"),
    ("jobs.lever.co", "Lever ATS postings"),
    ("ashbyhq.com", "Ashby ATS postings"),
    ("workable.com", "Workable ATS postings"),
)


@dataclass(frozen=True)
class SearchQuery:
    query: str
    label: str


@dataclass
class SearchResult:
    query: str
    title: str
    url: str
    snippet: str
    display_link: str | None = None
    provider: str = SEARCH_PROVIDER_GOOGLE
    source_type: str = SOURCE_TYPE_UNKNOWN

    def with_classification(self, source_type: str) -> "SearchResult":
        self.source_type = source_type
        return self


@dataclass
class SearchFeasibilityRun:
    target_name: str
    queries: list[SearchQuery] = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)
    mode: str = "dry-run"
    provider: str = SEARCH_PROVIDER_GOOGLE


def _quote_phrase(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if " " in cleaned or '"' in cleaned:
        escaped = cleaned.replace('"', "")
        return f'"{escaped}"'
    return cleaned


def _or_group(values: list[str]) -> str:
    phrases = [_quote_phrase(value) for value in values if value.strip()]
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    return f"({' OR '.join(phrases)})"


def generate_dork_queries(target: TargetBrief) -> list[SearchQuery]:
    """Build deterministic Google dork queries from a target brief."""
    title_group = _or_group(target.title_keywords)
    seniority_group = _or_group(target.seniority)
    location_group = _or_group(target.locations)

    core_parts = [part for part in (title_group, seniority_group, location_group) if part]
    queries: list[SearchQuery] = []

    if core_parts:
        queries.append(
            SearchQuery(
                query=" ".join(core_parts),
                label="General target-aware dork",
            )
        )

    site_parts = [part for part in (title_group, location_group) if part]
    if site_parts:
        site_query_body = " ".join(site_parts)
        for domain, label in SITE_SPECIFIC_DORKS:
            queries.append(
                SearchQuery(
                    query=f"site:{domain} {site_query_body}",
                    label=label,
                )
            )

    if target.seniority and title_group and location_group:
        queries.append(
            SearchQuery(
                query=(
                    f"site:ashbyhq.com {title_group} {seniority_group} "
                    f"{location_group}"
                ),
                label="Ashby ATS with seniority lane",
            )
        )

    return queries


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

    for pattern in GOOGLE_SURFACE_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern) and _path_matches_pattern(path_segments, pattern):
            return SOURCE_TYPE_GOOGLE_SURFACE

    for pattern in AGGREGATOR_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern) and _path_matches_pattern(path_segments, pattern):
            return SOURCE_TYPE_AGGREGATOR

    for pattern in ATS_DOMAIN_PATTERNS:
        if _host_matches_pattern(host, pattern):
            return SOURCE_TYPE_ATS

    if host.endswith(".com") or host.endswith(".io") or host.endswith(".co"):
        return SOURCE_TYPE_EMPLOYER

    return SOURCE_TYPE_UNKNOWN


def classify_search_results(results: list[SearchResult]) -> list[SearchResult]:
    """Attach source_type classification to each search result."""
    for result in results:
        result.source_type = classify_result_url(result.url)
    return results


def parse_google_search_items(
    payload: dict,
    query: str,
    *,
    provider: str = SEARCH_PROVIDER_GOOGLE,
) -> list[SearchResult]:
    """Parse a Google Custom Search JSON API response into SearchResult rows."""
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise ValueError("Google search response items must be a list")

    results: list[SearchResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("link")
        title = item.get("title")
        if not isinstance(url, str) or not isinstance(title, str):
            continue
        snippet = item.get("snippet")
        display_link = item.get("displayLink")
        results.append(
            SearchResult(
                query=query,
                title=title,
                url=url,
                snippet=snippet if isinstance(snippet, str) else "",
                display_link=display_link if isinstance(display_link, str) else None,
                provider=provider,
            )
        )

    return classify_search_results(results)


def promising_results(results: list[SearchResult]) -> list[SearchResult]:
    """Prefer canonical ATS/employer URLs over aggregators and search surfaces."""
    preferred = [result for result in results if result.source_type in PREFERRED_SOURCE_TYPES]
    if preferred:
        return preferred
    return [result for result in results if result.source_type not in DEPRIORITIZED_SOURCE_TYPES]
