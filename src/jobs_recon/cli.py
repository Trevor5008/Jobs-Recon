import argparse
import json
import sys
from pathlib import Path

from jobs_recon.brief import generate_brief
from jobs_recon.google_search import (
    GoogleSearchConfigError,
    fetch_google_search,
    get_google_search_config,
    load_google_search_fixture,
)
from jobs_recon.parser import load_postings
from jobs_recon.search_discovery import generate_dork_queries, parse_google_search_items
from jobs_recon.search_feasibility import (
    build_feasibility_run,
    generate_search_feasibility_report,
)
from jobs_recon.source_feasibility import generate_feasibility_report, get_source_profile
from jobs_recon.target import load_target_brief

SOURCE_FEASIBILITY_COMMAND = "source-feasibility"
GOOGLE_DORKS_COMMAND = "google-dorks"


def build_brief_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobs-recon",
        description="Generate a local job-market recon brief from a JSON postings file.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a JSON file containing job postings.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the Markdown recon brief will be written.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        help="Optional path to a target brief JSON file that scopes the recon pass.",
    )
    return parser


def build_source_feasibility_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"jobs-recon {SOURCE_FEASIBILITY_COMMAND}",
        description="Generate a source feasibility report before building an adapter.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source to evaluate (for example: handshake).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the Markdown feasibility report will be written.",
    )
    return parser


def run_brief(argv: list[str]) -> int:
    parser = build_brief_parser()
    args = parser.parse_args(argv)

    input_path: Path = args.input
    output_path: Path = args.output

    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        postings = load_postings(input_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not postings:
        print("Error: input file contains no postings.", file=sys.stderr)
        return 1

    target = None
    if args.target is not None:
        target_path: Path = args.target
        if not target_path.is_file():
            print(f"Error: target file not found: {target_path}", file=sys.stderr)
            return 1
        try:
            target = load_target_brief(target_path)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    brief = generate_brief(postings, target=target)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(brief, encoding="utf-8")
    print(f"Wrote recon brief to {output_path}")
    return 0


def build_google_dorks_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"jobs-recon {GOOGLE_DORKS_COMMAND}",
        description=(
            "Generate target-aware Google dorks and optionally evaluate Google "
            "Custom Search JSON API results for discovery feasibility."
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Path to a target brief JSON file used to generate dork queries.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path where the Markdown search feasibility report will be written.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate dork queries only; do not load fixtures or call the live API.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Path to a saved Google Custom Search JSON API response fixture.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live Google Custom Search JSON API requests (requires env credentials).",
    )
    return parser


def run_google_dorks(argv: list[str]) -> int:
    parser = build_google_dorks_parser()
    args = parser.parse_args(argv)

    if args.live and args.fixture is not None:
        print("Error: --live and --fixture cannot be used together.", file=sys.stderr)
        return 1

    target_path: Path = args.target
    if not target_path.is_file():
        print(f"Error: target file not found: {target_path}", file=sys.stderr)
        return 1

    try:
        target = load_target_brief(target_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    queries = generate_dork_queries(target)

    if args.dry_run and args.fixture is not None:
        print("Error: --dry-run and --fixture cannot be used together.", file=sys.stderr)
        return 1

    if args.dry_run and args.live:
        print("Error: --dry-run and --live cannot be used together.", file=sys.stderr)
        return 1

    mode = "dry-run"
    results = []

    if args.fixture is not None:
        fixture_path: Path = args.fixture
        if not fixture_path.is_file():
            print(f"Error: fixture file not found: {fixture_path}", file=sys.stderr)
            return 1
        try:
            payload = load_google_search_fixture(str(fixture_path))
            query_text = queries[0].query if queries else ""
            results = parse_google_search_items(payload, query_text)
            mode = "fixture"
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    elif args.live:
        try:
            api_key, cse_id = get_google_search_config()
        except GoogleSearchConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        mode = "live"
        for search_query in queries:
            try:
                payload = fetch_google_search(
                    search_query.query,
                    api_key=api_key,
                    cse_id=cse_id,
                )
            except (RuntimeError, ValueError) as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            results.extend(parse_google_search_items(payload, search_query.query))
    elif not args.dry_run:
        if args.output is None:
            print(
                "Error: no results source selected. Use --dry-run, --fixture, or --live.",
                file=sys.stderr,
            )
            return 1

    run = build_feasibility_run(
        target_name=target.name,
        queries=queries,
        results=results,
        mode=mode,
    )
    report = generate_search_feasibility_report(run)

    if args.output is not None:
        output_path: Path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Wrote search feasibility report to {output_path}")
    elif args.dry_run:
        for index, search_query in enumerate(queries, start=1):
            print(f"Query {index} ({search_query.label}):")
            print(search_query.query)
            print()
    else:
        print(report)

    if args.dry_run:
        print(f"Generated {len(queries)} dork quer{'y' if len(queries) == 1 else 'ies'}.")

    return 0


def run_source_feasibility(argv: list[str]) -> int:
    parser = build_source_feasibility_parser()
    args = parser.parse_args(argv)

    try:
        profile = get_source_profile(args.source)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    report = generate_feasibility_report(profile)
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote source feasibility report to {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == SOURCE_FEASIBILITY_COMMAND:
        return run_source_feasibility(argv[1:])

    if argv and argv[0] == GOOGLE_DORKS_COMMAND:
        return run_google_dorks(argv[1:])

    return run_brief(argv)


if __name__ == "__main__":
    raise SystemExit(main())
