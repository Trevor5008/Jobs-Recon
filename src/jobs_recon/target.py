import json
from pathlib import Path

from jobs_recon.models import JobPosting, TargetBrief, TargetMatch

STRING_LIST_FIELDS = (
    "title_keywords",
    "locations",
    "seniority",
    "required_skills",
)


def _validate_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
    return value


def load_target_brief(path: Path) -> TargetBrief:
    """Load and validate a target brief from a local JSON file."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        raise ValueError("Target brief is missing required field: name")

    optional_string_fields = {
        "role_family": data.get("role_family"),
        "remote_preference": data.get("remote_preference"),
        "notes": data.get("notes"),
    }
    for field_name, value in optional_string_fields.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")

    list_values = {field: _validate_string_list(data.get(field), field) for field in STRING_LIST_FIELDS}

    return TargetBrief(
        name=name.strip(),
        role_family=optional_string_fields["role_family"],
        title_keywords=list_values["title_keywords"],
        locations=list_values["locations"],
        remote_preference=optional_string_fields["remote_preference"],
        seniority=list_values["seniority"],
        required_skills=list_values["required_skills"],
        notes=optional_string_fields["notes"],
    )


def _matches_location(posting_location: str, target_locations: list[str]) -> bool:
    posting_lower = posting_location.casefold()
    return any(location.casefold() == posting_lower for location in target_locations)


def _find_title_keyword_match(title: str, keywords: list[str]) -> str | None:
    title_lower = title.casefold()
    for keyword in keywords:
        if keyword.casefold() in title_lower:
            return keyword
    return None


def _find_seniority_match(posting: JobPosting, seniority_keywords: list[str]) -> str | None:
    text = f"{posting.title} {posting.description}".casefold()
    for keyword in seniority_keywords:
        if keyword.casefold() in text:
            return keyword
    return None


def _posting_has_skill(posting: JobPosting, skill: str) -> bool:
    skill_lower = skill.casefold()
    return any(existing.casefold() == skill_lower for existing in posting.skills)


def evaluate_posting_against_target(posting: JobPosting, target: TargetBrief) -> TargetMatch:
    """Apply deterministic target gates and evidence signals to one posting."""
    matched_reasons: list[str] = []
    warnings: list[str] = []

    if target.title_keywords:
        keyword = _find_title_keyword_match(posting.title, target.title_keywords)
        if keyword is None:
            return TargetMatch(
                included=False,
                skipped_reasons=["title did not match target keywords"],
            )
        matched_reasons.append(f"title matched keyword: {keyword}")

    if target.locations:
        if not posting.location:
            return TargetMatch(
                included=False,
                skipped_reasons=["location missing"],
            )
        if not _matches_location(posting.location, target.locations):
            return TargetMatch(
                included=False,
                skipped_reasons=["location did not match target locations"],
            )
        matched_reasons.append(f"location matched target: {posting.location}")

    if target.seniority:
        seniority_match = _find_seniority_match(posting, target.seniority)
        if seniority_match is None:
            warnings.append("no seniority keyword matched in title or description")
        else:
            matched_reasons.append(f"matched seniority signal: {seniority_match}")

    if target.required_skills:
        matched_required: list[str] = []
        missing_required: list[str] = []
        for skill in target.required_skills:
            if _posting_has_skill(posting, skill):
                matched_required.append(skill)
                matched_reasons.append(f"matched required skill: {skill}")
            else:
                missing_required.append(skill)

        if missing_required:
            warnings.append(f"missing required skill(s): {', '.join(missing_required)}")

    return TargetMatch(
        included=True,
        matched_reasons=matched_reasons,
        warnings=warnings,
    )


def evaluate_postings_against_target(
    postings: list[JobPosting],
    target: TargetBrief,
) -> tuple[list[tuple[JobPosting, TargetMatch]], list[tuple[JobPosting, TargetMatch]]]:
    """Split postings into included and skipped match results."""
    included: list[tuple[JobPosting, TargetMatch]] = []
    skipped: list[tuple[JobPosting, TargetMatch]] = []

    for posting in postings:
        match = evaluate_posting_against_target(posting, target)
        if match.included:
            included.append((posting, match))
        else:
            skipped.append((posting, match))

    return included, skipped
