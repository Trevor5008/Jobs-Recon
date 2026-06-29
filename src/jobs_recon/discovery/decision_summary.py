"""Decision-oriented summaries for grounded discovery leads."""

from jobs_recon.discovery.leads import is_vertex_redirect_url
from jobs_recon.discovery.types import (
    ACTIONABILITY_CANONICAL_CANDIDATE,
    ACTIONABILITY_MANUAL_REVIEW,
    ACTIONABILITY_MANUAL_REVIEW_ONLY,
    ACTIONABILITY_NOT_ACTIONABLE,
    ACTIONABILITY_SEARCH_SURFACE_ONLY,
    AVAILABILITY_ACTIVE,
    AVAILABILITY_AGGREGATOR_ONLY,
    AVAILABILITY_INACTIVE,
    AVAILABILITY_LOGIN_GATED,
    AVAILABILITY_UNCERTAIN,
    DiscoveryLead,
)


def _lead_summary_line(lead: DiscoveryLead) -> str:
    label = lead.title or lead.display_domain or lead.discovery_url
    details: list[str] = [f"actionability={lead.actionability}"]
    if lead.source_family and lead.source_family != "unknown":
        details.append(f"family={lead.source_family}")
    if lead.canonical_posting_url:
        details.append("canonical URL available")
    elif is_vertex_redirect_url(lead.discovery_url):
        details.append("redirect-only")
    if lead.availability_status in {
        AVAILABILITY_INACTIVE,
        AVAILABILITY_UNCERTAIN,
        AVAILABILITY_LOGIN_GATED,
    }:
        details.append(f"availability={lead.availability_status}")
    recommendation = lead.recommendation or "Manual review required."
    return f"- **{label}** ({', '.join(details)}): {recommendation}"


def group_leads_for_decision_summary(leads: list[DiscoveryLead]) -> dict[str, list[DiscoveryLead]]:
    more_actionable: list[DiscoveryLead] = []
    investigate: list[DiscoveryLead] = []
    low_actionability: list[DiscoveryLead] = []

    for lead in leads:
        if lead.availability_status in (AVAILABILITY_INACTIVE, AVAILABILITY_LOGIN_GATED):
            low_actionability.append(lead)
            continue

        if lead.availability_status == AVAILABILITY_AGGREGATOR_ONLY:
            if lead.actionability in (
                ACTIONABILITY_MANUAL_REVIEW_ONLY,
                ACTIONABILITY_MANUAL_REVIEW,
            ):
                investigate.append(lead)
                continue
            low_actionability.append(lead)
            continue

        if lead.actionability == ACTIONABILITY_CANONICAL_CANDIDATE:
            if lead.availability_status == AVAILABILITY_ACTIVE or lead.canonical_posting_url:
                more_actionable.append(lead)
            else:
                investigate.append(lead)
            continue

        if lead.actionability in (ACTIONABILITY_MANUAL_REVIEW, ACTIONABILITY_MANUAL_REVIEW_ONLY):
            investigate.append(lead)
            continue

        if lead.actionability in (
            ACTIONABILITY_SEARCH_SURFACE_ONLY,
            ACTIONABILITY_NOT_ACTIONABLE,
        ):
            low_actionability.append(lead)
            continue

        if lead.availability_status == AVAILABILITY_UNCERTAIN and is_vertex_redirect_url(
            lead.discovery_url
        ):
            low_actionability.append(lead)
            continue

        investigate.append(lead)

    return {
        "more_actionable": more_actionable,
        "investigate_manually": investigate,
        "low_actionability": low_actionability,
    }


def render_lead_actionability_summary(leads: list[DiscoveryLead]) -> list[str]:
    if not leads:
        return [
            "## Lead Actionability Summary",
            "",
            "No grounded citations were available for this run.",
            "",
        ]

    grouped = group_leads_for_decision_summary(leads)
    lines: list[str] = [
        "## Lead Actionability Summary",
        "",
        "Grounded citations are discovery evidence only — not full posting descriptions. "
        "Use this summary to decide what to investigate manually next.",
        "",
        "### More actionable",
        "",
    ]

    if grouped["more_actionable"]:
        for lead in grouped["more_actionable"]:
            lines.append(_lead_summary_line(lead))
    else:
        lines.append(
            "_No ATS/employer-style leads marked as canonical candidates in this run._"
        )

    lines.extend(["", "### Investigate manually", ""])
    if grouped["investigate_manually"]:
        for lead in grouped["investigate_manually"]:
            lines.append(_lead_summary_line(lead))
    else:
        lines.append("_None in this run._")

    lines.extend(["", "### Low actionability / caution", ""])
    if grouped["low_actionability"]:
        for lead in grouped["low_actionability"]:
            lines.append(_lead_summary_line(lead))
    else:
        lines.append("_None in this run._")

    lines.extend(
        [
            "",
            "Do not treat aggregator echoes, search surfaces, login-gated pages, stale listings, "
            "or Vertex redirect wrappers as recommended jobs without manual verification.",
            "",
        ]
    )
    return lines
