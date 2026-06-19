import argparse
import sys
from pathlib import Path

from jobs_recon.brief import generate_brief
from jobs_recon.parser import load_postings
from jobs_recon.source_feasibility import generate_feasibility_report, get_source_profile

SOURCE_FEASIBILITY_COMMAND = "source-feasibility"


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

    brief = generate_brief(postings)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(brief, encoding="utf-8")
    print(f"Wrote recon brief to {output_path}")
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

    return run_brief(argv)


if __name__ == "__main__":
    raise SystemExit(main())
