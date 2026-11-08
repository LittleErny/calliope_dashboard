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

## Accounting and time invariants

`carriers.py` classifies each enabled node/technology as one carrier or Shared.
Shared technology flows stay selectable in each applicable carrier; undivided
costs are zeroed in carrier-exclusive views and retained once in the raw ledger.
`costs.py` reconciles every enabled node/technology/cost class against raw `cost`,
retains negative values, and separates upfront CAPEX from annualised investment.
The ledger's UI is currently hidden, not its underlying accounting checks.

Energy and variable-cost arrays are summed over the selected original timesteps.
Fixed/annualised cost allocation uses represented hours (duration × weight).
Input availability applies source units, capacity/area bounds and efficiencies.
Generation/storage capacity excludes demand sinks and transmission; production
excludes transmission and includes storage discharge, so it is gross output.

Operate loading uses sending-end power divided by solved/fixed line capacity;
delivered energy is measured at the receiving end. Charge/discharge aggregation
preserves energy totals; SOC is a state with end/min/max values, not an energy
sum. Optional omitted unmet-demand slack is zero; unexpected required-data
failures raise `DataUnavailable` through `errors.py`, rather than becoming zeros.
