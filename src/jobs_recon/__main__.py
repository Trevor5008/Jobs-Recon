import sys

try:
    from jobs_recon.cli import main
except ModuleNotFoundError as exc:
    missing = exc.name or "unknown"
    print(
        "Jobs Recon is not available in this Python environment "
        f"(missing module: {missing}).",
        file=sys.stderr,
    )
    print(
        "Install and run from the project environment:\n"
        "  uv sync --all-extras\n"
        "  uv run jobs-recon --help\n"
        "Or activate .venv after uv sync and use python -m jobs_recon.",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

raise SystemExit(main())
