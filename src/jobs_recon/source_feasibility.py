"""Source feasibility report for Handshake."""
from dataclasses import dataclass

# Define the handshake investigation checklist
HANDSHAKE_INVESTIGATION_CHECKLIST: tuple[str, ...] = (
    "Check whether Handshake provides export/download options",
    "Check whether saved searches can produce email alerts",
    "Check whether postings have stable URLs",
    "Check whether relevant fields can be copied manually",
    "Check whether terms permit automated access",
    "Check whether school affiliation affects available postings",
    "Decide whether MVP 0.3 should use manual import, email digest import, or a direct adapter",
)

# Define the source feasibility report
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

# Define the handshake profile
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

# Define the source profiles
SOURCE_PROFILES: dict[str, SourceFeasibilityReport] = {
    "handshake": handshake_profile(),
}

# Get a source profile
def get_source_profile(source_key: str) -> SourceFeasibilityReport:
    key = source_key.strip().lower()
    if key not in SOURCE_PROFILES:
        known = ", ".join(sorted(SOURCE_PROFILES))
        raise ValueError(f"Unknown source {source_key!r}. Known sources: {known}")

    return SOURCE_PROFILES[key]

# Generate a feasibility report
def generate_feasibility_report(report: SourceFeasibilityReport) -> str:
    # Build the lines
    lines: list[str] = [
        f"# Source Feasibility Report: {report.source_name}",
        "",
        "## Summary",
        "",
        f"- Source type: {report.source_type}",
        f"- Access model: {report.access_model}",
        f"- Automation risk: {report.automation_risk}",
        "",
        "## Expected Signal",
        "",
        report.expected_signal,
        "",
        "## Access / Automation Considerations",
        "",
        "Known limitations (needs investigation):",
        "",
    ]

    # Add the known limitations
    for limitation in report.known_limitations:
        lines.append(f"- {limitation}")

    # Add the possible ingestion paths
    lines.extend(
        [
            "",
            "No public API access or automated ingestion should be assumed unless "
            "verified manually and permitted by terms.",
            "",
            "## Possible Ingestion Paths",
            "",
        ]
    )

    # Add the possible ingestion paths
    for path in report.possible_ingestion_paths:
        lines.append(f"- {path}")

    # Add the recommendation
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            report.recommended_next_step,
            "",
            "## Manual Investigation Checklist",
            "",
        ]
    )

    # Add the investigation checklist
    for item in report.investigation_checklist:
        lines.append(f"- [ ] {item}")

    # Add the empty line
    lines.append("")
    return "\n".join(lines)
