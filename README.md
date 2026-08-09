# Calliope 0.7 Dashboard

This branch runs the existing Dash application with Calliope `0.7.0.dev7`.
The Inputs, Planning, and Operate tabs keep the original layout and callback
structure, while the helper classes read Calliope 0.7's native dimensions and
variable names.

## Requirements

- Miniforge, Miniconda, or another Conda distribution.
- GNU Make is recommended, but the setup script can also be run directly.

The project intentionally uses Conda instead of pip requirements or uv. Conda
installs the Python packages and the CBC solver from the same environment file.

## Setup

Create or update the complete environment with one command:

```bash
make setup
```

Without Make:

```bash
bash scripts/setup_environments.sh
```

Both commands create `calliope-dashboard-070` from `environment.yml`.

## Verify and run

Run the dashboard tests and a 24-hour Calliope/CBC solve:

```bash
make check
```

Start the dashboard:

```bash
make run
```

Dash prints the local address after startup. Stop it with `Ctrl+C`.

## Dashboard data

The branch includes two solved NetCDF fixtures generated from Calliope's
built-in `national_scale` example:

- `models/0.7_national_scale/planning.nc`
- `models/0.7_national_scale/operate.nc`

Regenerate both files with:

```bash
make generate
```

To display another Calliope 0.7 model, point the application at a folder that
contains `planning.nc` and `operate.nc`:

```bash
CALLIOPE_DASHBOARD_MODEL_DIR=/absolute/path/to/model \
conda run -n calliope-dashboard-070 python app/app.py
```

Each file must contain Calliope's `inputs`, `results`, and `attrs` NetCDF groups.

## Local Git branches

- `stable/calliope-0.6.10` is the tested Calliope 0.6.10 implementation.
- `migration/calliope-0.7.0-dev7` is this Calliope 0.7 implementation.
- `main` remains at the internship version; tag `internship-original` marks the
  starting commit.

Nothing needs to be pushed to use these local branches. See
[`docs/branches.md`](docs/branches.md) before merging changes between them.

## Repository layout

- `app/`: Dash layouts, callbacks, figures, and NetCDF loading.
- `helpers/`: the Calliope-to-dashboard compatibility boundary.
- `models/`: model sources and generated dashboard fixtures.
- `tests/`: data, helper, and Dash smoke tests.
- `docs/`: branch, architecture, and environment notes.
