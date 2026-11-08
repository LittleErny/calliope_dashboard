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

The Python API can combine an existing solution with an unsolved model factory
and export it for viewing. The server runs in a subprocess, keeping `app_data`
immutable for its lifetime and allowing the caller to stop or replace the view.

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

## Scenario and carrier isolation

`app_data` preloads the root pair and optionally the manifest's other pairs,
checks common nodes, coordinates, map connections and time axes, and caches
helpers by `(scenario, carrier)`. Technology and carrier sets can differ. A
scenario-dependent Carrier selector preserves a still-valid choice or selects
the first available carrier. Requests with a stale unavailable carrier raise
`PreventUpdate` until that selector updates, avoiding a misleading interim view.
Every numerical callback resolves that selection explicitly. Loaded datasets
are reused; the browser's dropdown does not change a shared active scenario.
Coordinates and time axes come from exports, not source YAML discovered later.

`helpers/carriers.py` keeps applicable physical flows while separating exclusive
costs from Shared costs at node/technology level. `helpers/costs.py` provides raw
whole-model reconciliation; the corresponding Planning layout is commented out.

## Applied controls and display aggregation

The browser edits draft slider/date values. Only Apply updates `applied-time`,
which feeds the expensive Python callbacks. Calendar-year limits include final
step duration. Coverage components are allocated per original timestep before
calendar aggregation; Auto caps bins at 60, while Hourly preserves source steps.
Full-screen behavior and resizing live in packaged browser assets.

## Errors and solve provenance

The shared Dash error handler logs exceptions, clears affected outputs, and
shows an Operate missing-export hint where relevant. Switching tabs clears both
banner style and text. A successful view is not evidence that a dispatch solve
occurred: `CalliopeDashboard.prepare()` currently copies its selected Planning
solution to `operate.nc` as well. Genuine rolling-horizon results require a
separately solved/exported Operate model passed through `--model-dir`.

See [current progress](dashboard-progress-2026-11-07.md) for validation and limits.
