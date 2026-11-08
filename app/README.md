# App

This folder contains the Dash application. It reads solved Calliope 0.7 data;
it does not run the optimisation model.

## Structure

- `app.py`: application entry point.
- `app_data.py`: loads NetCDF groups and creates helper instances.
- `figures.py`: shared figure and resampling functions.
- `layouts/`: Inputs, Planning, Operate, and common layouts.
- `callbacks/`: data binding and user interaction.

## Data selection

The default folder is `models/1_german_scale`. Select another export without
editing Python source:

```bash
calliope-dashboard --model-dir /absolute/path/to/model
```

The folder must contain `planning.nc` and `operate.nc`. Both files must have
Calliope's `inputs`, `results`, and `attrs` groups and must describe compatible
nodes, coordinates, map connections, and time axes. Scenario technology and
carrier sets may differ.

## Tabs

- Inputs shows topology, demand profiles, supply limits, and input parameters.
- Planning shows system-wide or per-location capacity, costs, production,
  emissions, and detail tables.
- Operate shows unmet demand, line loading, flows, and storage operation.

The global scenario, carrier, and time controls are shared by all three tabs.
Labels assume kW for flow capacity, kWh for energy, EUR for monetary cost, and
kg for a cost class named `co2`.

## Applied time and coverage

`time_window.py` computes sparse date marks and calendar-year limits.
`assets/time_window.js` edits draft dates locally; only Apply updates the
`applied-time` store used by Python callbacks. `coverage.py` chooses the first
calendar interval with at most 60 nonempty bins. Allocation happens at the
original resolution before energy is summed. `assets/coverage.js` manages
full-screen cards and requests chart resizing on entry/exit.

`assets/dashboard.css` and `assets/z_consumer.css` provide layouts, the time
panel, selectors, charts, and help icons. Planning KPI and Operate coverage
help appears on hover or keyboard focus. The local Geist font and these assets
are included in the installed package through `pyproject.toml`.

## Scenario bundles and errors

An optional `dashboard_scenarios.json` selects paired exports. Startup validates
common nodes, coordinates, map connections and time axes. Technology sets and
carrier definitions may differ between investment scenarios; the Carrier selector
updates to the chosen scenario and preserves its value only when available. Callbacks
use the selected scenario/carrier bundle; selection does not mutate a global
active scenario. Export files are read at startup, so restart after replacing them.

`data_errors.py` logs callback failures, clears affected figures/tables/maps, and
sets the shared error banner. Its Operate hint is a possible cause, not proof
that optimisation was skipped. The banner and message clear on tab changes.

`costs_view.py` and its callbacks remain available, but `layout_cost_ledger()` is
commented out in the Planning layout at the user's request. No custom CSV export
workflow is required. See the [current checkpoint](../docs/dashboard-progress-2026-11-07.md).

## Inputs corner cases

An absent local demand technology displays explicit zero fixed demand; a defined
technology without a fixed profile displays “Not specified”. Defined zero
profiles remain visible. Partial profile gaps remain gaps and make the selected
demand total incomplete; missing values outside the selected window do not
block valid data. Unbounded supply limits retain cost information without an
infinite graph. Conversion cards use both input and output carriers, and storage
separates flow-capacity cost (EUR/kW) from storage-capacity cost (EUR/kWh).
