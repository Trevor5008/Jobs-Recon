import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from jobs_recon.brief import generate_brief
from jobs_recon.discovery_provider import GoogleGroundingProvider, ManualFixtureProvider
from jobs_recon.google_grounding import GoogleGroundingConfigError
from jobs_recon.parser import load_postings
from jobs_recon.search_discovery import summarize_target
from jobs_recon.search_feasibility import (
    build_feasibility_run,
    generate_search_feasibility_report,
)
from jobs_recon.source_feasibility import generate_feasibility_report, get_source_profile
from jobs_recon.target import load_target_brief

load_dotenv()

SOURCE_FEASIBILITY_COMMAND = "source-feasibility"
SEARCH_GROUNDING_COMMAND = "search-grounding"


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


def build_search_grounding_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"jobs-recon {SEARCH_GROUNDING_COMMAND}",
        description=(
            "Generate target-aware grounded-search prompts and optionally evaluate "
            "Gemini / Vertex Google Search grounding for discovery feasibility."
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Path to a target brief JSON file used to generate discovery prompts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path where the Markdown search feasibility report will be written.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate discovery prompts only; do not load fixtures or call live grounding.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Path to a saved grounded-response JSON fixture.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run live Gemini / Vertex Google Search grounding "
            "(requires credentials and google-genai)."
        ),
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


def run_search_grounding(argv: list[str]) -> int:
    parser = build_search_grounding_parser()
    args = parser.parse_args(argv)

    if args.live and args.fixture is not None:
        print("Error: --live and --fixture cannot be used together.", file=sys.stderr)
        return 1
    if args.dry_run and args.fixture is not None:
        print("Error: --dry-run and --fixture cannot be used together.", file=sys.stderr)
        return 1
    if args.dry_run and args.live:
        print("Error: --dry-run and --live cannot be used together.", file=sys.stderr)
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

    prompts = GoogleGroundingProvider().generate_queries(target)
    mode = "dry-run"
    responses = []
    provider_name = GoogleGroundingProvider.name

    if args.fixture is not None:
        fixture_path: Path = args.fixture
        if not fixture_path.is_file():
            print(f"Error: fixture file not found: {fixture_path}", file=sys.stderr)
            return 1
        try:
            fixture_provider = ManualFixtureProvider(str(fixture_path))
            provider_name = fixture_provider.name
            responses = [fixture_provider.discover(prompt) for prompt in prompts[:1]]
            mode = "fixture"
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    elif args.live:
        try:
            live_provider = GoogleGroundingProvider()
            provider_name = live_provider.name
        except GoogleGroundingConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        mode = "live"
        for prompt in prompts[:1]:
            try:
                responses.append(live_provider.discover(prompt))
            except (GoogleGroundingConfigError, RuntimeError, ValueError) as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
    elif not args.dry_run:
        if args.output is None:
            print(
                "Error: no results source selected. Use --dry-run, --fixture, or --live.",
                file=sys.stderr,
            )
            return 1

    run = build_feasibility_run(
        target_name=target.name,
        target_summary=summarize_target(target),
        target_path=str(target_path),
        prompts=prompts,
        responses=responses,
        mode=mode,
        provider=provider_name,
    )
    report = generate_search_feasibility_report(run)

    if args.output is not None:
        output_path: Path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Wrote search feasibility report to {output_path}")
    elif args.dry_run:
        for index, discovery_prompt in enumerate(prompts, start=1):
            print(f"Prompt {index} ({discovery_prompt.label}):")
            print(discovery_prompt.prompt)
            print()
    else:
        print(report)

    if args.dry_run:
        print(f"Generated {len(prompts)} discovery prompt(s).")

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

    if argv and argv[0] == SEARCH_GROUNDING_COMMAND:
        return run_search_grounding(argv[1:])

    return run_brief(argv)


if __name__ == "__main__":
    raise SystemExit(main())
