# Helpers

Helpers are the compatibility boundary between Calliope 0.7 xarray datasets
and the existing dashboard callbacks.

- `inputs_helper.py` reads processed model inputs.
- `results_helper.py` builds planning aggregates and timeseries.
- `operate_results_helper.py` builds operate aggregates, storage series, and
  directed views of transmission links.

Calliope 0.7 uses separate `nodes`, `techs`, `carriers`, and `timesteps`
dimensions. Helpers select those dimensions directly and return regular lists,
dictionaries, pandas Series, or DataFrames. Layouts and callbacks should not
depend on raw Calliope variable names.

The old dashboard names such as `energy_cap_max` are retained only in returned
display dictionaries where callbacks already expect those keys. Internally they
map to Calliope 0.7 variables such as `flow_cap_max`.
