# Dashboard architecture

## Data flow

The application uses four small layers:

1. `calliope_dashboard.CalliopeDashboard` selects a solution, combines it with
   the inputs from a model factory, and owns the local server lifecycle.
2. NetCDF is the stable hand-off between Calliope and the web process.
3. `helpers/` translates Calliope arrays into the small Python and pandas
   structures expected by the dashboard.
4. `app/` renders maps, charts, cards, and tables with Dash.

Neither the public API nor Dash callbacks run an optimisation. They only select
an existing solution and read the datasets loaded at application startup.

## Solution sources

The dashboard's core input is one Calliope-compatible solution dataset. It may
come directly from a normally solved model, from an existing NetCDF export, or
from another workflow that produces compatible results.

### Optional Pareto integration

`ParetoResult.solution(point_id)` contains the full result dataset but does not
duplicate model inputs for every point. `CalliopeDashboard.from_pareto(...)`
therefore also accepts the study's model factory. It creates an unsolved model,
attaches the selected result, and calls Calliope's own `to_netcdf` exporter.

The server runs in a subprocess. This keeps `app_data` immutable for the life of
one dashboard and allows notebook code to stop or replace the view explicitly.

## NetCDF files

Calliope 0.7 writes one file per solved model with three groups:

- `inputs`: processed model configuration and timeseries;
- `results`: planning or operate solution arrays;
- `attrs`: serialized configuration, runtime metadata, and solver status.

The application loads every group into memory and closes the file handle. It
uses the `h5netcdf` reader to avoid keeping native NetCDF handles open during
Dash callbacks.

## Calliope 0.7 dimensions

Calliope 0.7 stores `nodes`, `techs`, and `carriers` as separate dimensions.
The previous 0.6 implementation encoded combinations such as
`location::technology::carrier` in a single coordinate. Helpers now select the
separate dimensions directly, but their public methods remain stable so the
layouts and callbacks do not need a broad rewrite.

Important variable mappings are documented in
[`calliope-input-docs.md`](../calliope-input-docs.md),
[`calliope-results-docs.md`](../calliope-results-docs.md), and
[`calliope-operate-results-docs.md`](../calliope-operate-results-docs.md).

## Configuration boundary

The command-line layer sets `CALLIOPE_DASHBOARD_MODEL_DIR` before importing
`app/app_data.py`. The default is `models/1_german_scale`. A custom directory
must contain both `planning.nc` and `operate.nc` produced by the same Calliope
model family.

The helper classes are the version boundary. Code in layouts and callbacks
should call helper methods instead of reading xarray variables directly.
