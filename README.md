# Jobs Recon

Jobs Recon is a CLI-first job-market reconnaissance tool. It turns a small, local set of job postings into a short Markdown brief so you can decide what to focus on next.

This project is a smaller pivot from Jobs-Radar, which grew into a broader job-intelligence system. Jobs Recon stays intentionally narrow: parse local inputs, extract simple signals, and write one evidence-first brief.

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

Real source ingestion, including Handshake feasibility, is future work.

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

The output brief includes posting counts, companies, locations, repeated skills, per-posting notes, and a short next-actions section. Treat results as directional signal from a small sample, not certainty about the wider market.

## Input format

`examples/sample_postings.json` shows the expected shape: a JSON array of posting objects with required fields `title`, `company`, and `description`, plus optional `source`, `source_url`, and `location`.

## License

MIT — see [LICENSE](LICENSE).
