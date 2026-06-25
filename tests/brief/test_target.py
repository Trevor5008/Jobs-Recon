import json
from pathlib import Path

import pytest

from jobs_recon.brief.io import load_postings
from jobs_recon.brief.report import generate_brief
from jobs_recon.brief.target import evaluate_posting_against_target, load_target_brief
from jobs_recon.cli import main
from jobs_recon.models import JobPosting, TargetBrief

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
SAMPLE_PATH = EXAMPLES_DIR / "sample_postings.json"
TARGET_PATH = EXAMPLES_DIR / "target_brief.json"

# Test that a valid target brief loads
def test_valid_target_brief_loads():
    target = load_target_brief(TARGET_PATH)

    assert target.name == "Entry-Level AI / Software Roles"
    assert target.role_family == "Software Engineering / AI"
    assert "software engineer" in target.title_keywords
    assert "Atlanta, GA" in target.locations
    assert "Python" in target.required_skills


# Test that a target brief with missing required name raises a value error
def test_missing_required_name_raises_value_error(tmp_path: Path):
    bad_file = tmp_path / "bad_target.json"
    bad_file.write_text(json.dumps({"title_keywords": ["engineer"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required field: name"):
        load_target_brief(bad_file)


# Test that a target brief with list fields must be lists of strings
def test_list_fields_must_be_lists_of_strings(tmp_path: Path):
    bad_file = tmp_path / "bad_target.json"
    bad_file.write_text(
        json.dumps({"name": "Test", "title_keywords": ["ok", 123]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="title_keywords\\[1\\] must be a string"):
        load_target_brief(bad_file)


# Test that a title keyword match is case insensitive
def test_title_keyword_match_is_case_insensitive():
    target = TargetBrief(name="Test", title_keywords=["software engineer"])
    posting = JobPosting(
        title="ENTRY LEVEL SOFTWARE ENGINEER",
        company="Co",
        description="Build tools.",
    )

    match = evaluate_posting_against_target(posting, target)

    assert match.included is True
    assert any("title matched keyword" in reason for reason in match.matched_reasons)


# Test that a location match is case insensitive
def test_location_match_is_case_insensitive():
    target = TargetBrief(name="Test", locations=["remote"])
    posting = JobPosting(
        title="Engineer",
        company="Co",
        description="Build tools.",
        location="REMOTE",
    )

    match = evaluate_posting_against_target(posting, target)

    assert match.included is True
    assert any("location matched target" in reason for reason in match.matched_reasons)


# Test that a title mismatch skips a posting
def test_title_mismatch_skips_posting():
    target = TargetBrief(name="Test", title_keywords=["data scientist"])
    posting = JobPosting(title="Backend Developer Intern", company="Co", description="APIs.")

    match = evaluate_posting_against_target(posting, target)

    assert match.included is False
    assert match.skipped_reasons == ["title did not match target keywords"]


# Test that a location mismatch skips a posting
def test_location_mismatch_skips_posting():
    target = TargetBrief(name="Test", locations=["Atlanta, GA"])
    posting = JobPosting(
        title="Software Engineer",
        company="Co",
        description="Build tools.",
        location="New York, NY",
    )

    match = evaluate_posting_against_target(posting, target)

    assert match.included is False
    assert match.skipped_reasons == ["location did not match target locations"]


# Test that a missing required skills adds a warning but does not skip
def test_missing_required_skills_add_warning_but_does_not_skip():
    target = TargetBrief(
        name="Test",
        title_keywords=["engineer"],
        locations=["Remote"],
        required_skills=["Python", "SQL", "Git"],
    )
    posting = JobPosting(
        title="Software Engineer",
        company="Co",
        description="Python only.",
        location="Remote",
        skills=["Python"],
    )

    match = evaluate_posting_against_target(posting, target)

    assert match.included is True
    assert any("matched required skill: Python" in reason for reason in match.matched_reasons)
    assert any("missing required skill(s): SQL, Git" in warning for warning in match.warnings)


# Test that a brief with a target includes target sections
def test_brief_with_target_includes_target_sections():
    postings = load_postings(SAMPLE_PATH)
    target = load_target_brief(TARGET_PATH)
    brief = generate_brief(postings, target=target)

    assert "## Target Brief" in brief
    assert "Entry-Level AI / Software Roles" in brief
    assert "## Target Match Summary" in brief
    assert "Input postings: 3" in brief


# Test that a brief with repeated skills uses included postings only
def test_brief_repeated_skills_use_included_postings_only():
    postings = [
        JobPosting(
            title="Software Engineer",
            company="Included Co",
            description="Python and SQL.",
            location="Remote",
            skills=["Python", "SQL"],
        ),
        JobPosting(
            title="Marketing Manager",
            company="Skipped Co",
            description="Python and SQL.",
            location="New York, NY",
            skills=["Python", "SQL"],
        ),
    ]
    target = TargetBrief(
        name="Engineer Roles",
        title_keywords=["software engineer"],
        locations=["Remote"],
    )
    brief = generate_brief(postings, target=target)

    assert "Included postings: 1" in brief
    assert "Skipped postings: 1" in brief
    assert "Python: 1 posting" in brief
    assert "SQL: 1 posting" in brief
    assert "Python: 2 postings" not in brief


# Test that a brief includes skipped posting reasons
def test_brief_includes_skipped_posting_reasons():
    postings = [
        JobPosting(
            title="Marketing Manager",
            company="Skipped Co",
            description="General role.",
            location="New York, NY",
        )
    ]
    target = TargetBrief(
        name="Engineer Roles",
        title_keywords=["software engineer"],
        locations=["Remote"],
    )
    brief = generate_brief(postings, target=target)

    assert "## Skipped Postings" in brief
    assert "Marketing Manager — Skipped Co" in brief
    assert "title did not match target keywords" in brief


# Test that a brief with zero included postings still generates markdown
def test_brief_with_zero_included_postings_still_generates_markdown():
    postings = [
        JobPosting(
            title="Marketing Manager",
            company="Skipped Co",
            description="General role.",
            location="New York, NY",
        )
    ]
    target = TargetBrief(
        name="Engineer Roles",
        title_keywords=["software engineer"],
        locations=["Remote"],
    )
    brief = generate_brief(postings, target=target)

    assert "# Jobs Recon Brief" in brief
    assert "No postings matched the target brief." in brief
    assert "Included postings: 0" in brief


# Test that a CLI without a target still works
def test_cli_without_target_still_works(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(["--input", str(SAMPLE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "Target Brief" not in content
    assert "Postings analyzed: 3" in content


# Test that a CLI with a target writes a markdown file
def test_cli_with_target_writes_markdown_file(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(
        [
            "--input",
            str(SAMPLE_PATH),
            "--target",
            str(TARGET_PATH),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "Target Brief" in content
    assert "Target Match Summary" in content


# Test that a CLI with an invalid target path returns a non-zero exit code
def test_cli_invalid_target_path_returns_nonzero(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(
        [
            "--input",
            str(SAMPLE_PATH),
            "--target",
            str(tmp_path / "missing_target.json"),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 1
    assert not output_path.exists()
