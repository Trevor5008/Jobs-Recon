"""Tests for grounded lead source-family and actionability triage."""

import pytest

from jobs_recon.discovery.leads import enrich_lead, infer_source_family
from jobs_recon.discovery.report import generate_search_feasibility_report
from jobs_recon.discovery.types import (
    ACTIONABILITY_CANONICAL_CANDIDATE,
    ACTIONABILITY_MANUAL_REVIEW,
    ACTIONABILITY_MANUAL_REVIEW_ONLY,
    ACTIONABILITY_NOT_ACTIONABLE,
    ACTIONABILITY_SEARCH_SURFACE_ONLY,
    AVAILABILITY_AGGREGATOR_ONLY,
    AVAILABILITY_UNCERTAIN,
    SOURCE_FAMILY_ATS,
    SOURCE_FAMILY_DICE,
    SOURCE_FAMILY_GOOGLE_JOBS,
    SOURCE_FAMILY_GOOGLE_SEARCH,
    SOURCE_FAMILY_HANDSHAKE,
    SOURCE_FAMILY_LINKEDIN,
    SOURCE_FAMILY_VERTEX_REDIRECT,
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_ATS,
    SOURCE_TYPE_SEARCH_SURFACE,
    SOURCE_TYPE_UNKNOWN,
    DiscoveryFeasibilityRun,
    DiscoveryLead,
    DiscoveryResponse,
)

VERTEX_REDIRECT = (
    "https://vertexaisearch.cloud.google.com/grounding-api-redirect/example"
)


@pytest.mark.parametrize(
    ("url", "expected_family"),
    [
        ("https://www.linkedin.com/jobs/view/123", SOURCE_FAMILY_LINKEDIN),
        ("https://www.dice.com/job-detail/example", SOURCE_FAMILY_DICE),
        ("https://www.google.com/search?q=entry+level+ai+jobs", SOURCE_FAMILY_GOOGLE_SEARCH),
        ("https://jobs.google.com/search?q=entry+level+ai", SOURCE_FAMILY_GOOGLE_JOBS),
        ("https://app.joinhandshake.com/stu/jobs/123", SOURCE_FAMILY_HANDSHAKE),
        ("https://boards.greenhouse.io/acme/jobs/123", SOURCE_FAMILY_ATS),
        ("https://jobs.lever.co/acme/123", SOURCE_FAMILY_ATS),
        (VERTEX_REDIRECT, SOURCE_FAMILY_VERTEX_REDIRECT),
    ],
)
def test_infer_source_family(url: str, expected_family: str):
    assert infer_source_family(url) == expected_family


@pytest.mark.parametrize(
    ("url", "expected_type", "expected_family", "expected_actionability", "expected_availability"),
    [
        (
            "https://www.linkedin.com/jobs/view/123",
            SOURCE_TYPE_AGGREGATOR,
            SOURCE_FAMILY_LINKEDIN,
            ACTIONABILITY_MANUAL_REVIEW_ONLY,
            AVAILABILITY_AGGREGATOR_ONLY,
        ),
        (
            "https://www.dice.com/job-detail/example",
            SOURCE_TYPE_AGGREGATOR,
            SOURCE_FAMILY_DICE,
            ACTIONABILITY_MANUAL_REVIEW,
            AVAILABILITY_AGGREGATOR_ONLY,
        ),
        (
            "https://www.google.com/search?q=entry+level+ai+jobs",
            SOURCE_TYPE_SEARCH_SURFACE,
            SOURCE_FAMILY_GOOGLE_SEARCH,
            ACTIONABILITY_SEARCH_SURFACE_ONLY,
            AVAILABILITY_UNCERTAIN,
        ),
        (
            "https://jobs.google.com/search?q=entry+level+ai",
            SOURCE_TYPE_SEARCH_SURFACE,
            SOURCE_FAMILY_GOOGLE_JOBS,
            ACTIONABILITY_SEARCH_SURFACE_ONLY,
            AVAILABILITY_UNCERTAIN,
        ),
        (
            "https://app.joinhandshake.com/stu/jobs/123",
            SOURCE_TYPE_AGGREGATOR,
            SOURCE_FAMILY_HANDSHAKE,
            ACTIONABILITY_MANUAL_REVIEW_ONLY,
            AVAILABILITY_AGGREGATOR_ONLY,
        ),
        (
            "https://boards.greenhouse.io/acme/jobs/123",
            SOURCE_TYPE_ATS,
            SOURCE_FAMILY_ATS,
            ACTIONABILITY_CANONICAL_CANDIDATE,
            AVAILABILITY_UNCERTAIN,
        ),
        (
            "https://jobs.lever.co/acme/123",
            SOURCE_TYPE_ATS,
            SOURCE_FAMILY_ATS,
            ACTIONABILITY_CANONICAL_CANDIDATE,
            AVAILABILITY_UNCERTAIN,
        ),
        (
            VERTEX_REDIRECT,
            SOURCE_TYPE_UNKNOWN,
            SOURCE_FAMILY_VERTEX_REDIRECT,
            ACTIONABILITY_NOT_ACTIONABLE,
            AVAILABILITY_UNCERTAIN,
        ),
    ],
)

# Test that enrich lead triage fields are correct
def test_enrich_lead_triage_fields(
    url: str,
    expected_type: str,
    expected_family: str,
    expected_actionability: str,
    expected_availability: str,
):
    lead = enrich_lead(DiscoveryLead(discovery_url=url))
    assert lead.source_type == expected_type
    assert lead.source_family == expected_family
    assert lead.actionability == expected_actionability
    assert lead.availability_status == expected_availability
    assert lead.recommendation
    assert len(lead.recommendation) > 10

# Test that enrich lead preserves explicit triage from payload
def test_enrich_lead_preserves_explicit_triage_from_payload():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url="https://boards.greenhouse.io/acme/jobs/123",
            source_family="custom_family",
            actionability="custom_action",
            recommendation="Keep this recommendation.",
        ),
        preserve_source_family=True,
        preserve_actionability=True,
        preserve_recommendation=True,
    )
    assert lead.source_family == "custom_family"
    assert lead.actionability == "custom_action"
    assert lead.recommendation == "Keep this recommendation."


# Test that feasibility report includes triage fields
def test_feasibility_report_includes_triage_fields():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url="https://www.dice.com/job-detail/example",
            title="Example Dice posting",
        )
    )
    run = DiscoveryFeasibilityRun(
        target_name="Test",
        target_summary="Test target",
        target_path=None,
        responses=[
            DiscoveryResponse(
                provider="manual_fixture",
                model=None,
                prompt="test",
                response_text="example",
                citations=[lead],
            )
        ],
        mode="fixture",
    )
    report = generate_search_feasibility_report(run)

    assert "Source family:" in report
    assert "Actionability:" in report
    assert "Recommendation:" in report
    assert "dice" in report
    assert "manual_review" in report
