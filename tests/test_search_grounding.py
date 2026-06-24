from pathlib import Path

import pytest

from jobs_recon.cli import main
from jobs_recon.google_grounding import (
    GoogleGroundingConfigError,
    get_google_grounding_config,
    google_grounding_configured,
    load_grounding_fixture,
)
from jobs_recon.models import TargetBrief
from jobs_recon.search_discovery import (
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_ATS,
    SOURCE_TYPE_EMPLOYER,
    SOURCE_TYPE_IRRELEVANT,
    SOURCE_TYPE_SEARCH_SURFACE,
    classify_result_url,
    generate_discovery_prompts,
    normalize_grounded_response,
    promising_citations,
)
from jobs_recon.search_feasibility import (
    assess_viability,
    build_feasibility_run,
    generate_search_feasibility_report,
)
from jobs_recon.target import load_target_brief

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TARGET_AI_PATH = EXAMPLES_DIR / "target-ai-engineer.json"
GROUNDING_FIXTURE_PATH = FIXTURES_DIR / "google_grounding_response.json"
SAMPLE_PATH = EXAMPLES_DIR / "sample_postings.json"
TARGET_PATH = EXAMPLES_DIR / "target_brief.json"


def test_generate_discovery_prompts_from_target_brief():
    target = load_target_brief(TARGET_AI_PATH)
    prompts = generate_discovery_prompts(target)

    assert len(prompts) >= 5
    general = prompts[0]
    assert "AI Engineer" in general.prompt
    assert "Machine Learning Engineer" in general.prompt
    assert "intern" in general.prompt or "junior" in general.prompt
    assert "Miami" in general.prompt
    assert "Greenhouse" in prompts[1].prompt
    assert "Lever" in prompts[2].prompt
    assert "canonical employer career pages" in general.prompt


def test_generate_discovery_prompts_handles_minimal_target():
    target = TargetBrief(name="Minimal", title_keywords=["Engineer"], locations=["Remote"])
    prompts = generate_discovery_prompts(target)

    assert len(prompts) >= 1
    assert "Engineer" in prompts[0].prompt
    assert "Remote" in prompts[0].prompt


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/123", SOURCE_TYPE_ATS),
        ("https://jobs.lever.co/acme/abc-def", SOURCE_TYPE_ATS),
        ("https://jobs.ashbyhq.com/acme/abc", SOURCE_TYPE_ATS),
        ("https://apply.workable.com/acme/j/ABC", SOURCE_TYPE_ATS),
        ("https://www.indeed.com/viewjob?jk=abc", SOURCE_TYPE_AGGREGATOR),
        ("https://www.linkedin.com/jobs/view/123", SOURCE_TYPE_AGGREGATOR),
        ("https://www.google.com/search?q=jobs", SOURCE_TYPE_SEARCH_SURFACE),
        ("https://careers.example.com/jobs/ai-engineer", SOURCE_TYPE_EMPLOYER),
        ("", SOURCE_TYPE_IRRELEVANT),
    ],
)
def test_classify_result_url(url: str, expected: str):
    assert classify_result_url(url) == expected


def test_parse_grounding_fixture_results():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    prompt = "Find current public job postings for intern AI/software roles around Miami."
    response = normalize_grounded_response(payload, prompt)

    assert response.response_text
    assert len(response.citations) == 3
    assert response.citations[0].source_type == SOURCE_TYPE_ATS
    assert response.citations[1].source_type == SOURCE_TYPE_AGGREGATOR
    assert response.citations[2].source_type == SOURCE_TYPE_ATS
    assert response.model == "gemini-2.5-flash"
    assert response.grounding_metadata is not None


def test_promising_citations_prefers_ats_over_aggregators():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, "test prompt")
    promising = promising_citations(response.citations)

    assert len(promising) == 2
    assert all(citation.source_type == SOURCE_TYPE_ATS for citation in promising)


def test_search_feasibility_report_includes_required_sections():
    target = load_target_brief(TARGET_AI_PATH)
    prompts = generate_discovery_prompts(target)
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, prompts[0].prompt)
    run = build_feasibility_run(
        target_name=target.name,
        target_summary="AI / software intern roles",
        target_path=str(TARGET_AI_PATH),
        prompts=prompts,
        responses=[response],
        mode="fixture",
    )
    report = generate_search_feasibility_report(run)

    assert "# Search Feasibility Report: Google Search Grounding" in report
    assert "## Prompts Tested" in report
    assert "## Citation Counts" in report
    assert "## Promising URLs" in report
    assert "## Important Limitations" in report
    assert "does **not** scrape Google Jobs" in report
    assert "discovery evidence only" in report
    assert "boards.greenhouse.io" in report
    assert "Google Custom Search JSON API are out of scope" in report


def test_assess_viability_with_fixture_results():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, "test")
    verdict, _ = assess_viability(response.citations)

    assert verdict == "promising"


def test_missing_grounding_credentials_raise_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    assert google_grounding_configured() is False
    with pytest.raises(GoogleGroundingConfigError, match="GEMINI_API_KEY"):
        get_google_grounding_config()


def test_cli_search_grounding_dry_run_prints_prompts(capsys):
    exit_code = main(
        [
            "search-grounding",
            "--target",
            str(TARGET_AI_PATH),
            "--dry-run",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Greenhouse" in captured.out
    assert "Generated" in captured.out


def test_cli_search_grounding_fixture_writes_report(tmp_path: Path):
    output_path = tmp_path / "google_grounding_feasibility.md"
    exit_code = main(
        [
            "search-grounding",
            "--target",
            str(TARGET_AI_PATH),
            "--fixture",
            str(GROUNDING_FIXTURE_PATH),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "Search Feasibility Report" in content
    assert "jobs.lever.co" in content


def test_cli_live_without_credentials_returns_nonzero(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    output_path = tmp_path / "google_grounding_feasibility.md"
    exit_code = main(
        [
            "search-grounding",
            "--target",
            str(TARGET_AI_PATH),
            "--live",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 1
    assert not output_path.exists()


def test_existing_brief_command_still_works(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(["--input", str(SAMPLE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert "Postings analyzed: 3" in output_path.read_text(encoding="utf-8")


def test_existing_source_feasibility_command_still_works(tmp_path: Path):
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
    assert "Source Feasibility Report: Handshake" in output_path.read_text(encoding="utf-8")


def test_existing_target_aware_brief_command_still_works(tmp_path: Path):
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
    assert "Target Brief" in output_path.read_text(encoding="utf-8")
