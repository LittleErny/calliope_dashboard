"""Small command-line entry point used by the public API."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Calliope dashboard.")
    parser.add_argument("--model-dir", type=Path, help="Directory containing planning.nc and operate.nc")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument(
        "--default-tab",
        choices=("inputs", "results_planning", "results_operate"),
        default="inputs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.model_dir is not None:
        os.environ["CALLIOPE_DASHBOARD_MODEL_DIR"] = str(args.model_dir.resolve())
    os.environ["CALLIOPE_DASHBOARD_DEFAULT_TAB"] = args.default_tab

    # Import only after setting the data directory: app_data loads NetCDF once.
    from app.app import app

    app.run(debug=False, host=args.host, port=args.port)
    return 0
