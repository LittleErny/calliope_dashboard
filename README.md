# Calliope Dashboard

An interactive dashboard for exploring Calliope 0.7 model inputs, planning
results, and operate results.

The dashboard is a general-purpose viewer: it does not optimise a model and is
not tied to multi-objective optimisation. It can open an ordinary solved
Calliope model, an existing NetCDF export, or one selected solution from a
Pareto study.

## Quick start

The reproducible environment includes Calliope `0.7.0.dev7`, CBC, Dash, and the
dashboard package:

```bash
make setup
make check
make run
```

`make run` opens the included German-scale example. The terminal prints the
local address; stop the server with `Ctrl+C`.

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

## Open one Pareto point

`model_factory` must create the same unsolved Calliope model configuration used
for the Pareto study. It supplies model inputs and metadata; the selected
`ParetoResult` supplies the solved result arrays.

```python
from calliope_dashboard import CalliopeDashboard

dashboard = CalliopeDashboard.from_pareto(
    result=weighted_sum_result,
    point_id=8,
    model_factory=thd_co2_model,
)

url = dashboard.start()  # prints and returns http://127.0.0.1:8050
```

This is an optional convenience adapter around the same general dashboard API.
When finished:

```python
dashboard.stop()
```

The class is also a context manager:

```python
with CalliopeDashboard.from_pareto(
    result=weighted_sum_result,
    point_id=8,
    model_factory=thd_co2_model,
) as dashboard:
    print(dashboard.url)
```

Use `port=8051` when port 8050 is already occupied. Pass `data_dir=...` if the
generated `planning.nc`, `operate.nc`, and `selection.json` should be kept;
otherwise a temporary directory is used.

## Open an existing NetCDF export

The directory must contain compatible `planning.nc` and `operate.nc` files with
Calliope's `inputs`, `results`, and `attrs` groups:

```bash
calliope-dashboard \
  --model-dir /absolute/path/to/dashboard-data \
  --default-tab results_planning
```

## Planning views

Planning mode supports three perspectives:

- **All locations** aggregates the complete system by technology. KPI cards
  show total CAPEX, time-window OPEX, installed flow capacity, production, and
  CO₂. The charts and detail table show the corresponding technology breakdown.
- **By location** shows the same metrics for one model node.
- **By technology** compares one technology across model nodes.

Production and demand time series respect the selected carrier and time window.
The CO₂ panels appear when the model contains a `co2` cost class.

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
