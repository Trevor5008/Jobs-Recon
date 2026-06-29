"""Deterministic decision buckets for target-aware recon briefs."""

from dataclasses import dataclass

from jobs_recon.models import JobPosting, TargetBrief, TargetMatch

BUCKET_REACHABLE = "reachable"
BUCKET_STRETCH = "stretch"
BUCKET_MISMATCH = "mismatch"


@dataclass(frozen=True)
class DecisionBuckets:
    reachable: tuple[tuple[JobPosting, TargetMatch], ...]
    stretch: tuple[tuple[JobPosting, TargetMatch], ...]
    mismatch: tuple[tuple[JobPosting, TargetMatch], ...]


def _has_matched_required_skill(match: TargetMatch) -> bool:
    return any(reason.startswith("matched required skill:") for reason in match.matched_reasons)


def classify_included_bucket(posting: JobPosting, match: TargetMatch, target: TargetBrief) -> str:
    """Classify an included posting as reachable or stretch."""
    if match.warnings:
        return BUCKET_STRETCH

    if _has_matched_required_skill(match):
        return BUCKET_REACHABLE

    if len(match.matched_reasons) >= 2:
        return BUCKET_REACHABLE

    if not target.required_skills and match.matched_reasons:
        return BUCKET_REACHABLE

    return BUCKET_STRETCH


def build_decision_buckets(
    included: list[tuple[JobPosting, TargetMatch]],
    skipped: list[tuple[JobPosting, TargetMatch]],
    target: TargetBrief,
) -> DecisionBuckets:
    reachable: list[tuple[JobPosting, TargetMatch]] = []
    stretch: list[tuple[JobPosting, TargetMatch]] = []
    mismatch = list(skipped)

    for posting, match in included:
        bucket = classify_included_bucket(posting, match, target)
        if bucket == BUCKET_REACHABLE:
            reachable.append((posting, match))
        else:
            stretch.append((posting, match))

    return DecisionBuckets(
        reachable=tuple(reachable),
        stretch=tuple(stretch),
        mismatch=tuple(mismatch),
    )


def posting_label(posting: JobPosting) -> str:
    return f"{posting.title} — {posting.company}"


def skill_example_labels(postings: list[JobPosting], skill: str, *, limit: int = 3) -> list[str]:
    """Return deterministic example posting labels for a skill."""
    ordered = sorted(postings, key=lambda item: (item.title.casefold(), item.company.casefold()))
    examples: list[str] = []
    for posting in ordered:
        if skill not in posting.skills:
            continue
        examples.append(posting_label(posting))
        if len(examples) >= limit:
            break
    return examples


def format_bucket_entry(posting: JobPosting, match: TargetMatch) -> list[str]:
    lines = [f"- **{posting_label(posting)}**"]
    if posting.location:
        lines.append(f"  - Location: {posting.location}")
    if posting.source_url:
        lines.append(f"  - URL: {posting.source_url}")
    if posting.skills:
        lines.append(f"  - Matched skills: {', '.join(posting.skills)}")
    for reason in match.matched_reasons:
        lines.append(f"  - Matched: {reason}")
    for warning in match.warnings:
        lines.append(f"  - Weak signal: {warning}")
    for reason in match.skipped_reasons:
        lines.append(f"  - Skipped: {reason}")
    return lines


def generate_next_actions(
    *,
    target: TargetBrief,
    buckets: DecisionBuckets,
    skill_counts: list[tuple[str, int]],
    included_count: int,
    skipped_count: int,
) -> list[str]:
    actions: list[str] = []

    if skill_counts:
        top_skills = ", ".join(skill for skill, _count in skill_counts[:5])
        actions.append(f"Compare repeated skills such as {top_skills} against resume/project evidence.")

    if buckets.stretch:
        actions.append(
            "Review stretch postings for recurring gaps before changing the target brief."
        )

    if skipped_count and included_count:
        actions.append(
            "Refine title keywords or location filters if skipped postings look relevant."
        )

    if included_count == 0:
        actions.append(
            "Start by loosening one hard gate, such as title keywords or location, then rerun the same input."
        )

    if buckets.reachable:
        actions.append(
            "Inspect reachable postings manually and import full posting text before relying on skill signals."
        )

    if not actions:
        actions.append("Run another focused recon pass with a tighter target brief or more local postings.")

    actions.append(
        "Treat this as directional signal from a small local sample, not certainty about the wider market."
    )
    return actions[:6]
