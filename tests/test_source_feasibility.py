from pathlib import Path

import pytest

from jobs_recon.cli import main
from jobs_recon.source_feasibility import (
    generate_feasibility_report,
    get_source_profile,
    handshake_profile,
)

API_FACT_PATTERNS = (
    "has a public api",
    "provides a public api",
    "api is available",
    "confirmed api",
    "handshake api supports",
)

# Test that the handshake feasibility profile exists
def test_handshake_feasibility_profile_exists():
    profile = handshake_profile()

    assert profile.source_name == "Handshake"
    assert profile.source_type == "university / early-career job board"
    assert "internships" in profile.expected_signal
    assert profile.access_model == "likely authenticated / school-affiliated"
    assert len(profile.known_limitations) >= 3
    assert len(profile.possible_ingestion_paths) >= 3
    assert profile.recommended_next_step


# Test that the get_source_profile function accepts handshake as an alias
def test_get_source_profile_accepts_handshake_alias():
    profile = get_source_profile("handshake")
    assert profile.source_name == "Handshake"


# Test that the get_source_profile function rejects unknown sources
def test_get_source_profile_rejects_unknown_source():
    with pytest.raises(ValueError, match="Unknown source"):
        get_source_profile("unknown-board")


# Test that the markdown report includes required sections
def test_markdown_report_includes_required_sections():
    report = generate_feasibility_report(handshake_profile())

    assert "Source Feasibility Report: Handshake" in report
    assert "Handshake" in report
    assert "## Possible Ingestion Paths" in report
    assert "## Manual Investigation Checklist" in report
    assert "- [ ] Check whether Handshake provides export/download options" in report
    assert "direct adapter only if supported by terms and access model" in report


# Test that the markdown report does not claim direct API support
def test_markdown_report_does_not_claim_direct_api_support():
    report = generate_feasibility_report(handshake_profile()).lower()

    for pattern in API_FACT_PATTERNS:
        assert pattern not in report

    assert "may not expose a public api" in report
    assert "unknown until terms/access are reviewed" in report


# Test that the CLI writes feasibility markdown output
def test_cli_writes_feasibility_markdown_output(tmp_path: Path):
    output_path = tmp_path / "handshake_feasibility.md"
    exit_code = main(
        [
            "source-feasibility",
            "--source",
            "handshake",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "Source Feasibility Report: Handshake" in content
    assert "Possible Ingestion Paths" in content
    assert "Manual Investigation Checklist" in content

    lowered = content.lower()
    for pattern in API_FACT_PATTERNS:
        assert pattern not in lowered
