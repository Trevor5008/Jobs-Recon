import json
from pathlib import Path

import pytest

from jobs_recon.brief import generate_brief
from jobs_recon.parser import extract_skills, load_postings

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "sample_postings.json"


# Test that the parser accepts valid sample postings
def test_parser_accepts_valid_sample_postings():
    postings = load_postings(SAMPLE_PATH)
    assert len(postings) == 3
    assert postings[0].title == "Entry Level Software Engineer"
    assert postings[0].company == "Example Co"
    assert postings[0].source == "manual"
    assert postings[0].source_url == "https://example.com/job/1"


# Test that the parser rejects missing required fields
def test_parser_rejects_missing_required_fields(tmp_path: Path):
    bad_data = [{"title": "Engineer", "company": "Acme"}]
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required field"):
        load_postings(bad_file)


# Test that skill extraction is deterministic and case-insensitive
def test_skill_extraction_is_deterministic_and_case_insensitive():
    description = "Needs python, SQL, and GIT experience."
    first = extract_skills(description)
    second = extract_skills(description)
    assert first == second
    assert first == ["Python", "SQL", "Git"]


# Test that the brief includes counts, skills, and posting details
def test_brief_includes_counts_skills_and_posting_details():
    postings = load_postings(SAMPLE_PATH)
    brief = generate_brief(postings)

    assert "Postings analyzed: 3" in brief
    assert "Python: 2 postings" in brief
    assert "Entry Level Software Engineer — Example Co" in brief
    assert "https://example.com/job/1" in brief


# Test that the CLI generates markdown output
def test_cli_generates_markdown_output(tmp_path: Path):
    from jobs_recon.cli import main

    output_path = tmp_path / "recon_brief.md"
    exit_code = main(["--input", str(SAMPLE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "Jobs Recon Brief" in content
    assert "Postings analyzed: 3" in content
    assert "Python: 2 postings" in content
    assert "https://example.com/job/1" in content
