#!/usr/bin/env bash
set -euo pipefail

conda_command="${CONDA_COMMAND:-conda}"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v "${conda_command}" >/dev/null 2>&1; then
    echo "Conda command not found: ${conda_command}" >&2
    echo "Install Miniforge, then run 'make setup' again." >&2
    exit 1
fi

"${conda_command}" env update --file environment.yml --prune
"${conda_command}" run -n calliope-dashboard-070 \
    python -m pip install --no-deps --editable "${project_root}"

echo "Dashboard environment: calliope-dashboard-070"
