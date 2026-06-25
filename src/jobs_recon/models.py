from dataclasses import dataclass, field

# JobPosting class schema
@dataclass
class JobPosting:
    title: str
    company: str
    description: str
    source: str | None = None
    source_url: str | None = None
    location: str | None = None
    skills: list[str] = field(default_factory=list)

# TargetBrief class schema
@dataclass
class TargetBrief:
    name: str
    role_family: str | None = None
    title_keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_preference: str | None = None
    seniority: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    notes: str | None = None


# TargetMatch class schema
@dataclass
class TargetMatch:
    included: bool
    matched_reasons: list[str] = field(default_factory=list)
    skipped_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
