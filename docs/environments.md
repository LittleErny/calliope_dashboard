# Conda environments

## Why there are two environments

Calliope 0.6.10 depends on Plotly 3.x. Dash 3.2 depends on Plotly 5 or newer. These requirements cannot be installed
in one valid environment.

The application therefore uses:

- `environment.yml` for the dashboard;
- `environment-model.yml` for model generation and CBC.

Both files use the `conda-forge` channel and pin the direct dependencies that define the supported runtime.

## Creating and updating

```bash
make setup
```

The setup script calls `conda env update --prune`, so the same command creates missing environments and updates
existing environments to match the YAML files.

If Mamba is installed:

```bash
make setup CONDA_COMMAND=mamba
```

## Running commands manually

```bash
conda run -n calliope-dashboard-0610 pytest -q
conda run -n calliope-dashboard-0610 python app/app.py
conda run -n calliope-model-0610 python scripts/check_model_environment.py
```

## Updating dependencies

Do not combine the two YAML files. Update one environment at a time and run `make check` after every version
change. Saved pickle compatibility must be checked when changing Python, pandas, numpy, or xarray.

The model check uses the project German model with a 24-hour subset. It verifies preprocessing, Pyomo, CBC, and an
optimal solver result without running the full dataset.
