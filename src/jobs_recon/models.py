from dataclasses import dataclass, field


@dataclass
class JobPosting:
    title: str
    company: str
    description: str
    source: str | None = None
    source_url: str | None = None
    location: str | None = None
    skills: list[str] = field(default_factory=list)
