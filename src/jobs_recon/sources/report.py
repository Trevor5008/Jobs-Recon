"""Markdown source feasibility reports."""

from jobs_recon.sources.profiles import SourceFeasibilityReport


def generate_feasibility_report(report: SourceFeasibilityReport) -> str:
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

    for limitation in report.known_limitations:
        lines.append(f"- {limitation}")

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

    for path in report.possible_ingestion_paths:
        lines.append(f"- {path}")

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

    for item in report.investigation_checklist:
        lines.append(f"- [ ] {item}")

    lines.append("")
    return "\n".join(lines)
