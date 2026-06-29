from collections import Counter

from jobs_recon.brief.decision import (
    build_decision_buckets,
    format_bucket_entry,
    generate_next_actions,
    skill_example_labels,
)
from jobs_recon.brief.target import evaluate_postings_against_target
from jobs_recon.models import JobPosting, TargetBrief, TargetMatch


def _pluralize_postings(count: int) -> str:
    return "1 posting" if count == 1 else f"{count} postings"


def _format_locations(postings: list[JobPosting]) -> str:
    locations = sorted({p.location for p in postings if p.location})
    return "; ".join(locations) if locations else "Not specified"


def _format_list(values: list[str]) -> str:
    return "; ".join(values) if values else "Not specified"


def _skill_counts(postings: list[JobPosting]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for posting in postings:
        for skill in posting.skills:
            counts[skill] += 1

    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _append_repeated_skills_section(lines: list[str], postings: list[JobPosting]) -> None:
    lines.extend(["## Repeated Skills", ""])
    skill_counts = _skill_counts(postings)
    if skill_counts:
        for skill, count in skill_counts:
            lines.append(f"- {skill}: {_pluralize_postings(count)}")
            examples = skill_example_labels(postings, skill)
            if examples:
                lines.append(f"  - Examples: {'; '.join(examples)}")
    else:
        lines.append("- No vocabulary skills matched in the included postings.")


def _append_posting_note(lines: list[str], posting: JobPosting, match: TargetMatch | None) -> None:
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

    if match is not None:
        for reason in match.matched_reasons:
            lines.append(f"- Matched reason: {reason}")
        for warning in match.warnings:
            lines.append(f"- Warning: {warning}")

    lines.append("")


def _append_target_brief_section(lines: list[str], target: TargetBrief) -> None:
    lines.extend(
        [
            "## Target Brief",
            "",
            f"- Name: {target.name}",
            f"- Role family: {target.role_family or 'Not specified'}",
            f"- Title keywords: {_format_list(target.title_keywords)}",
            f"- Locations: {_format_list(target.locations)}",
            f"- Remote preference: {target.remote_preference or 'Not specified'}",
            f"- Seniority: {_format_list(target.seniority)}",
            f"- Required skills: {_format_list(target.required_skills)}",
            "",
        ]
    )
    if target.notes:
        lines.append(f"- Notes: {target.notes}")
        lines.append("")


def _append_target_match_summary(
    lines: list[str],
    input_count: int,
    included_count: int,
    skipped_count: int,
) -> None:
    lines.extend(
        [
            "## Target Match Summary",
            "",
            f"- Input postings: {input_count}",
            f"- Included postings: {included_count}",
            f"- Skipped postings: {skipped_count}",
            "",
        ]
    )


def _append_decision_buckets_section(
    lines: list[str],
    buckets,
) -> None:
    lines.extend(
        [
            "## Decision Buckets",
            "",
            "Explanation buckets for manual triage — not rankings or recommendations.",
            "",
            "### Reachable",
            "",
        ]
    )
    if buckets.reachable:
        for posting, match in buckets.reachable:
            lines.extend(format_bucket_entry(posting, match))
            lines.append("")
    else:
        lines.append("_None in this run._")
        lines.append("")

    lines.extend(["### Stretch", ""])
    if buckets.stretch:
        for posting, match in buckets.stretch:
            lines.extend(format_bucket_entry(posting, match))
            lines.append("")
    else:
        lines.append("_None in this run._")
        lines.append("")

    lines.extend(["### Mismatch", ""])
    if buckets.mismatch:
        for posting, match in buckets.mismatch:
            lines.extend(format_bucket_entry(posting, match))
            lines.append("")
    else:
        lines.append("_None in this run._")
        lines.append("")


def _append_skipped_postings_section(
    lines: list[str],
    skipped: list[tuple[JobPosting, TargetMatch]],
) -> None:
    if not skipped:
        return

    lines.extend(["## Skipped Postings", ""])
    for posting, match in skipped:
        lines.append(f"### {posting.title} — {posting.company}")
        lines.append("")
        for reason in match.skipped_reasons:
            lines.append(f"- Reason: {reason}")
        lines.append("")


def generate_brief(postings: list[JobPosting], target: TargetBrief | None = None) -> str:
    """Build a deterministic Markdown recon brief from parsed postings."""
    if target is None:
        return _generate_brief_without_target(postings)

    included_pairs, skipped_pairs = evaluate_postings_against_target(postings, target)
    included_postings = [posting for posting, _match in included_pairs]
    buckets = build_decision_buckets(list(included_pairs), list(skipped_pairs), target)
    skill_counts = _skill_counts(included_postings)

    lines: list[str] = ["# Jobs Recon Brief", ""]
    _append_target_brief_section(lines, target)
    _append_target_match_summary(lines, len(postings), len(included_pairs), len(skipped_pairs))

    lines.extend(["## Summary", ""])
    if included_postings:
        lines.extend(
            [
                f"- Postings analyzed: {len(included_postings)}",
                f"- Companies represented: {len({p.company for p in included_postings})}",
                f"- Locations represented: {_format_locations(included_postings)}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "- Postings analyzed: 0",
                "- No postings matched the target brief.",
                "",
            ]
        )

    _append_decision_buckets_section(lines, buckets)
    _append_repeated_skills_section(lines, included_postings)

    lines.extend(["", "## Posting Notes", ""])
    if included_pairs:
        for posting, match in included_pairs:
            _append_posting_note(lines, posting, match)
    else:
        lines.append("No postings matched the target brief.")
        lines.append("")

    _append_skipped_postings_section(lines, skipped_pairs)

    next_actions = generate_next_actions(
        target=target,
        buckets=buckets,
        skill_counts=skill_counts,
        included_count=len(included_pairs),
        skipped_count=len(skipped_pairs),
    )
    lines.extend(["## Next Actions", ""])
    for action in next_actions:
        lines.append(f"- {action}")
    lines.append("")

    return "\n".join(lines)


def _generate_brief_without_target(postings: list[JobPosting]) -> str:
    lines: list[str] = [
        "# Jobs Recon Brief",
        "",
        "## Summary",
        "",
        f"- Postings analyzed: {len(postings)}",
        f"- Companies represented: {len({p.company for p in postings})}",
        f"- Locations represented: {_format_locations(postings)}",
        "",
        "Decision buckets require a target brief.",
        "",
        "## Repeated Skills",
        "",
    ]

    skill_counts = _skill_counts(postings)
    if skill_counts:
        for skill, count in skill_counts:
            lines.append(f"- {skill}: {_pluralize_postings(count)}")
            examples = skill_example_labels(postings, skill)
            if examples:
                lines.append(f"  - Examples: {'; '.join(examples)}")
    else:
        lines.append("- No vocabulary skills matched in this sample.")

    lines.extend(["", "## Posting Notes", ""])
    for posting in postings:
        _append_posting_note(lines, posting, None)

    lines.extend(
        [
            "## Next Actions",
            "",
            "- Compare repeated skills against current resume/project evidence.",
            "- Add a target brief when you want reachable/stretch/mismatch decision buckets.",
            "- Treat this as directional signal from a small local sample, not certainty about the wider market.",
            "",
        ]
    )

    return "\n".join(lines)
