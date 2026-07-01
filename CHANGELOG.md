# Changelog

All notable milestones for Jobs Recon. Version numbers follow MVP releases.

## MVP 0.4.1 — Remove Source Feasibility

**Question:** Can Jobs Recon stay focused now that static source profiles are out of scope?

- Removed the `source-feasibility` CLI command and `sources/` package
- Removed Handshake-specific discovery triage and static source profiles
- Kept `search-grounding` for grounded lead discovery and actionability reports

**Does not do:** static job-board feasibility memos or Handshake-specific workflows.

## MVP 0.4 — Decision-Oriented Output

**Question:** Does the brief help the user decide what to do next?

- Added reachable/stretch/mismatch decision buckets for target-aware recon briefs
- Repeated skills now show compact example postings
- Next actions are conservative and evidence-based
- Grounded discovery reports include a lead actionability summary
- Preserved the boundary that grounded citations are discovery evidence, not full postings

**Does not do:** scraping, login automation, application tracking, ranking engines, or LLM-based classification.

## MVP 0.3.4 — Grounded Lead Triage

**Question:** Can Jobs Recon classify grounded citations into actionable source families without scraping?

- Added source-family and actionability triage for grounded leads
- Distinguished Dice, LinkedIn, Google Jobs/search, ATS, and employer leads
- Feasibility reports now explain what each lead is useful for
- Preserved the boundary that grounded snippets are not full job descriptions

**Does not do:** scrape job boards, automate browser/login flows, resolve redirect wrappers automatically, or import full postings from grounded snippets.

## MVP 0.3.2 — Vertex Grounding Config Hardening

**Question:** Can the working Vertex / Gemini grounding setup become a repeatable local workflow?

- Added `search-grounding --check-config` preflight (no live API call)
- Made Vertex the documented primary live path
- Separated `discovery_url` from `canonical_posting_url` on discovery leads
- Vertex redirect wrappers are preserved for provenance but not treated as canonical sources
- Expanded aggregator classification and added `availability_status` on leads
- Regrouped feasibility reports into Candidate Leads by availability
- Default live model: `gemini-2.5-flash`
- Deprecated Google Custom Search JSON API as an active discovery path

**Does not do:** auto-resolve redirect URLs, crawl postings, or mark leads active from grounded text alone.

## MVP 0.3.1 — Google Search Grounding Feasibility

**Question:** Can Gemini / Vertex Google Search grounding discover useful public posting URLs without Jobs Recon becoming a scraper?

- Added `search-grounding` CLI with `--dry-run`, `--fixture`, and `--live`
- Target-aware grounded-search prompt generation
- Optional Gemini / Vertex Google Search grounding via `google-genai`
- URL classification and Markdown feasibility reports with provenance
- Provider-neutral discovery design (`google_grounding`, `manual_fixture`)

Replaced the non-viable Google Custom Search JSON API / dorking path.

**Does not do:** scrape Google Jobs, browser automation, CAPTCHA bypass, or treat snippets as full job descriptions.

## MVP 0.3 — Target Search Brief

**Question:** Can the user define the scan scope before running a recon pass?

- Optional target brief JSON (`examples/target_brief.json`)
- Deterministic target matching with included/skipped explanations
- Target-aware Markdown recon brief
- Title keywords and locations as hard gates; seniority/skills as evidence signals

**Does not do:** live fetching, scraping, authentication, or recommendation logic.

## MVP 0.2 — Source Feasibility (removed in 0.4.1)

**Question:** Which source-evaluation path can Jobs Recon use without becoming Jobs-Radar again?

- Added `source-feasibility` CLI plumbing and a Handshake feasibility profile
- Later removed when Jobs Recon focused on public canonical leads and local inputs

## MVP 0.1 — Local Recon Brief

**Question:** Can I turn a small set of postings into a useful market brief?

- Local JSON postings input
- Deterministic skill extraction from a small vocabulary
- Markdown recon brief generation
- Source/provenance fields preserved

**Does not do:** live scraping, browser automation, database, frontend UI, application tracking, or LLM scoring.
