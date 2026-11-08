# Calliope Dashboard

An interactive dashboard for exploring Calliope 0.7 model inputs, planning
results, and operate results.

The dashboard is a standalone, general-purpose viewer for solved Calliope
models and compatible NetCDF exports. It reads existing results; it does not
run optimisation or depend on a particular model or study.

## Quick start

The reproducible environment includes Calliope `0.7.0.dev7`, CBC, Dash, and the
dashboard package:

```bash
make setup
# Install the local Calliope fork containing the current table/inputs schema.
conda run -n calliope-dashboard-070 python -m pip install --no-deps --editable /path/to/thd-spatial-ai-calliope
make check
make run
```

`make run` opens the included German-scale example. The terminal prints the
local address; stop the server with `Ctrl+C`. The example has electricity and
illustrative heat, plus Baseline and High demand (+20%) scenarios.

The published Conda package and the newer local fork both report `0.7.0.dev7`
but accept different data-table fields. The model generators in this checkout
use the fork's `table` / `inputs` format. Verify `calliope.__file__` as well as
its version; see [environment setup](docs/environments.md).

If the correct Calliope environment already exists, install only this checkout:

```bash
python -m pip install --no-deps --editable /path/to/intern-calliope-visualization
```

## Open a solved Calliope result from Python

The main API accepts any solved Calliope result as an `xarray.Dataset`:

```python
from calliope_dashboard import CalliopeDashboard

dashboard = CalliopeDashboard(
    model_factory=my_model_factory,
    solution=solved_model.results,
)
dashboard.start()
```

`model_factory` recreates the corresponding unsolved model so that its inputs
and metadata can be combined with the supplied result dataset. No optimisation
is run by `start()`.

Pass `port=8051` to `CalliopeDashboard(...)` when port 8050 is occupied. Call
`dashboard.stop()` when finished, or use the dashboard as a context manager.
This single-solution API copies the supplied solution to both Planning and Operate
files; it does not run a separate Operate solve. To compare independently solved
Planning and Operate results, open their paired exports with `--model-dir`.

## Open an existing NetCDF export

The directory must contain compatible `planning.nc` and `operate.nc` files with
Calliope's `inputs`, `results`, and `attrs` groups:

```bash
calliope-dashboard \
  --model-dir /absolute/path/to/dashboard-data \
  --port 8050 \
  --default-tab results_planning
```

An optional `dashboard_scenarios.json` in the same directory lists scenario IDs,
labels and relative Planning/Operate paths. Its `default` field chooses the
initial scenario. See the included
[scenario manifest](models/1_german_scale/dashboard_scenarios.json) for an example.
Each export must have compatible nodes, coordinates, connections and time axes;
technology and carrier sets can differ. Restart the server after replacing exports.

## Planning views

Planning mode supports three perspectives:

- **All locations** aggregates selected-carrier results across all nodes by technology. KPI cards
  show modeled cost, CAPEX, time-window OPEX, installed flow capacity, production,
  and CO₂. The charts and detail table show the technology breakdown.
- **By location** shows the same metrics for one model node.
- **By technology** compares one technology across model nodes.

Production and demand time series respect the selected carrier and time window.
Each KPI has a question-mark explanation on hover or keyboard focus. A missing
`co2` class is shown as unavailable rather than measured zero.

Costs are carrier-exclusive: a node/technology connected to multiple carriers
is classified as Shared, and its undivided costs are excluded from carrier
summaries. Its physical flows and capacities remain visible. CAPEX is upfront
investment; modeled cost includes annualised investment, so the two must not
be added together. The whole-model technology cost table is temporarily hidden;
its reconciliation helper and tests remain available. See
[cost accounting](docs/dashboard-costs-and-time-2026-11-03.md).

## Repository layout

- `calliope_dashboard/`: public Python API and server command.
- `app/`: Dash layouts, callbacks, and data loading.
- `helpers/`: Calliope/xarray-to-dashboard adapters.
- `models/`: reproducible NetCDF fixtures and historical examples.
- `tests/`: helper, aggregation, API, and Dash smoke tests.
- `docs/`: architecture and environment details.

The current implementation targets Calliope `0.7.0.dev7`. See
[`docs/architecture.md`](docs/architecture.md) for the data boundary and
[`docs/environments.md`](docs/environments.md) for environment maintenance.

## Time controls, Operate and maps

Scenario and Carrier sit to the right of the model title on wide screens; the
time panel stays separately at the top right. These controls apply across all
tabs. Edit dates or the slider, then press **Apply** to recalculate.
The maximum selected duration is one calendar year, including the final
selected timestep; longer simulations remain selectable in yearly windows.

Demand coverage defaults to **Auto (≤60 bars)**, selecting readable hour/day/
week/month bins and summing energy after allocating each original timestep.
**Hourly (all)** retains the original resolution. A full-screen button expands
the card; its upper-right question mark explains proportional allocation of
met demand to local output/imports, which is not physical origin tracing.

Maps place arrowheads near receiving nodes, respect link direction and carrier,
and fit the coordinate extent. Missing coordinates cannot be recovered from a
later YAML edit: re-export the model. Layouts support square desktop windows
and laptop screens; a dedicated mobile design is outside this update.

Data failures clear affected results and display a dismissible banner. Operate
errors mention possibly missing dispatch exports; changing tabs clears the
banner. Detailed failures are logged on the server.

## Current validation and documentation

The test suite covers scenarios and carriers, accounting, time controls, coverage,
map geometry, Inputs corner cases and error handling. Run `make test` to check
the current checkout. These checks establish consistency with model exports, not
calibration of a real energy system. The German example intentionally allows
unmet demand.

- [Progress since the previous commit](docs/dashboard-progress-2026-11-07.md)
- [Input variables](calliope-input-docs.md)
- [Planning values and formulas](calliope-results-docs.md)
- [Operate values and interpretation](calliope-operate-results-docs.md)
- [German scenario validation](docs/german-scale-scenarios-2026-11-02.md)
