# App

This folder contains the Dash application that visualizes Calliope inputs and results. The app does not generate data.
It only loads pickle files and renders interactive maps and charts.

## Structure

- `app/app.py` Application entry point.
- `app/app_data.py` Loads pickle files and exposes derived data for callbacks and layouts.
- `app/figures.py` Shared figure helpers and formatting utilities.
- `app/layouts/` Layout definitions for the Inputs, Planning, and Operate tabs.
- `app/callbacks/` Dash callbacks for interactivity and data binding.

## Configuration

Update the following paths in `app/app_data.py` to point to your model outputs:

- `INPUTS_PATH`
- `PLANNING_RESULTS_PATH`
- `OPERATE_RESULTS_PATH`

All three files must be from the same model to ensure consistent locations, carriers, and timesteps.

## App layout and functionality:

### Global Controls

This part is available in any of the 3 tabs:

- Scenario selector: chooses the scenario from the planning results.
- Carrier selector: filters charts and operating metrics by carrier.
- Time window slider: defines the global time range used by all charts and maps.

### Inputs Tab

Purpose: visualize the model topology and input data before any optimization.

Map:
- Location markers: one per location.
- Transmission lines: red polylines between connected locations.
- Direction arrowheads: scaled by zoom level for consistent on-screen size.
- Centering: the map center is computed from the average of all location coordinates.

Info panel behavior:
- Click a location to view location area and technology details.
- Click a line to view transmission capacity.

Charts and cards:
- Demand time series for the selected location and carrier.
  - Goal: show the magnitude and temporal profile of demand.
- Supply potential time series per technology.
  - Goal: show the maximum available supply by tech over time.
- Technology details list.
  - Goal: expose key constraints and cost parameters from inputs.

Note: this tab functionality is quite repeated by Ricardo's project, so using his project for model configuration is advised.


### Results: Planning Tab

Purpose: summarize optimized planning results at the asset level and over time.

KPI strip:
- CAPEX, OPEX, installed capacity, production, CO2.
- Goal: give a quick, comparable snapshot for the current selection and time window.

Installed capacity bar chart:
- Grouped by technology or by location (controlled by the View mode).
- Goal: show where and which technologies were built.

Cost breakdown bar chart:
- Stacked CAPEX, fixed OPEX, variable OPEX.
- Optional normalization per kW.
- Goal: show cost structure by group.

CO2 breakdown bar chart:
- Total emissions by group for the selected window.
- Goal: show the major contributors to emissions.

Production over time:
- Line chart grouped by top technologies (others collapsed into “Other”).
- Optional demand overlay as a dashed red line.
- Goal: show production dynamics and compare to demand.

CO2 over time:
- Line chart grouped by top technologies (others collapsed into “Other”).
- Goal: show emission dynamics over time.

Details table:
- Capacity, CAPEX, fixed/variable OPEX, CO2, production, capacity factor.
- Goal: provide a precise, exportable summary of the current selection.

Coloring:
- Technology colors are taken from Calliope inputs if present.
- Missing tech colors receive deterministic category-based colors.

### Results: Operate Tab

Purpose: analyze operational performance over the selected time window.

Map modes:
- Timestep: displays the current timestep state.
- Critical: displays worst-case values within the selected time window.

Location markers:
- Color encodes unmet demand fraction.
- Gradient: green (0%) → dark red (10%) → red (100%).
- Goal: quickly locate stress points in the system.

Unmet demand gradient reference:

![Unmet demand gradient](../gradient_unmet_demand_ramp.jpeg)

Transmission lines:
- Color encodes line load fraction.
- Gradient: green (low) → yellow (medium) → red (high).
- Line width encodes installed capacity.
- Arrowheads indicate flow direction.
- Goal: communicate congestion and flow direction at a glance.

Line load gradient reference:

![Line load gradient](../gradient_load_ramp.jpeg)

Line details (on click):
- Flow time series for both directions.
- Dashed capacity reference line.
- Summary: max capacity, peak flow, total flow.

Location details (on click):
- Summary: total demand, total production, unmet demand, unmet share, variable OPEX.
- Demand coverage chart: stacked bars by technology plus unmet demand.
- Storage cards: SOC or charge/discharge view with summary statistics.

### Notes

- All charts and maps are driven exclusively by the three pickle files configured in `app/app_data.py`.
- If the pickle files do not originate from the same model configuration, indices may not align and the dashboard will be incorrect.
- Units are hardcoded in labels: kWh for energy, kW for capacity, EUR for costs, kg for CO2.
- Demand values in Calliope can be negative; the dashboard displays demand as absolute values.
- The global time window affects all charts and the Operate tab “critical” mode calculations.
- Large models can slow down map rendering due to many markers, lines, and arrows.
