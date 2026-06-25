# Jobs Recon

Jobs Recon is a CLI-first job-market reconnaissance tool. 
- It turns a small, local set of job postings into a short Markdown brief so you can decide what to focus on next.

- This project is a smaller pivot from Jobs-Radar, which grew into a broader job-intelligence system. 
- Jobs Recon stays intentionally narrow: parse local inputs, extract simple signals, and write one evidence-first brief.

## MVP 0.1

MVP 0.1 answers one question:

> Can I turn a small set of postings into a useful market brief?

It supports this workflow:

1. Provide a local JSON file of job postings.
2. Jobs Recon parses and validates each posting.
3. Jobs Recon extracts a few normalized fields and matches skills from a small built-in vocabulary.
4. Jobs Recon writes one Markdown recon brief.

## What MVP 0.1 does not do yet

- Live scraping or automated source ingestion
- Handshake adapter (feasibility spike needed; may be login-gated or unsuitable for automation)
- Browser automation, authentication, or schedulers
- Database, frontend UI, application tracking, or recommendation engines
- LLM integration or complex scoring

Real source ingestion remains future work until a source passes feasibility review.

## MVP 0.2

MVP 0.2 answers one question:

> Which high-signal source can Jobs Recon use first without becoming Jobs-Radar again?

It adds a source feasibility workflow. Before building any adapter, Jobs Recon can generate a Markdown report that frames expected signal, access constraints, possible ingestion paths, and a manual investigation checklist.

Handshake is included as the first feasibility profile because it is likely high-signal for internships, student roles, and new-grad recruiting. 
- It is **not** implemented as an adapter in MVP 0.2. 
_Access may be login-gated, school-affiliated, or unsuitable for automation until terms and account capabilities are reviewed manually._

### Generate a source feasibility report

```bash
python -m jobs_recon source-feasibility --source handshake --output output/handshake_feasibility.md
```

## MVP 0.3

MVP 0.3 answers one question:

> Can the user define the scan scope before running a recon pass?

Jobs Recon is still local-only. A target search brief lets you describe the role scope before generating a recon brief from local postings. The output explains which postings were included, which were skipped, and why.

Title keywords and locations act as hard gates. Seniority and required skills are evidence signals or warnings, not a ranking engine.

### Example target brief

See `examples/target_brief.json` for the expected JSON shape.

### Generate a scoped recon brief

```bash
python -m jobs_recon --input examples/sample_postings.json --target examples/target_brief.json --output output/recon_brief.md
```

Without a target brief, the MVP 0.1 command still works:

```bash
python -m jobs_recon --input examples/sample_postings.json --output output/recon_brief.md
```

### What MVP 0.3 does not do

- Live fetching, scraping, or source ingestion
- Handshake adapter work
- Authentication, API integrations, or scheduling
- Database, frontend UI, recommendation engine, or LLM integration

## MVP 0.3.1

MVP 0.3.1 answers one question:

> Can Gemini / Vertex Google Search grounding discover useful public posting URLs without Jobs Recon becoming a scraper?

This milestone is a **discovery feasibility spike**, not full ingestion. Jobs Recon can generate target-aware grounded-search prompts, optionally call Gemini / Vertex with Google Search grounding when credentials are configured, classify cited URLs by likely source type, and export a Markdown feasibility report.

The earlier **Google Custom Search JSON API / dorking path is not used** because it is not viable for the current account setup. This spike evaluates grounding instead and keeps the design provider-neutral for future discovery backends.

It does **not** scrape Google Jobs, run browser automation, bypass CAPTCHAs, or treat grounded answer text as complete job descriptions.

### Example target brief for discovery

See `examples/target-ai-engineer.json` for a Miami / South Florida AI and software intern/junior target.

### Generate prompts only (dry run)

```bash
python -m jobs_recon search-grounding --target examples/target-ai-engineer.json --dry-run
```

### Generate a feasibility report from fixture JSON (tests / offline)

```bash
python -m jobs_recon search-grounding \
  --target examples/target-ai-engineer.json \
  --fixture tests/fixtures/google_grounding_response.json \
  --output output/google_grounding_feasibility.md
```

### Run live Google Search grounding (requires credentials)

Install the optional grounding extra:

```bash
uv pip install -e ".[dev,grounding]"
```

Set environment variables (see `.env.example`). **Vertex AI is the recommended live path.**

- `GOOGLE_GENAI_USE_VERTEXAI=true`
- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `GEMINI_MODEL` — optional, defaults to `gemini-2.5-flash`
- `GOOGLE_APPLICATION_CREDENTIALS` — path to local service account JSON

Gemini API key mode remains available if configured, but Vertex is the documented primary workflow.

```bash
python -m jobs_recon search-grounding \
  --target examples/target-ai-engineer.json \
  --live \
  --output output/google_grounding_feasibility.md
```

If credentials are missing, `--live` exits with a clear error. Use `--dry-run` or `--fixture` instead.

### Recommended workflow

1. Generate target-aware grounded-search prompts with `--dry-run`.
2. Run fixture or controlled live grounding checks.
3. Inspect cited/source URLs manually.
4. Select promising canonical employer or ATS URLs (prefer Greenhouse, Lever, Ashby, Workable, and similar ATS domains over aggregators).
5. Feed selected URLs or pasted posting text into Jobs Recon later for skill matching and brief generation.

### What MVP 0.3.1 does not do

- Google Custom Search JSON API integration
- Google Jobs UI scraping or browser automation
- CAPTCHA bypass, login/session automation, or broad crawling
- LinkedIn or Handshake scraping
- Ranking/recommendation logic or application tracking
- Treating grounded responses as final posting evidence for skill matching

## MVP 0.3.2

MVP 0.3.2 answers one question:

> Can the working Vertex / Gemini grounding setup become a repeatable local Jobs Recon workflow?

This milestone hardens the now-working Vertex path. It makes configuration repeatable, separates discovery URLs from canonical posting URLs, and improves feasibility reporting so grounded leads are easier to triage manually.

The **Google Custom Search JSON API is deprecated** in Jobs Recon and should not be treated as the active discovery path.

### Vertex-first setup

Copy `.env.example` to `.env` and set:

- `GOOGLE_GENAI_USE_VERTEXAI=true`
- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION` (for example `us-central1`)
- `GEMINI_MODEL=gemini-2.5-flash`
- `GOOGLE_APPLICATION_CREDENTIALS` — absolute path to your local service account JSON

Keep `.env` and `gcp-credentials.json` out of git. The service account needs **Agent Platform User** (`roles/aiplatform.user`) on the project.

Install the optional grounding extra:

```bash
uv pip install -e ".[dev,grounding]"
```

### Check config (no live API call)

```bash
python -m jobs_recon search-grounding --check-config
```

### Generate prompts only (dry run)

```bash
python -m jobs_recon search-grounding --target examples/target-ai-engineer.json --dry-run
```

### Generate a feasibility report from fixture JSON

```bash
python -m jobs_recon search-grounding \
  --target examples/target-ai-engineer.json \
  --fixture tests/fixtures/google_grounding_response.json \
  --output output/google_grounding_feasibility.md
```

### Run live Vertex grounding

```bash
python -m jobs_recon search-grounding \
  --target examples/target-ai-engineer.json \
  --live \
  --output output/google_grounding_feasibility_live.md
```

### How to interpret grounded leads

- **Discovery URL** — what Vertex returned, including redirect wrappers
- **Canonical posting URL** — the employer/ATS page to import later, if resolved
- **Availability** — `active`, `inactive`, `login_gated`, `aggregator_only`, or `uncertain`
- Grounded answer text is triage-only and is **not** enough to mark a lead active
- Aggregator echoes and redirect-only citations are not actionable postings by themselves

### Recommended workflow

1. Run `search-grounding --check-config`
2. Generate target-aware prompts with `--dry-run`
3. Run fixture or controlled live grounding
4. Resolve discovery URLs to canonical employer/ATS pages manually
5. Import selected URLs or pasted posting text into Jobs Recon later

## Setup

Requires Python 3.10+.

```bash
# Optional: create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode (recommended)
pip install -e ".[dev]"
```

With [uv](https://github.com/astral-sh/uv):

```bash
uv pip install -e ".[dev]"
```

## Run tests

```bash
python -m pytest
```

## Generate a recon brief

```bash
python -m jobs_recon --input examples/sample_postings.json --output output/recon_brief.md
```

Or, after install:

```bash
jobs-recon --input examples/sample_postings.json --output output/recon_brief.md
```

The output brief includes posting counts, companies, locations, repeated skills, per-posting notes, and a short next-actions section. 
_Treat results as directional signal from a small sample, not certainty about the wider market._

## Input format

`examples/sample_postings.json` shows the expected shape: a JSON array of posting objects with required fields `title`, `company`, and `description`, plus optional `source`, `source_url`, and `location`.

## License

MIT — see [LICENSE](LICENSE).
