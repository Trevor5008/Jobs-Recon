"""Source profiles for feasibility reports."""

from dataclasses import dataclass

HANDSHAKE_INVESTIGATION_CHECKLIST: tuple[str, ...] = (
    "Check whether Handshake provides export/download options",
    "Check whether saved searches can produce email alerts",
    "Check whether postings have stable URLs",
    "Check whether relevant fields can be copied manually",
    "Check whether terms permit automated access",
    "Check whether school affiliation affects available postings",
    "Decide whether MVP 0.3 should use manual import, email digest import, or a direct adapter",
)


@dataclass
class SourceFeasibilityReport:
    source_name: str
    source_type: str
    expected_signal: str
    access_model: str
    automation_risk: str
    known_limitations: list[str]
    possible_ingestion_paths: list[str]
    recommended_next_step: str
    investigation_checklist: list[str]


def handshake_profile() -> SourceFeasibilityReport:
    return SourceFeasibilityReport(
        source_name="Handshake",
        source_type="university / early-career job board",
        expected_signal=(
            "high for internships, student roles, new-grad roles, "
            "and school-affiliated recruiting"
        ),
        access_model="likely authenticated / school-affiliated",
        automation_risk="unknown until terms/access are reviewed",
        known_limitations=[
            "may require user login",
            "may not expose a public API",
            "may restrict automated access",
            "available postings may depend on school affiliation",
        ],
        possible_ingestion_paths=[
            "manual copy/paste into local JSON",
            "saved-search email digest ingestion",
            "manual export if available",
            "direct adapter only if supported by terms and access model",
        ],
        recommended_next_step=(
            "inspect logged-in Handshake account manually for export, saved search, "
            "alert, or API options before implementing any adapter"
        ),
        investigation_checklist=list(HANDSHAKE_INVESTIGATION_CHECKLIST),
    )


SOURCE_PROFILES: dict[str, SourceFeasibilityReport] = {
    "handshake": handshake_profile(),
}


def get_source_profile(source_key: str) -> SourceFeasibilityReport:
    key = source_key.strip().lower()
    if key not in SOURCE_PROFILES:
        known = ", ".join(sorted(SOURCE_PROFILES))
        raise ValueError(f"Unknown source {source_key!r}. Known sources: {known}")

    return SOURCE_PROFILES[key]
