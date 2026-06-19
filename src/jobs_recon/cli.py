import argparse
import sys
from pathlib import Path

from jobs_recon.brief import generate_brief
from jobs_recon.parser import load_postings


def build_parser() -> argparse.ArgumentParser:
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
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


if __name__ == "__main__":
    raise SystemExit(main())
