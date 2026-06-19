from collections import Counter

from jobs_recon.models import JobPosting


def _pluralize_postings(count: int) -> str:
    return "1 posting" if count == 1 else f"{count} postings"


def _format_locations(postings: list[JobPosting]) -> str:
    locations = sorted({p.location for p in postings if p.location})
    return "; ".join(locations) if locations else "Not specified"


def _skill_counts(postings: list[JobPosting]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for posting in postings:
        for skill in posting.skills:
            counts[skill] += 1

    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def generate_brief(postings: list[JobPosting]) -> str:
    """Build a deterministic Markdown recon brief from parsed postings."""
    lines: list[str] = [
        "# Jobs Recon Brief",
        "",
        "## Summary",
        "",
        f"- Postings analyzed: {len(postings)}",
        f"- Companies represented: {len({p.company for p in postings})}",
        f"- Locations represented: {_format_locations(postings)}",
        "",
        "## Repeated Skills",
        "",
    ]

    skill_counts = _skill_counts(postings)
    if skill_counts:
        for skill, count in skill_counts:
            lines.append(f"- {skill}: {_pluralize_postings(count)}")
    else:
        lines.append("- No vocabulary skills matched in this sample.")

    lines.extend(["", "## Posting Notes", ""])

    for posting in postings:
        lines.append(f"### {posting.title} — {posting.company}")
        lines.append("")
        if posting.location:
            lines.append(f"- Location: {posting.location}")
        if posting.source:
            lines.append(f"- Source: {posting.source}")
        if posting.source_url:
            lines.append(f"- URL: {posting.source_url}")
        if posting.skills:
            lines.append(f"- Matched skills: {', '.join(posting.skills)}")
        else:
            lines.append("- Matched skills: None")
        lines.append("")

    lines.extend(
        [
            "## Next Actions",
            "",
            "- Treat this as directional signal only; the sample is small.",
            "- Compare repeated skills against current resume/project evidence.",
            "- Run another focused recon pass with a tighter target brief.",
            "",
        ]
    )

    return "\n".join(lines)
