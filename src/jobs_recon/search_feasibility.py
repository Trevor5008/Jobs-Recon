"""Markdown feasibility report for search grounding discovery."""

import json
from collections import Counter

from jobs_recon.search_discovery import (
    DEPRIORITIZED_SOURCE_TYPES,
    PREFERRED_SOURCE_TYPES,
    PROVIDER_GOOGLE_GROUNDING,
    DiscoveryFeasibilityRun,
    DiscoveryPrompt,
    DiscoveryResponse,
    all_citations,
    promising_citations,
)


def _count_by_source_type(citations) -> Counter[str]:
    return Counter(citation.source_type for citation in citations)


def assess_viability(citations) -> tuple[str, str]:
    """Return (verdict, rationale) for whether this discovery path looks viable."""
    if not citations:
        return (
            "inconclusive",
            "No cited URLs were available to evaluate. Generate prompts and inspect "
            "fixture or live grounding output before deciding.",
        )

    counts = _count_by_source_type(citations)
    preferred_count = sum(counts.get(source_type, 0) for source_type in PREFERRED_SOURCE_TYPES)
    deprioritized_count = sum(
        counts.get(source_type, 0) for source_type in DEPRIORITIZED_SOURCE_TYPES
    )

    if preferred_count >= 1 and preferred_count >= deprioritized_count:
        return (
            "promising",
            "At least one ATS or employer URL appeared, and preferred URLs were not "
            "outnumbered by aggregators or search surfaces.",
        )

    if preferred_count >= 1:
        return (
            "mixed",
            "Some ATS or employer URLs appeared, but aggregators or search surfaces "
            "were also common. Treat results as triage-only.",
        )

    if deprioritized_count >= 1:
        return (
            "weak",
            "Results skewed toward aggregators or search surfaces rather than "
            "canonical employer or ATS posting URLs.",
        )

    return (
        "inconclusive",
        "Results were mostly unclassified. Manual URL inspection is required before "
        "using this source path.",
    )


def generate_search_feasibility_report(run: DiscoveryFeasibilityRun) -> str:
    """Build a deterministic Markdown feasibility report for search grounding."""
    citations = all_citations(run.responses)
    verdict, rationale = assess_viability(citations)
    counts = _count_by_source_type(citations)
    promising = promising_citations(citations)

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
            f"- Cited/source URLs: {len(citations)}",
            f"- Viability verdict: **{verdict}**",
            "",
            rationale,
            "",
            "## Important Limitations",
            "",
            "- This workflow does **not** scrape Google Jobs or run browser automation.",
            "- Grounded answer text, citations, and snippets are discovery evidence only, "
            "not complete job descriptions.",
            "- Do not use grounded text for skill matching or eligibility decisions unless a "
            "full posting is later imported from a canonical source URL or pasted text.",
            "- CAPTCHA bypass, login automation, broad crawling, and the legacy Google Custom "
            "Search JSON API are out of scope.",
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

    lines.extend(["## Promising URLs", ""])

    if promising:
        for citation in promising:
            lines.extend(
                [
                    f"- **{citation.title or citation.url}**",
                    f"  - URL: {citation.url}",
                    f"  - Source type: {citation.source_type}",
                ]
            )
            if citation.snippet:
                lines.append(f"  - Snippet (triage only): {citation.snippet}")
            lines.append("")
    else:
        lines.extend(
            [
                "No ATS or employer URLs were identified as promising in this run.",
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
                for citation in response.citations:
                    lines.extend(
                        [
                            f"- **{citation.title or citation.url}**",
                            f"  - URL: {citation.url}",
                            f"  - Source type: {citation.source_type}",
                        ]
                    )
                    if citation.snippet:
                        lines.append(f"  - Snippet: {citation.snippet}")
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
            "1. Generate target-aware grounded-search prompts from a target brief.",
            "2. Run fixture or controlled live grounding checks.",
            "3. Inspect cited/source URLs manually.",
            "4. Select promising canonical employer or ATS URLs.",
            "5. Feed selected URLs or pasted posting text into Jobs Recon later.",
            "",
            "## Next Steps",
            "",
            "- Prefer importing canonical ATS/employer posting pages over aggregator listings.",
            "- Treat aggregator and search-surface citations as leads, not final sources.",
            "- Re-run with `--live` only when Gemini / Vertex grounding credentials are configured.",
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
