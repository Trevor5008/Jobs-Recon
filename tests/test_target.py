import json
from pathlib import Path

import pytest

from jobs_recon.brief import generate_brief
from jobs_recon.cli import main
from jobs_recon.models import JobPosting, TargetBrief
from utils.parser import load_postings
from jobs_recon.target import evaluate_posting_against_target, load_target_brief

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
SAMPLE_PATH = EXAMPLES_DIR / "sample_postings.json"
TARGET_PATH = EXAMPLES_DIR / "target_brief.json"


def test_valid_target_brief_loads():
    target = load_target_brief(TARGET_PATH)

    assert target.name == "Entry-Level AI / Software Roles"
    assert target.role_family == "Software Engineering / AI"
    assert "software engineer" in target.title_keywords
    assert "Atlanta, GA" in target.locations
    assert "Python" in target.required_skills


def test_missing_required_name_raises_value_error(tmp_path: Path):
    bad_file = tmp_path / "bad_target.json"
    bad_file.write_text(json.dumps({"title_keywords": ["engineer"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required field: name"):
        load_target_brief(bad_file)


def test_list_fields_must_be_lists_of_strings(tmp_path: Path):
    bad_file = tmp_path / "bad_target.json"
    bad_file.write_text(
        json.dumps({"name": "Test", "title_keywords": ["ok", 123]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="title_keywords\\[1\\] must be a string"):
        load_target_brief(bad_file)


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


def test_title_mismatch_skips_posting():
    target = TargetBrief(name="Test", title_keywords=["data scientist"])
    posting = JobPosting(title="Backend Developer Intern", company="Co", description="APIs.")

    match = evaluate_posting_against_target(posting, target)

    assert match.included is False
    assert match.skipped_reasons == ["title did not match target keywords"]


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


def test_brief_with_target_includes_target_sections():
    postings = load_postings(SAMPLE_PATH)
    target = load_target_brief(TARGET_PATH)
    brief = generate_brief(postings, target=target)

    assert "## Target Brief" in brief
    assert "Entry-Level AI / Software Roles" in brief
    assert "## Target Match Summary" in brief
    assert "Input postings: 3" in brief


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


def test_cli_without_target_still_works(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(["--input", str(SAMPLE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "Target Brief" not in content
    assert "Postings analyzed: 3" in content


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
