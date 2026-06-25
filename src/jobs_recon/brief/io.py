import json
from pathlib import Path

# Import the JobPosting class
from jobs_recon.models import JobPosting

# Import the skill vocabulary
from jobs_recon.brief.constants import SKILL_VOCABULARY, REQUIRED_FIELDS

# Helper function to extract skills from a posting description
def extract_skills(description: str) -> list[str]:
    """Return matched skills in vocabulary order (deterministic)."""
    desc_lower = description.lower()
    return [skill for skill in SKILL_VOCABULARY if skill.lower() in desc_lower]


# Helper function to validate a posting schema
def _validate_posting(raw: dict, index: int) -> None:
    if not isinstance(raw, dict):
        raise ValueError(f"Posting at index {index} must be an object, got {type(raw).__name__}")

    missing = [field for field in REQUIRED_FIELDS if not raw.get(field)]
    if missing:
        raise ValueError(
            f"Posting at index {index} is missing required field(s): {', '.join(missing)}"
        )

# Helper function to parse a posting into a JobPosting
def _parse_posting(raw: dict) -> JobPosting:
    skills = extract_skills(raw["description"])
    return JobPosting(
        title=str(raw["title"]).strip(),
        company=str(raw["company"]).strip(),
        description=str(raw["description"]).strip(),
        source=raw.get("source"),
        source_url=raw.get("source_url"),
        location=raw.get("location"),
        skills=skills,
    )

# Load postings from a local JSON file
def load_postings(path: Path) -> list[JobPosting]:
    """Load and validate postings from a local JSON file."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of postings in {path}")

    postings: list[JobPosting] = []
    for index, raw in enumerate(data):
        _validate_posting(raw, index)
        postings.append(_parse_posting(raw))

    return postings
