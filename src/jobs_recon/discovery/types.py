"""Discovery dataclasses and constants."""

from dataclasses import dataclass, field

PROVIDER_GOOGLE_GROUNDING = "google_grounding"
PROVIDER_MANUAL_FIXTURE = "manual_fixture"

SOURCE_TYPE_ATS = "ats"
SOURCE_TYPE_EMPLOYER = "employer"
SOURCE_TYPE_AGGREGATOR = "aggregator"
SOURCE_TYPE_SEARCH_SURFACE = "search_surface"
SOURCE_TYPE_IRRELEVANT = "irrelevant"
SOURCE_TYPE_UNKNOWN = "unknown"

AVAILABILITY_ACTIVE = "active"
AVAILABILITY_INACTIVE = "inactive"
AVAILABILITY_LOGIN_GATED = "login_gated"
AVAILABILITY_AGGREGATOR_ONLY = "aggregator_only"
AVAILABILITY_UNCERTAIN = "uncertain"

PREFERRED_SOURCE_TYPES = (SOURCE_TYPE_ATS, SOURCE_TYPE_EMPLOYER)
DEPRIORITIZED_SOURCE_TYPES = (
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_SEARCH_SURFACE,
    SOURCE_TYPE_IRRELEVANT,
)

VERTEX_REDIRECT_HOST = "vertexaisearch.cloud.google.com"
VERTEX_REDIRECT_PATH_PREFIX = "/grounding-api-redirect/"

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
    ("jobleads.com",),
    ("remoterocketship.com",),
    ("prosple.com",),
    ("workingnomads.com",),
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
class DiscoveryLead:
    discovery_url: str
    title: str | None = None
    snippet: str | None = None
    canonical_posting_url: str | None = None
    display_domain: str | None = None
    source_type: str = SOURCE_TYPE_UNKNOWN
    availability_status: str = AVAILABILITY_UNCERTAIN

    @property
    def url(self) -> str:
        """Backward-compatible alias for discovery_url."""
        return self.discovery_url


DiscoveryCitation = DiscoveryLead


@dataclass
class DiscoveryResponse:
    provider: str
    model: str | None
    prompt: str
    response_text: str
    citations: list[DiscoveryLead] = field(default_factory=list)
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
