from jobs_recon.brief import generate_brief
from jobs_recon.models import JobPosting

# Test that the brief handles empty skill matches
def test_brief_handles_empty_skill_matches():
    postings = [
        JobPosting(
            title="Generalist Role",
            company="Sample Inc",
            description="No listed tech keywords here.",
            location="Remote",
        )
    ]
    brief = generate_brief(postings)

    assert "Postings analyzed: 1" in brief
    assert "No vocabulary skills matched" in brief
    assert "Generalist Role — Sample Inc" in brief
    assert "Matched skills: None" in brief


# Test that the brief sorts skills by count then name
def test_brief_sorts_skills_by_count_then_name():
    postings = [
        JobPosting(title="A", company="Co", description="Git", skills=["Git"]),
        JobPosting(title="B", company="Co", description="SQL SQL", skills=["SQL"]),
        JobPosting(title="C", company="Co", description="Python Python", skills=["Python"]),
        JobPosting(title="D", company="Co", description="Python", skills=["Python"]),
    ]
    brief = generate_brief(postings)

    python_index = brief.index("Python: 2 postings")
    git_index = brief.index("Git: 1 posting")
    sql_index = brief.index("SQL: 1 posting")
    assert python_index < git_index
    assert git_index < sql_index
