# Conda environment

## One environment

The 0.7 branch uses one environment named `calliope-dashboard-070`. Calliope,
CBC, Dash, Plotly, xarray, and the test runner are resolved together from
`environment.yml`.

Calliope `0.7.0.dev7` is published on the conda-forge `calliope_dev` label, so
that label appears before the normal conda-forge channel. All direct runtime
dependencies are pinned to the versions verified by this branch.

## Creating and updating

```bash
make setup
```

The setup script calls `conda env update --prune`. The same command creates a
missing environment or updates an existing environment to match the YAML file.

Mamba can be used as a faster Conda-compatible command:

```bash
make setup CONDA_COMMAND=mamba
```

## Common commands

```bash
conda run -n calliope-dashboard-070 pytest -q
conda run -n calliope-dashboard-070 python scripts/check_model_environment.py
conda run -n calliope-dashboard-070 python app/app.py
```

`make check` combines the first two checks. The model check verifies the exact
Calliope version, the CBC executable, Pyomo's solver connection, and an optimal
24-hour solve.

## Updating dependencies

Change only `environment.yml`, run `make setup`, then run `make check` and
`make generate`. Do not add a second pip requirements file: it would create a
second, independent dependency definition and would not install CBC.

Calliope exports with `netCDF4`. The dashboard reads the same standard files
through `h5netcdf`, which was verified without NumPy ABI warnings in this
environment.
