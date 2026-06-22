"""Markdown feasibility report for Google dork / JSON search discovery."""

from collections import Counter

from jobs_recon.search_discovery import (
    DEPRIORITIZED_SOURCE_TYPES,
    PREFERRED_SOURCE_TYPES,
    SEARCH_PROVIDER_GOOGLE,
    SearchFeasibilityRun,
    SearchQuery,
    SearchResult,
    promising_results,
)


def _count_by_source_type(results: list[SearchResult]) -> Counter[str]:
    return Counter(result.source_type for result in results)


def assess_viability(results: list[SearchResult]) -> tuple[str, str]:
    """Return (verdict, rationale) for whether this discovery path looks viable."""
    if not results:
        return (
            "inconclusive",
            "No search results were available to evaluate. Generate dorks and inspect "
            "fixture or live JSON output before deciding.",
        )

    counts = _count_by_source_type(results)
    preferred_count = sum(counts.get(source_type, 0) for source_type in PREFERRED_SOURCE_TYPES)
    deprioritized_count = sum(
        counts.get(source_type, 0) for source_type in DEPRIORITIZED_SOURCE_TYPES
    )

    if preferred_count >= 1 and preferred_count >= deprioritized_count:
        return (
            "promising",
            "At least one ATS or employer URL appeared, and preferred URLs were not "
            "outnumbered by aggregators or Google search surfaces.",
        )

    if preferred_count >= 1:
        return (
            "mixed",
            "Some ATS or employer URLs appeared, but aggregators or Google search "
            "surfaces were also common. Treat results as triage-only.",
        )

    if deprioritized_count >= 1:
        return (
            "weak",
            "Results skewed toward aggregators or Google search surfaces rather than "
            "canonical employer or ATS posting URLs.",
        )

    return (
        "inconclusive",
        "Results were mostly unclassified. Manual URL inspection is required before "
        "using this source path.",
    )


def generate_search_feasibility_report(run: SearchFeasibilityRun) -> str:
    """Build a deterministic Markdown feasibility report for search discovery."""
    verdict, rationale = assess_viability(run.results)
    counts = _count_by_source_type(run.results)
    promising = promising_results(run.results)

    lines: list[str] = [
        "# Search Feasibility Report: Google Dorking / JSON Search",
        "",
        "## Summary",
        "",
        f"- Target: {run.target_name}",
        f"- Mode: {run.mode}",
        f"- Search provider: {run.provider}",
        f"- Queries tested: {len(run.queries)}",
        f"- Results captured: {len(run.results)}",
        f"- Viability verdict: **{verdict}**",
        "",
        rationale,
        "",
        "## Important Limitations",
        "",
        "- This workflow does **not** scrape Google Jobs or run browser automation.",
        "- Google JSON API snippets are discovery evidence only, not complete job descriptions.",
        "- Do not use snippets for skill matching or eligibility decisions unless a full posting "
        "is later imported into Jobs Recon.",
        "- CAPTCHA bypass, login automation, and broad crawling are out of scope.",
        "",
        "## Queries Tested",
        "",
    ]

    if run.queries:
        for index, search_query in enumerate(run.queries, start=1):
            lines.extend(
                [
                    f"### Query {index}: {search_query.label}",
                    "",
                    f"```text",
                    search_query.query,
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(["No queries were generated.", ""])

    lines.extend(["## Result Counts", ""])

    if run.results:
        result_counts = Counter(result.query for result in run.results)
        for search_query in run.queries:
            count = result_counts.get(search_query.query, 0)
            lines.append(f"- {search_query.label}: {count} result(s)")
        lines.append("")
        lines.append("### Likely source types")
        lines.append("")
        for source_type, count in sorted(counts.items()):
            lines.append(f"- {source_type}: {count}")
        lines.append("")
    else:
        lines.extend(
            [
                "- No search results were loaded for this run.",
                "- Use `--fixture` with saved JSON or `--live` with credentials to capture results.",
                "",
            ]
        )

    lines.extend(["## Promising URLs", ""])

    if promising:
        for result in promising:
            domain = result.display_link or result.url
            lines.extend(
                [
                    f"- **{result.title}**",
                    f"  - URL: {result.url}",
                    f"  - Domain: {domain}",
                    f"  - Source type: {result.source_type}",
                    f"  - Query: `{result.query}`",
                ]
            )
            if result.snippet:
                lines.append(f"  - Snippet (triage only): {result.snippet}")
            lines.append("")
    else:
        lines.extend(
            [
                "No ATS or employer URLs were identified as promising in this run.",
                "",
            ]
        )

    if run.results:
        lines.extend(["## All Results (provenance preserved)", ""])
        for index, result in enumerate(run.results, start=1):
            lines.extend(
                [
                    f"### Result {index}",
                    "",
                    f"- Query: `{result.query}`",
                    f"- Title: {result.title}",
                    f"- URL: {result.url}",
                    f"- Display link: {result.display_link or 'n/a'}",
                    f"- Provider: {result.provider}",
                    f"- Source type: {result.source_type}",
                    f"- Snippet: {result.snippet or 'n/a'}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Recommended Workflow",
            "",
            "1. Generate target-aware dorks from a target brief.",
            "2. Inspect JSON/search results manually or via fixture output.",
            "3. Select promising canonical employer or ATS URLs.",
            "4. Feed selected URLs or pasted posting text into Jobs Recon later.",
            "",
            "## Next Steps",
            "",
            "- Prefer importing canonical ATS/employer posting pages over aggregator listings.",
            "- Treat aggregator and Google search-surface hits as leads, not final sources.",
            "- Re-run with `--live` only when `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` are configured.",
            "",
        ]
    )

    return "\n".join(lines)


def build_feasibility_run(
    *,
    target_name: str,
    queries: list[SearchQuery],
    results: list[SearchResult],
    mode: str,
    provider: str = SEARCH_PROVIDER_GOOGLE,
) -> SearchFeasibilityRun:
    return SearchFeasibilityRun(
        target_name=target_name,
        queries=queries,
        results=results,
        mode=mode,
        provider=provider,
    )
