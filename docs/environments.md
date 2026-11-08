# Conda environment

## One environment, explicit Calliope source

The 0.7 branch uses one environment named `calliope-dashboard-070`. Calliope,
CBC, Dash, Plotly, xarray, and the test runner are resolved together from
`environment.yml`.

Calliope `0.7.0.dev7` is published on the conda-forge `calliope_dev` label, so
that label appears before the normal conda-forge channel. It supplies the
bootstrap package and solver dependencies; source-model generation in this
checkout requires the newer local fork installed after setup. Dependency
versions alone cannot distinguish these two Calliope snapshots.

## Creating and updating

```bash
make setup
```

The setup script calls `conda env update --prune`. The same command creates a
missing environment or updates an existing environment to match the YAML file.

For models using the newer table schema, install a compatible Calliope checkout after setup:

```bash
conda run -n calliope-dashboard-070 python -m pip install --no-deps --editable ../thd-spatial-ai-calliope
conda run -n calliope-dashboard-070 python -c "import calliope; print(calliope.__version__, calliope.__file__)"
```

The published Conda build (7 September 2025) and the local fork both report
`0.7.0.dev7`. The fork includes upstream commit `8b9ba5d3` (16 December 2025),
which renamed data-table `data` to `table` and the `parameters` dimension to
`inputs`. The THD model and German model generator use that newer format.
Check the import path as well as the version; after another `make setup`,
reapply the editable install if Python imports the Conda package instead.

Mamba can be used as a faster Conda-compatible command:

```bash
make setup CONDA_COMMAND=mamba
```

## Common commands

```bash
conda run -n calliope-dashboard-070 pytest -q
conda run -n calliope-dashboard-070 python scripts/check_model_environment.py
conda run -n calliope-dashboard-070 python -m calliope_dashboard
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

## Verified source and notebook kernels

The 7 November checkpoint used a local Calliope checkout at `30d64b7c`,
installed editable with no dependency upgrades. Its table schema comes from
upstream. Verify the checkout and import path for your own environment.

After replacing an installed package, restart already-running notebook kernels
and dashboard servers: they may retain previously imported modules. The THD
annual Planning/Operate pair was regenerated on the fork and reloaded through
it; changing the installed package does not migrate historical exports by itself.
`python -m pip check` reported no broken requirements, and 83 dashboard tests
passed on this source. See [the checkpoint](dashboard-progress-2026-11-07.md).
