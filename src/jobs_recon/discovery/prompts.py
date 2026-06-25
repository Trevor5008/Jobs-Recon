"""Target-aware discovery prompt generation."""

from jobs_recon.discovery.types import (
    CANONICAL_ATS_GUIDANCE,
    DiscoveryPrompt,
    SITE_SPECIFIC_PROMPTS,
)
from jobs_recon.models import TargetBrief


def summarize_target(target: TargetBrief) -> str:
    """Build a short target summary for provenance in reports."""
    lines = [f"Name: {target.name}"]
    if target.role_family:
        lines.append(f"Role family: {target.role_family}")
    if target.title_keywords:
        lines.append(f"Title keywords: {', '.join(target.title_keywords)}")
    if target.locations:
        lines.append(f"Locations: {', '.join(target.locations)}")
    if target.seniority:
        lines.append(f"Seniority: {', '.join(target.seniority)}")
    if target.required_skills:
        lines.append(f"Required skills: {', '.join(target.required_skills)}")
    return "; ".join(lines)


def generate_discovery_prompts(target: TargetBrief) -> list[DiscoveryPrompt]:
    """Build deterministic grounded-search prompts from a target brief."""
    title_keywords = ", ".join(target.title_keywords) or "AI/software roles"
    locations = ", ".join(target.locations) or "any listed location"
    seniority = ", ".join(target.seniority) or "entry-level, junior, or intern"

    prompts: list[DiscoveryPrompt] = [
        DiscoveryPrompt(
            prompt=(
                f"Find current public job postings for {seniority} AI/software roles "
                f"matching titles such as {title_keywords} around {locations}. "
                f"{CANONICAL_ATS_GUIDANCE}"
            ),
            label="General grounded discovery prompt",
        )
    ]

    for platform, label in SITE_SPECIFIC_PROMPTS:
        prompts.append(
            DiscoveryPrompt(
                prompt=(
                    f"Find current public job postings for {title_keywords} on {platform} "
                    f"around {locations}, focusing on {seniority} roles. "
                    f"{CANONICAL_ATS_GUIDANCE}"
                ),
                label=label,
            )
        )

    return prompts
