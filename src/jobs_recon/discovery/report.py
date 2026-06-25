"""Markdown feasibility report for search grounding discovery."""

import json
from collections import Counter

from jobs_recon.discovery.leads import (
    active_canonical_leads,
    all_citations,
    group_leads_by_availability,
    is_vertex_redirect_url,
)
from jobs_recon.discovery.types import (
    AVAILABILITY_ACTIVE,
    AVAILABILITY_AGGREGATOR_ONLY,
    AVAILABILITY_INACTIVE,
    AVAILABILITY_LOGIN_GATED,
    AVAILABILITY_UNCERTAIN,
    DEPRIORITIZED_SOURCE_TYPES,
    PREFERRED_SOURCE_TYPES,
    PROVIDER_GOOGLE_GROUNDING,
    DiscoveryFeasibilityRun,
    DiscoveryLead,
    DiscoveryPrompt,
    DiscoveryResponse,
)


def _count_by_source_type(leads: list[DiscoveryLead]) -> Counter[str]:
    return Counter(lead.source_type for lead in leads)


def assess_viability(leads: list[DiscoveryLead]) -> tuple[str, str]:
    if not leads:
        return (
            "inconclusive",
            "No cited URLs were available to evaluate. Generate prompts and inspect "
            "fixture or live grounding output before deciding.",
        )

    active_canonical = active_canonical_leads(leads)
    if active_canonical:
        return (
            "promising",
            "At least one active canonical ATS or employer URL was identified.",
        )

    counts = _count_by_source_type(leads)
    preferred_count = sum(counts.get(source_type, 0) for source_type in PREFERRED_SOURCE_TYPES)
    deprioritized_count = sum(counts.get(source_type, 0) for source_type in DEPRIORITIZED_SOURCE_TYPES)

    canonical_preferred = [
        lead for lead in leads if lead.canonical_posting_url and lead.source_type in PREFERRED_SOURCE_TYPES
    ]
    if canonical_preferred:
        return (
            "mixed",
            "Canonical ATS or employer URLs appeared, but none were marked active. "
            "Manual URL review is required before import.",
        )

    if preferred_count >= 1 and preferred_count >= deprioritized_count:
        return (
            "mixed",
            "Some ATS or employer signals appeared, but redirect-only or unverified URLs "
            "need manual resolution before import.",
        )

    if deprioritized_count >= 1:
        return (
            "weak",
            "Results skewed toward aggregators, search surfaces, or redirect-only citations "
            "rather than verified canonical posting URLs.",
        )

    return ("inconclusive", "Results were mostly unclassified or redirect-only. Manual URL inspection is required.")


def _format_lead_lines(lead: DiscoveryLead) -> list[str]:
    lines: list[str] = [
        f"- **{lead.title or lead.display_domain or lead.discovery_url}**",
        f"  - Discovery URL: {lead.discovery_url}",
        f"  - Canonical posting URL: {lead.canonical_posting_url or 'not resolved'}",
        f"  - Display domain: {lead.display_domain or 'n/a'}",
        f"  - Source type: {lead.source_type}",
        f"  - Availability: {lead.availability_status}",
    ]
    if is_vertex_redirect_url(lead.discovery_url) and not lead.canonical_posting_url:
        lines.append(
            "  - Note: Vertex redirect wrapper only; resolve manually before treating as actionable."
        )
    if lead.snippet:
        lines.append(f"  - Snippet (triage only): {lead.snippet}")
    return lines


def generate_search_feasibility_report(run: DiscoveryFeasibilityRun) -> str:
    leads = all_citations(run.responses)
    verdict, rationale = assess_viability(leads)
    counts = _count_by_source_type(leads)
    grouped = group_leads_by_availability(leads)

    lines: list[str] = [
        "# Search Feasibility Report: Google Search Grounding",
        "",
        "## Summary",
        "",
        f"- Target: {run.target_name}",
        f"- Target summary: {run.target_summary}",
    ]

    if run.target_path:
        lines.append(f"- Target brief path: `{run.target_path}`")

    lines.extend(
        [
            f"- Mode: {run.mode}",
            f"- Discovery provider: {run.provider}",
            f"- Prompts tested: {len(run.prompts)}",
            f"- Responses captured: {len(run.responses)}",
            f"- Candidate leads: {len(leads)}",
            f"- Active canonical leads: {len(grouped[AVAILABILITY_ACTIVE])}",
            f"- Viability verdict: **{verdict}**",
            "",
            rationale,
            "",
            "## Important Limitations",
            "",
            "- This workflow does **not** scrape Google Jobs or run browser automation.",
            "- Grounded answer text, citations, and snippets are discovery evidence only, "
            "not complete job descriptions.",
            "- Vertex redirect URLs are not canonical posting URLs.",
            "- Do not use grounded text for skill matching or eligibility decisions unless a "
            "full posting is later imported from a canonical source URL or pasted text.",
            "- Aggregator echoes are not actionable postings without a resolved canonical URL.",
            "- The legacy Google Custom Search JSON API is deprecated and not the current path.",
            "",
            "## Prompts Tested",
            "",
        ]
    )
    if run.prompts:
        for index, discovery_prompt in enumerate(run.prompts, start=1):
            lines.extend(
                [
                    f"### Prompt {index}: {discovery_prompt.label}",
                    "",
                    "```text",
                    discovery_prompt.prompt,
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(["No prompts were generated.", ""])

    lines.extend(["## Citation Counts", ""])

    if run.responses:
        for index, response in enumerate(run.responses, start=1):
            lines.append(f"- Response {index}: {len(response.citations)} cited URL(s)")
        lines.append("")
        lines.append("### Likely source types")
        lines.append("")
        for source_type, count in sorted(counts.items()):
            lines.append(f"- {source_type}: {count}")
        lines.append("")
    else:
        lines.extend(
            [
                "- No grounded responses were loaded for this run.",
                "- Use `--fixture` with saved JSON or `--live` with credentials to capture results.",
                "",
            ]
        )

    lines.extend(["## Candidate Leads", ""])

    sections = [
        ("### Active canonical leads", grouped[AVAILABILITY_ACTIVE]),
        ("### Aggregator-only leads", grouped[AVAILABILITY_AGGREGATOR_ONLY]),
        ("### Stale or inactive leads", grouped[AVAILABILITY_INACTIVE]),
        ("### Login-gated leads", grouped[AVAILABILITY_LOGIN_GATED]),
        ("### Uncertain / manual review needed", grouped[AVAILABILITY_UNCERTAIN]),
    ]

    for heading, bucket in sections:
        lines.append(heading)
        lines.append("")
        if bucket:
            for lead in bucket:
                lines.extend(_format_lead_lines(lead))
                lines.append("")
        else:
            lines.append("_None in this run._")
            lines.append("")

    if not grouped[AVAILABILITY_ACTIVE]:
        lines.extend(
            [
                "No active canonical leads were identified in this run. "
                "Resolve discovery URLs manually before import.",
                "",
            ]
        )

    if run.responses:
        lines.extend(["## Grounded Responses (provenance preserved)", ""])
        for index, response in enumerate(run.responses, start=1):
            lines.extend(
                [
                    f"### Response {index}",
                    "",
                    f"- Provider: {response.provider}",
                    f"- Model: {response.model or 'n/a'}",
                    f"- Prompt label: {run.prompts[index - 1].label if index - 1 < len(run.prompts) else 'n/a'}",
                    f"- Timestamp: {response.timestamp or 'n/a'}",
                    "",
                    "#### Prompt",
                    "",
                    "```text",
                    response.prompt,
                    "```",
                    "",
                    "#### Response text (triage only)",
                    "",
                    response.response_text or "_No response text captured._",
                    "",
                    "#### Cited/source URLs",
                    "",
                ]
            )
            if response.citations:
                for lead in response.citations:
                    lines.extend(_format_lead_lines(lead))
                    lines.append("")
            else:
                lines.append("- No cited URLs in this response.")

            if response.grounding_metadata:
                lines.extend(["", "#### Grounding metadata", "", "```json"])
                lines.append(json.dumps(response.grounding_metadata, indent=2, sort_keys=True))
                lines.append("```")

            lines.append("")

    lines.extend(
        [
            "## Recommended Workflow",
            "",
            "1. Run `search-grounding --check-config` to verify Vertex setup.",
            "2. Generate target-aware grounded-search prompts from a target brief.",
            "3. Run fixture or controlled live grounding checks.",
            "4. Resolve discovery URLs to canonical employer or ATS posting pages.",
            "5. Feed selected URLs or pasted posting text into Jobs Recon later.",
            "",
            "## Next Steps",
            "",
            "- Prefer active canonical ATS/employer posting pages over aggregator listings.",
            "- Treat redirect-only and aggregator-only hits as leads, not final sources.",
            "- Re-run with `--live` only when Vertex grounding credentials are ready.",
            "",
        ]
    )

    return "\n".join(lines)


def build_feasibility_run(
    *,
    target_name: str,
    target_summary: str,
    target_path: str | None,
    prompts: list[DiscoveryPrompt],
    responses: list[DiscoveryResponse],
    mode: str,
    provider: str = PROVIDER_GOOGLE_GROUNDING,
) -> DiscoveryFeasibilityRun:
    return DiscoveryFeasibilityRun(
        target_name=target_name,
        target_summary=target_summary,
        target_path=target_path,
        prompts=prompts,
        responses=responses,
        mode=mode,
        provider=provider,
    )
