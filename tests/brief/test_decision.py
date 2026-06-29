from jobs_recon.brief.decision import (
    BUCKET_MISMATCH,
    BUCKET_REACHABLE,
    BUCKET_STRETCH,
    build_decision_buckets,
    classify_included_bucket,
    generate_next_actions,
    skill_example_labels,
)
from jobs_recon.brief.report import generate_brief
from jobs_recon.models import JobPosting, TargetBrief, TargetMatch


def _target(**kwargs) -> TargetBrief:
    defaults = {
        "name": "Test",
        "title_keywords": ["engineer"],
        "locations": ["Remote"],
        "required_skills": ["Python", "SQL", "Git"],
    }
    defaults.update(kwargs)
    return TargetBrief(**defaults)


def test_included_with_matched_required_skill_is_reachable():
    posting = JobPosting(
        title="Software Engineer",
        company="Co",
        description="Python SQL Git",
        location="Remote",
        skills=["Python", "SQL", "Git"],
    )
    match = TargetMatch(
        included=True,
        matched_reasons=[
            "title matched keyword: engineer",
            "location matched target: Remote",
            "matched required skill: Python",
            "matched required skill: SQL",
            "matched required skill: Git",
        ],
    )
    assert classify_included_bucket(posting, match, _target()) == BUCKET_REACHABLE


def test_included_with_missing_required_skills_is_stretch():
    posting = JobPosting(
        title="Software Engineer",
        company="Co",
        description="Python only",
        location="Remote",
        skills=["Python"],
    )
    match = TargetMatch(
        included=True,
        matched_reasons=[
            "title matched keyword: engineer",
            "location matched target: Remote",
            "matched required skill: Python",
        ],
        warnings=["missing required skill(s): SQL, Git"],
    )
    assert classify_included_bucket(posting, match, _target()) == BUCKET_STRETCH


def test_skipped_posting_is_mismatch():
    posting = JobPosting(title="Marketing Manager", company="Co", description="General")
    match = TargetMatch(
        included=False,
        skipped_reasons=["title did not match target keywords"],
    )
    buckets = build_decision_buckets([], [(posting, match)], _target())
    assert buckets.mismatch == ((posting, match),)
    assert not buckets.reachable
    assert not buckets.stretch


def test_no_target_brief_does_not_invent_decision_buckets():
    postings = [
        JobPosting(title="Engineer", company="Co", description="Python", skills=["Python"]),
    ]
    brief = generate_brief(postings)
    assert "Decision buckets require a target brief." in brief
    assert "Decision Buckets" not in brief
    assert "Reachable" not in brief


def test_repeated_skills_include_example_postings():
    postings = [
        JobPosting(title="B Role", company="Beta", description="Python", skills=["Python"]),
        JobPosting(title="A Role", company="Alpha", description="Python", skills=["Python"]),
    ]
    brief = generate_brief(postings)
    assert "Python: 2 postings" in brief
    assert "Examples: A Role — Alpha; B Role — Beta" in brief


def test_skill_examples_are_deterministic():
    postings = [
        JobPosting(title="Z", company="Co", description="", skills=["Git"]),
        JobPosting(title="A", company="Co", description="", skills=["Git"]),
    ]
    assert skill_example_labels(postings, "Git") == ["A — Co", "Z — Co"]


def test_next_actions_include_caveat_and_stretch_guidance():
    target = _target()
    posting = JobPosting(
        title="Software Engineer",
        company="Co",
        description="Python",
        location="Remote",
        skills=["Python"],
    )
    stretch_match = TargetMatch(
        included=True,
        matched_reasons=["title matched keyword: engineer", "location matched target: Remote"],
        warnings=["missing required skill(s): SQL, Git"],
    )
    buckets = build_decision_buckets([(posting, stretch_match)], [], target)
    actions = generate_next_actions(
        target=target,
        buckets=buckets,
        skill_counts=[("Python", 1)],
        included_count=1,
        skipped_count=0,
    )
    assert any("stretch postings" in action for action in actions)
    assert any("directional signal" in action for action in actions)
    assert any("Compare repeated skills" in action for action in actions)


def test_next_actions_suggest_loosening_gates_when_zero_included():
    target = _target()
    skipped_match = TargetMatch(
        included=False,
        skipped_reasons=["location did not match target locations"],
    )
    posting = JobPosting(title="Engineer", company="Co", description="Python", location="NYC")
    buckets = build_decision_buckets([], [(posting, skipped_match)], target)
    actions = generate_next_actions(
        target=target,
        buckets=buckets,
        skill_counts=[],
        included_count=0,
        skipped_count=1,
    )
    assert any("loosening one hard gate" in action for action in actions)


def test_brief_with_target_includes_decision_buckets():
    target = _target(title_keywords=["software engineer"], locations=["Atlanta, GA"])
    postings = [
        JobPosting(
            title="Software Engineer",
            company="Good Co",
            description="Python SQL Git teamwork",
            location="Atlanta, GA",
            skills=["Python", "SQL", "Git"],
        ),
        JobPosting(
            title="Software Engineer",
            company="Stretch Co",
            description="Python only",
            location="Atlanta, GA",
            skills=["Python"],
        ),
        JobPosting(
            title="Marketing Manager",
            company="Mismatch Co",
            description="General",
            location="Atlanta, GA",
        ),
    ]
    brief = generate_brief(postings, target=target)
    assert "## Decision Buckets" in brief
    assert "### Reachable" in brief
    assert "### Stretch" in brief
    assert "### Mismatch" in brief
    assert "Good Co" in brief
    assert "Stretch Co" in brief
    assert "Mismatch Co" in brief
    assert "missing required skill(s)" in brief or "Weak signal" in brief
