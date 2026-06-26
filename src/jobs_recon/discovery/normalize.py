"""Normalize fixture or API JSON into DiscoveryResponse objects."""

from jobs_recon.discovery.leads import enrich_lead, enrich_leads
from jobs_recon.discovery.types import (
    PROVIDER_GOOGLE_GROUNDING,
    DiscoveryLead,
    DiscoveryResponse,
)


def _lead_from_mapping(data: dict) -> DiscoveryLead | None:
    discovery_url = data.get("discovery_url") or data.get("url") or data.get("uri") or data.get("link")
    if not isinstance(discovery_url, str) or not discovery_url.strip():
        return None

    title = data.get("title")
    snippet = data.get("snippet")
    canonical = data.get("canonical_posting_url")
    availability = data.get("availability_status")
    source_family = data.get("source_family")
    actionability = data.get("actionability")
    recommendation = data.get("recommendation")

    lead = DiscoveryLead(
        discovery_url=discovery_url,
        title=title if isinstance(title, str) else None,
        snippet=snippet if isinstance(snippet, str) else None,
        canonical_posting_url=canonical if isinstance(canonical, str) else None,
    )
    if isinstance(availability, str) and availability.strip():
        lead.availability_status = availability.strip()

    preserve_source_family = False
    preserve_actionability = False
    preserve_recommendation = False

    if isinstance(source_family, str) and source_family.strip():
        lead.source_family = source_family.strip()
        preserve_source_family = True
    if isinstance(actionability, str) and actionability.strip():
        lead.actionability = actionability.strip()
        preserve_actionability = True
    if isinstance(recommendation, str) and recommendation.strip():
        lead.recommendation = recommendation.strip()
        preserve_recommendation = True

    return enrich_lead(
        lead,
        preserve_source_family=preserve_source_family,
        preserve_actionability=preserve_actionability,
        preserve_recommendation=preserve_recommendation,
    )


def _extract_grounding_metadata(payload: dict) -> dict | None:
    metadata = payload.get("grounding_metadata") or payload.get("groundingMetadata")
    return metadata if isinstance(metadata, dict) else None


def _leads_from_grounding_metadata(metadata: dict) -> list[DiscoveryLead]:
    chunks = metadata.get("grounding_chunks") or metadata.get("groundingChunks") or []
    if not isinstance(chunks, list):
        return []

    leads: list[DiscoveryLead] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web")
        if not isinstance(web, dict):
            continue
        lead = _lead_from_mapping(web)
        if lead is not None:
            leads.append(lead)
    return leads


def _response_text_from_payload(payload: dict) -> str:
    if isinstance(payload.get("response_text"), str):
        return payload["response_text"]

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""

    first = candidates[0]
    if not isinstance(first, dict):
        return ""

    content = first.get("content")
    if not isinstance(content, dict):
        return ""

    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""

    text_parts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text_parts.append(part["text"])
    return "\n".join(text_parts)


def normalize_grounded_response(
    payload: dict,
    prompt: str,
    *,
    provider: str = PROVIDER_GOOGLE_GROUNDING,
    model: str | None = None,
    timestamp: str | None = None,
) -> DiscoveryResponse:
    """Normalize fixture or Gemini API JSON into a DiscoveryResponse."""
    if not isinstance(payload, dict):
        raise ValueError("Grounded response payload must be a JSON object")

    response_text = _response_text_from_payload(payload)
    grounding_metadata = _extract_grounding_metadata(payload)

    leads: list[DiscoveryLead] = []
    raw_citations = payload.get("citations")
    if isinstance(raw_citations, list):
        for item in raw_citations:
            if isinstance(item, dict):
                lead = _lead_from_mapping(item)
                if lead is not None:
                    leads.append(lead)

    if not leads and grounding_metadata is not None:
        leads = _leads_from_grounding_metadata(grounding_metadata)

    enrich_leads(leads)

    resolved_model = payload.get("model")
    if not isinstance(resolved_model, str):
        resolved_model = model

    resolved_timestamp = payload.get("timestamp")
    if not isinstance(resolved_timestamp, str):
        resolved_timestamp = timestamp

    return DiscoveryResponse(
        provider=provider,
        model=resolved_model,
        prompt=prompt,
        response_text=response_text,
        citations=leads,
        grounding_metadata=grounding_metadata,
        timestamp=resolved_timestamp,
    )
