from jobs_recon.discovery.decision_summary import (
    group_leads_for_decision_summary,
    render_lead_actionability_summary,
)
from jobs_recon.discovery.leads import enrich_lead, is_vertex_redirect_url
from jobs_recon.discovery.report import generate_search_feasibility_report
from jobs_recon.discovery.types import (
    ACTIONABILITY_CANONICAL_CANDIDATE,
    ACTIONABILITY_MANUAL_REVIEW_ONLY,
    ACTIONABILITY_NOT_ACTIONABLE,
    ACTIONABILITY_SEARCH_SURFACE_ONLY,
    AVAILABILITY_ACTIVE,
    AVAILABILITY_INACTIVE,
    DiscoveryFeasibilityRun,
    DiscoveryLead,
    DiscoveryResponse,
)

VERTEX_REDIRECT = (
    "https://vertexaisearch.cloud.google.com/grounding-api-redirect/example"
)


def test_discovery_report_includes_actionability_summary():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url="https://boards.greenhouse.io/acme/jobs/123",
            title="Acme AI Engineer",
        )
    )
    run = DiscoveryFeasibilityRun(
        target_name="Test",
        target_summary="Test",
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
    assert "## Lead Actionability Summary" in report
    assert "### More actionable" in report
    assert "### Investigate manually" in report
    assert "### Low actionability / caution" in report
    assert "discovery evidence only" in report


def test_ats_lead_grouped_as_more_actionable_when_canonical_candidate():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url="https://boards.greenhouse.io/acme/jobs/123",
            canonical_posting_url="https://boards.greenhouse.io/acme/jobs/123",
            availability_status=AVAILABILITY_ACTIVE,
        )
    )
    grouped = group_leads_for_decision_summary([lead])
    assert lead in grouped["more_actionable"]
    assert lead.actionability == ACTIONABILITY_CANONICAL_CANDIDATE


def test_linkedin_lead_grouped_for_manual_investigation():
    lead = enrich_lead(
        DiscoveryLead(discovery_url="https://www.linkedin.com/jobs/view/123")
    )
    grouped = group_leads_for_decision_summary([lead])
    assert lead in grouped["investigate_manually"]
    assert lead.actionability == ACTIONABILITY_MANUAL_REVIEW_ONLY


def test_search_surface_lead_grouped_as_low_actionability():
    lead = enrich_lead(
        DiscoveryLead(discovery_url="https://www.google.com/search?q=ai+jobs")
    )
    grouped = group_leads_for_decision_summary([lead])
    assert lead in grouped["low_actionability"]
    assert lead.actionability == ACTIONABILITY_SEARCH_SURFACE_ONLY


def test_vertex_redirect_summary_stays_cautious():
    lead = enrich_lead(DiscoveryLead(discovery_url=VERTEX_REDIRECT))
    summary = render_lead_actionability_summary([lead])
    text = "\n".join(summary)
    assert lead.actionability == ACTIONABILITY_NOT_ACTIONABLE
    assert "redirect-only" in text or "redirect wrapper" in text
    assert is_vertex_redirect_url(lead.discovery_url)


def test_inactive_lead_not_described_as_recommended_job():
    lead = enrich_lead(
        DiscoveryLead(
            discovery_url="https://boards.greenhouse.io/acme/jobs/999",
            availability_status=AVAILABILITY_INACTIVE,
        )
    )
    summary = render_lead_actionability_summary([lead])
    text = "\n".join(summary)
    assert "not recommended jobs" in text.lower() or "caution" in text.lower()
    assert f"availability={AVAILABILITY_INACTIVE}" in text or AVAILABILITY_INACTIVE in text
