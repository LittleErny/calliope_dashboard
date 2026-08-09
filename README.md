# Calliope 0.6.10 Dashboard

This project is a Dash application for inspecting Calliope model inputs, planning results, and operate results.
This branch supports Calliope 0.6.10 datasets.

## Requirements

- Miniforge or another Conda distribution.
- Linux, macOS, or Windows.
- GNU Make is optional. The setup script can also be called directly.

The dashboard and Calliope model runner use separate environments. Calliope 0.6.10 requires Plotly 3, while the
dashboard uses Dash 3 and Plotly 6. Keeping the environments separate avoids an invalid dependency combination.

## Setup

Create both environments with one command:

```bash
make setup
```

Without Make:

```bash
bash scripts/setup_environments.sh
```

The command creates:

- `calliope-dashboard-0610` for the Dash application and tests.
- `calliope-model-0610` for Calliope 0.6.10 and CBC.

## Run the dashboard

```bash
make run
```

The application uses the Mainkofen pickle files in `models/mainkofen_case_study` by default.
To select another model folder:

```bash
CALLIOPE_DASHBOARD_MODEL_DIR=/absolute/path/to/model \
conda run -n calliope-dashboard-0610 python app/app.py
```

The selected folder must contain:

- `mainkofen_model_inputs.pkl`
- `mainkofen_model_results_planning.pkl`
- `mainkofen_model_results_operate.pkl`

## Verify the installation

```bash
make check
```

This runs the dashboard regression tests, verifies CBC, and solves a 24-hour version of the German example model.

## Regenerate Mainkofen data

```bash
make generate
```

This runs `models/mainkofen_case_study/calliope_to_pkl.py` in the model environment. The full Mainkofen model
contains 8760 hourly timesteps and may take some time to solve.

## Repository layout

- `app/`: Dash layouts, callbacks, figures, and data loading.
- `helpers/`: accessors for Calliope 0.6.10 xarray datasets.
- `models/`: Calliope model definitions, timeseries, and saved outputs.
- `tests/`: regression and application smoke tests.
- `docs/`: architecture and environment documentation.

See [docs/architecture.md](docs/architecture.md) and [docs/environments.md](docs/environments.md) for more detail.
