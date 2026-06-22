from pathlib import Path

import pytest

from jobs_recon.cli import main
from jobs_recon.google_search import (
    GoogleSearchConfigError,
    get_google_search_config,
    google_search_configured,
    load_google_search_fixture,
)
from jobs_recon.models import TargetBrief
from jobs_recon.search_discovery import (
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_ATS,
    SOURCE_TYPE_EMPLOYER,
    SOURCE_TYPE_GOOGLE_SURFACE,
    SOURCE_TYPE_IRRELEVANT,
    classify_result_url,
    generate_dork_queries,
    parse_google_search_items,
    promising_results,
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
GOOGLE_FIXTURE_PATH = FIXTURES_DIR / "google_search_response.json"
SAMPLE_PATH = EXAMPLES_DIR / "sample_postings.json"
TARGET_PATH = EXAMPLES_DIR / "target_brief.json"

# TODO: remove this test once Google search is implemented
def test_generate_dork_queries_from_target_brief():
    target = load_target_brief(TARGET_AI_PATH)
    queries = generate_dork_queries(target)

    assert len(queries) >= 5
    general = queries[0]
    assert '"AI Engineer"' in general.query
    assert '"Machine Learning Engineer"' in general.query
    assert "intern" in general.query or "junior" in general.query
    assert "Miami" in general.query
    assert "site:greenhouse.io" in queries[1].query
    assert "site:jobs.lever.co" in queries[2].query


# TODO: remove this test once Google search is implemented
def test_generate_dork_queries_handles_minimal_target():
    target = TargetBrief(name="Minimal", title_keywords=["Engineer"], locations=["Remote"])
    queries = generate_dork_queries(target)

    assert len(queries) >= 1
    assert "Engineer" in queries[0].query
    assert "Remote" in queries[0].query


# TODO: remove this test once Google search is implemented
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/123", SOURCE_TYPE_ATS),
        ("https://jobs.lever.co/acme/abc-def", SOURCE_TYPE_ATS),
        ("https://jobs.ashbyhq.com/acme/abc", SOURCE_TYPE_ATS),
        ("https://apply.workable.com/acme/j/ABC", SOURCE_TYPE_ATS),
        ("https://www.indeed.com/viewjob?jk=abc", SOURCE_TYPE_AGGREGATOR),
        ("https://www.linkedin.com/jobs/view/123", SOURCE_TYPE_AGGREGATOR),
        ("https://www.google.com/search?q=jobs", SOURCE_TYPE_GOOGLE_SURFACE),
        ("https://careers.example.com/jobs/ai-engineer", SOURCE_TYPE_EMPLOYER),
        ("", SOURCE_TYPE_IRRELEVANT),
    ],
)


# TODO: remove this test once Google search is implemented
def test_classify_result_url(url: str, expected: str):
    assert classify_result_url(url) == expected


# TODO: remove this test once Google search is implemented
def test_parse_google_search_fixture_results():
    payload = load_google_search_fixture(str(GOOGLE_FIXTURE_PATH))
    query = 'site:greenhouse.io ("AI Engineer") ("Miami" OR "Remote")'
    results = parse_google_search_items(payload, query)

    assert len(results) == 3
    assert results[0].source_type == SOURCE_TYPE_ATS
    assert results[0].title == "AI Engineer Intern - ExampleCo"
    assert results[1].source_type == SOURCE_TYPE_AGGREGATOR
    assert results[2].source_type == SOURCE_TYPE_ATS
    assert all(result.query == query for result in results)
    assert all(result.provider == "google_custom_search_json" for result in results)


# TODO: remove this test once Google search is implemented
def test_promising_results_prefers_ats_over_aggregators():
    payload = load_google_search_fixture(str(GOOGLE_FIXTURE_PATH))
    results = parse_google_search_items(payload, "test query")
    promising = promising_results(results)

    assert len(promising) == 2
    assert all(result.source_type == SOURCE_TYPE_ATS for result in promising)


# TODO: remove this test once Google search is implemented
def test_search_feasibility_report_includes_required_sections():
    target = load_target_brief(TARGET_AI_PATH)
    queries = generate_dork_queries(target)
    payload = load_google_search_fixture(str(GOOGLE_FIXTURE_PATH))
    results = parse_google_search_items(payload, queries[0].query)
    run = build_feasibility_run(
        target_name=target.name,
        queries=queries,
        results=results,
        mode="fixture",
    )
    report = generate_search_feasibility_report(run)

    assert "# Search Feasibility Report: Google Dorking / JSON Search" in report
    assert "## Queries Tested" in report
    assert "## Result Counts" in report
    assert "## Promising URLs" in report
    assert "## Important Limitations" in report
    assert "does **not** scrape Google Jobs" in report
    assert "snippets are discovery evidence only" in report
    assert "boards.greenhouse.io" in report

# TODO: remove this test once Google search is implemented
def test_assess_viability_with_fixture_results():
    payload = load_google_search_fixture(str(GOOGLE_FIXTURE_PATH))
    results = parse_google_search_items(payload, "test")
    verdict, _ = assess_viability(results)

    assert verdict == "promising"


# TODO: remove this test once Google search is implemented
def test_missing_api_credentials_raise_clear_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)

    assert google_search_configured() is False
    with pytest.raises(GoogleSearchConfigError, match="GOOGLE_API_KEY"):
        get_google_search_config()


# TODO: remove this test once Google search is implemented
def test_cli_google_dorks_dry_run_prints_queries(capsys):
    exit_code = main(
        [
            "google-dorks",
            "--target",
            str(TARGET_AI_PATH),
            "--dry-run",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "site:greenhouse.io" in captured.out
    assert "Generated" in captured.out


# TODO: remove this test once Google search is implemented
def test_cli_google_dorks_fixture_writes_report(tmp_path: Path):
    output_path = tmp_path / "google_dork_feasibility.md"
    exit_code = main(
        [
            "google-dorks",
            "--target",
            str(TARGET_AI_PATH),
            "--fixture",
            str(GOOGLE_FIXTURE_PATH),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "Search Feasibility Report" in content
    assert "jobs.lever.co" in content


# TODO: remove this test once Google search is implemented
def test_cli_live_without_credentials_returns_nonzero(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)

    output_path = tmp_path / "google_dork_feasibility.md"
    exit_code = main(
        [
            "google-dorks",
            "--target",
            str(TARGET_AI_PATH),
            "--live",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 1
    assert not output_path.exists()


# TODO: remove this test once Google search is implemented
def test_existing_brief_command_still_works(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(["--input", str(SAMPLE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert "Postings analyzed: 3" in output_path.read_text(encoding="utf-8")


# TODO: remove this test once Google search is implemented
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


# TODO: remove this test once Google search is implemented
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
