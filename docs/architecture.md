# Dashboard architecture

## Data flow

The application keeps the original three-layer structure:

1. `models/1_german_scale/calliope_to_netcdf.py` solves planning and
   operate models and writes NetCDF files.
2. `helpers/` translates Calliope arrays into the small Python and pandas
   structures expected by the dashboard.
3. `app/` renders maps, charts, cards, and tables with Dash.

Dash callbacks do not run an optimisation. They only read the datasets loaded
at application startup.

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

`app/app_data.py` reads `CALLIOPE_DASHBOARD_MODEL_DIR`. The default is
`models/1_german_scale`. A custom directory must contain both
`planning.nc` and `operate.nc` produced by the same Calliope model family.

The helper classes are the version boundary. Code in layouts and callbacks
should call helper methods instead of reading xarray variables directly.
