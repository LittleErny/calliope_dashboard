# Dashboard architecture

## Data flow

The dashboard has three layers:

1. `models/*/calliope_to_pkl.py` runs Calliope and stores xarray datasets.
2. `helpers/` extracts locations, technologies, carriers, costs, and timeseries from those datasets.
3. `app/` renders the extracted data with Dash, Plotly, and Dash Leaflet.

The Dash callbacks do not run an optimisation model. They only call helper methods and build figures.

## Saved datasets

The 0.6.10 dashboard uses three pickle files:

- inputs from `model.inputs`;
- planning results from `model.results`;
- operate results from a second model run.

Pickle files must only be loaded from a trusted source. Pickle is also sensitive to Python and xarray version
changes, which is why the dashboard environment pins its scientific dependencies.

## Configuration

`app/app_data.py` loads a model folder when the application starts. The default folder is
`models/mainkofen_case_study`.

Set `CALLIOPE_DASHBOARD_MODEL_DIR` to use another absolute model folder. Keeping this setting outside the Python
source avoids editing `app_data.py` for every model.

## Version boundary

The helper classes are the compatibility boundary between Calliope and the Dash application. Code in layouts and
callbacks should use helper methods instead of reading Calliope arrays directly.

Calliope 0.7 uses a different set of dimensions and variables. Its implementation lives on the
`migration/calliope-0.7.0-dev7` branch and keeps the same layout and callback structure where practical.
