import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from utils.parser import load_postings

from jobs_recon.brief import generate_brief
from jobs_recon.discovery_provider import GoogleGroundingProvider, ManualFixtureProvider
from jobs_recon.google_grounding import (
    GoogleGroundingConfigError,
    check_google_grounding_config,
    format_config_check_report,
)
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

# Build the parser for the brief command
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

# Build the parser for the source feasibility command
def build_source_feasibility_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"jobs-recon {SOURCE_FEASIBILITY_COMMAND}",
        description="Generate a source feasibility report before building an adapter.",
    )
    # Add the source argument
    parser.add_argument(
        "--source",
        required=True,
        help="Source to evaluate (for example: handshake).",
    )
    # Add the output argument
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the Markdown feasibility report will be written.",
    )
    return parser

# Build the parser for the search grounding command
def build_search_grounding_parser() -> argparse.ArgumentParser:
    # Create the parser
    parser = argparse.ArgumentParser(
        prog=f"jobs-recon {SEARCH_GROUNDING_COMMAND}",
        description=(
            "Generate target-aware grounded-search prompts and optionally evaluate "
            "Gemini / Vertex Google Search grounding for discovery feasibility."
        ),
    )
    # Add the target argument
    parser.add_argument(
        "--target",
        type=Path,
        help="Path to a target brief JSON file used to generate discovery prompts.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check Vertex / Gemini grounding configuration without making a live API call.",
    )
    # Add the output argument
    parser.add_argument(
        "--output",
        type=Path,
        help="Path where the Markdown search feasibility report will be written.",
    )
    # Add the dry-run argument
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate discovery prompts only; do not load fixtures or call live grounding.",
    )
    # Add the fixture argument
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Path to a saved grounded-response JSON fixture.",
    )
    # Add the live argument
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run live Gemini / Vertex Google Search grounding "
            "(requires credentials and google-genai)."
        ),
    )
    return parser

# Run the brief command
def run_brief(argv: list[str]) -> int:
    parser = build_brief_parser()
    args = parser.parse_args(argv)

    # Get the input and output paths
    input_path: Path = args.input
    output_path: Path = args.output

    # Check if the input file exists
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    # Load the postings
    try:
        postings = load_postings(input_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Check if the input file contains any postings
    if not postings:
        print("Error: input file contains no postings.", file=sys.stderr)
        return 1

    # Load the target brief
    target = None
    if args.target is not None:
        target_path: Path = args.target
        # Check if the target file exists
        if not target_path.is_file():
            print(f"Error: target file not found: {target_path}", file=sys.stderr)
            return 1
        # Load the target brief
        try:
            target = load_target_brief(target_path)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    # Generate the brief
    brief = generate_brief(postings, target=target)
    # Create the output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(brief, encoding="utf-8")
    # Write the brief to the output file
    print(f"Wrote recon brief to {output_path}")
    return 0

# Run the search grounding command
def run_search_grounding(argv: list[str]) -> int:
    parser = build_search_grounding_parser()
    args = parser.parse_args(argv)

    if args.check_config:
        if args.dry_run or args.fixture is not None or args.live or args.output is not None:
            print(
                "Error: --check-config cannot be combined with --dry-run, --fixture, --live, or --output.",
                file=sys.stderr,
            )
            return 1
        result = check_google_grounding_config()
        print(format_config_check_report(result))
        return 0 if result.ready else 1

    if args.target is None:
        print("Error: --target is required unless using --check-config.", file=sys.stderr)
        return 1

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

# Run the source feasibility command
def run_source_feasibility(argv: list[str]) -> int:
    # Build the parser
    parser = build_source_feasibility_parser()
    args = parser.parse_args(argv)

    # Get the source profile
    try:
        profile = get_source_profile(args.source)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Generate the feasibility report
    report = generate_feasibility_report(profile)
    # Create the output directory if it doesn't exist
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote source feasibility report to {output_path}")
    return 0

# Run the main command
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Check if the source feasibility command is used

    if argv and argv[0] == SOURCE_FEASIBILITY_COMMAND:
        return run_source_feasibility(argv[1:])
    # Check if the search grounding command is used
    if argv and argv[0] == SEARCH_GROUNDING_COMMAND:
        return run_search_grounding(argv[1:])
    # Run the brief command
    return run_brief(argv)


if __name__ == "__main__":
    raise SystemExit(main())
