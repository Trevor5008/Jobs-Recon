from pathlib import Path

import pytest

from jobs_recon.brief.target import load_target_brief
from jobs_recon.cli import main
from jobs_recon.discovery.leads import (
    active_canonical_leads,
    classify_result_url,
    enrich_lead,
    is_vertex_redirect_url,
    promising_citations,
)
from jobs_recon.discovery.normalize import normalize_grounded_response
from jobs_recon.discovery.prompts import generate_discovery_prompts
from jobs_recon.discovery.providers.google import (
    GoogleGroundingConfigError,
    check_google_grounding_config,
    format_config_check_report,
    get_google_grounding_config,
    google_grounding_configured,
    load_grounding_fixture,
)
from jobs_recon.discovery.report import (
    assess_viability,
    build_feasibility_run,
    generate_search_feasibility_report,
)
from jobs_recon.discovery.types import (
    AVAILABILITY_ACTIVE,
    AVAILABILITY_AGGREGATOR_ONLY,
    AVAILABILITY_INACTIVE,
    AVAILABILITY_LOGIN_GATED,
    AVAILABILITY_UNCERTAIN,
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_ATS,
    SOURCE_TYPE_IRRELEVANT,
    SOURCE_TYPE_SEARCH_SURFACE,
    SOURCE_TYPE_UNKNOWN,
    DiscoveryLead,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
TARGET_AI_PATH = EXAMPLES_DIR / "target-ai-engineer.json"
GROUNDING_FIXTURE_PATH = FIXTURES_DIR / "google_grounding_response.json"
SAMPLE_PATH = EXAMPLES_DIR / "sample_postings.json"
TARGET_PATH = EXAMPLES_DIR / "target_brief.json"

VERTEX_REDIRECT = (
    "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXAMPLE"
)

# Test that discovery prompts are generated from a target brief
def test_generate_discovery_prompts_from_target_brief():
    target = load_target_brief(TARGET_AI_PATH)
    prompts = generate_discovery_prompts(target)

    assert len(prompts) >= 5
    general = prompts[0]
    assert "AI Engineer" in general.prompt
    assert "Miami" in general.prompt
    assert "canonical employer career pages" in general.prompt


# Test that result URL classification is correct
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/123", SOURCE_TYPE_ATS),
        ("https://jobs.lever.co/acme/abc-def", SOURCE_TYPE_ATS),
        ("https://www.indeed.com/viewjob?jk=abc", SOURCE_TYPE_AGGREGATOR),
        ("https://www.jobleads.com/job/example", SOURCE_TYPE_AGGREGATOR),
        ("https://www.ziprecruiter.com/jobs/example", SOURCE_TYPE_AGGREGATOR),
        ("https://www.remoterocketship.com/job/example", SOURCE_TYPE_AGGREGATOR),
        (VERTEX_REDIRECT, SOURCE_TYPE_UNKNOWN),
        ("https://www.google.com/search?q=jobs", SOURCE_TYPE_SEARCH_SURFACE),
        ("https://careers.example.com/jobs/ai-engineer", SOURCE_TYPE_UNKNOWN),
        ("", SOURCE_TYPE_IRRELEVANT),
    ],
)

# Test that result URL classification is correct
def test_classify_result_url(url: str, expected: str):
    assert classify_result_url(url) == expected


# Test that vertex redirect is preserved as a discovery URL
def test_vertex_redirect_preserved_as_discovery_url():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, "test prompt")
    redirect_leads = [lead for lead in response.citations if is_vertex_redirect_url(lead.discovery_url)]

    assert redirect_leads
    assert all(lead.discovery_url.startswith("https://vertexaisearch.cloud.google.com/") for lead in redirect_leads)


# Test that vertex redirect is not classified as an employer without a canonical URL
def test_vertex_redirect_not_classified_as_employer_without_canonical_url():
    lead = enrich_lead(DiscoveryLead(discovery_url=VERTEX_REDIRECT, title="myworkdayjobs.com"))
    assert lead.source_type == SOURCE_TYPE_UNKNOWN
    assert lead.availability_status == AVAILABILITY_UNCERTAIN


# Test that canonical URL classification wins
def test_canonical_url_classification_wins():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url=VERTEX_REDIRECT,
            canonical_posting_url="https://boards.greenhouse.io/exampleco/jobs/123456",
            availability_status=AVAILABILITY_ACTIVE,
        )
    )
    assert lead.source_type == SOURCE_TYPE_ATS
    assert lead.canonical_posting_url is not None
    assert lead.canonical_posting_url.endswith("/123456")


# Test that parsing grounding fixture results is correct
def test_parse_grounding_fixture_results():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, "test prompt")

    assert response.response_text
    assert len(response.citations) == 6
    assert active_canonical_leads(response.citations)[0].availability_status == AVAILABILITY_ACTIVE
    assert any(lead.availability_status == AVAILABILITY_AGGREGATOR_ONLY for lead in response.citations)
    assert any(lead.availability_status == AVAILABILITY_INACTIVE for lead in response.citations)
    assert any(lead.availability_status == AVAILABILITY_LOGIN_GATED for lead in response.citations)


# Test that availability status defaults to uncertain
def test_availability_status_defaults_to_uncertain():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url=VERTEX_REDIRECT,
            title="wrapper-only",
        )
    )
    assert lead.availability_status == AVAILABILITY_UNCERTAIN


# Test that promising citations prefers active canonical leads
def test_promising_citations_prefers_active_canonical_leads():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, "test prompt")
    promising = promising_citations(response.citations)

    assert len(promising) == 1
    assert promising[0].availability_status == AVAILABILITY_ACTIVE
    assert promising[0].canonical_posting_url


# Test that search feasibility report includes lead fields
def test_search_feasibility_report_includes_lead_fields():
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

    assert "## Candidate Leads" in report
    assert "## Lead Actionability Summary" in report
    assert "Discovery URL:" in report
    assert "Canonical posting URL:" in report
    assert "Availability:" in report
    assert "Source family:" in report
    assert "Actionability:" in report
    assert "Recommendation:" in report
    assert "### Active canonical leads" in report
    assert "### Aggregator-only leads" in report
    assert "### Uncertain / manual review needed" in report
    assert "Vertex redirect wrapper only" in report


# Test that assess viability with active canonical fixture is correct
def test_assess_viability_with_active_canonical_fixture():
    payload = load_grounding_fixture(str(GROUNDING_FIXTURE_PATH))
    response = normalize_grounded_response(payload, "test")
    verdict, _ = assess_viability(response.citations)

    assert verdict == "promising"


# Test that vertex config check succeeds when env is set
def test_vertex_config_check_succeeds_when_env_is_set(monkeypatch, tmp_path: Path):
    creds = tmp_path / "gcp-credentials.json"
    creds.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "jobs-recon")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds))

    result = check_google_grounding_config()
    report = format_config_check_report(result)

    assert result.ready is True
    assert result.mode == "vertex"
    assert "Status: ready" in report
    assert "jobs-recon" in report


# Test that vertex config check fails when project is missing
def test_vertex_config_check_fails_when_project_missing(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    result = check_google_grounding_config()

    assert result.ready is False
    assert any("GOOGLE_CLOUD_PROJECT" in issue for issue in result.issues)


# Test that missing grounding credentials raise a clear error
def test_missing_grounding_credentials_raise_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    assert google_grounding_configured() is False
    with pytest.raises(GoogleGroundingConfigError):
        get_google_grounding_config()


# Test that CLI search grounding check config is correct
def test_cli_search_grounding_check_config(capsys, monkeypatch, tmp_path: Path):
    creds = tmp_path / "gcp-credentials.json"
    creds.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "jobs-recon")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds))

    exit_code = main(["search-grounding", "--check-config"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Google grounding config:" in captured.out
    assert "mode: vertex" in captured.out


# Test that CLI search grounding dry run prints prompts
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


# Test that CLI search grounding fixture writes report
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
    assert "Candidate Leads" in content
    assert "boards.greenhouse.io" in content


# Test that CLI live without credentials returns nonzero
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


# Test that existing brief command still works
def test_existing_brief_command_still_works(tmp_path: Path):
    output_path = tmp_path / "recon_brief.md"
    exit_code = main(["--input", str(SAMPLE_PATH), "--output", str(output_path)])

    assert exit_code == 0
    assert "Postings analyzed: 3" in output_path.read_text(encoding="utf-8")


# Test that existing target aware brief command still works
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
