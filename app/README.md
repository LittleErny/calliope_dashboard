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

The default folder is `models/1_german_scale`. Override it without editing
Python source:

```bash
CALLIOPE_DASHBOARD_MODEL_DIR=/absolute/path/to/model \
conda run -n calliope-dashboard-070 python app/app.py
```

The folder must contain `planning.nc` and `operate.nc`. Both files must have
Calliope's `inputs`, `results`, and `attrs` groups and must describe compatible
locations, technologies, and carriers.

## Tabs

- Inputs shows topology, demand profiles, supply limits, and input parameters.
- Planning shows capacity, costs, production, emissions, and detail tables.
- Operate shows unmet demand, line loading, flows, and storage operation.

The global scenario, carrier, and time controls are shared by all three tabs.
Labels assume kW for flow capacity, kWh for energy, EUR for monetary cost, and
kg for a cost class named `co2`.
