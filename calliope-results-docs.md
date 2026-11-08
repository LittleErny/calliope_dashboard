# Calliope 0.7 planning results

Planning results are stored in the `results` group of `planning.nc`. Arrays use
the same separate `nodes`, `techs`, `carriers`, `timesteps`, and `costs`
dimensions as the inputs.

| Variable | Meaning | Dashboard use |
| --- | --- | --- |
| `flow_cap` | optimised flow capacity | installed-capacity charts and KPIs |
| `flow_out` | carrier output by node and technology | production charts |
| `flow_in` | carrier input by node and technology | demand and conversion consumption |
| `storage`, `storage_cap` | state of charge and built energy capacity | storage data |
| `unmet_demand` | unmet load by node, carrier, and time | reliability data |
| `cost_operation_variable` | variable cost by tech and timestep | OPEX |
| `cost_investment` | non-annualised investment cost | CAPEX |
| `cost_investment_annualised` | annualised investment contribution | cost separation |
| `cost` | total objective cost contribution | cost separation |
| `capacity_factor` | flow divided by installed capacity | result context |

If the `costs` coordinate contains `co2`, the dashboard treats that slice of
`cost_operation_variable` as emissions. Models with only a `monetary` cost
class display CO2 as unavailable; an absent class is not evidence of zero emissions.

Transmission technology values are excluded from local generation and asset
charts. They are visualized separately as map links.

## Planning numbers and accounting scope

For the selected scenario, carrier, locations/technology and applied interval:

- Installed power sums relevant supply/conversion/storage `flow_cap`, excluding
  demand sinks and transmission. This is power, not stored energy capacity.
- Production sums `flow_out` excluding transmission and including storage
  discharge. It is gross output and can count energy that was previously charged.
- CAPEX is the full upfront `cost_investment`; it is not prorated with the window.
- Modeled cost combines annualised investment, fixed/other costs prorated by the
  selected share of represented hours, and actual selected variable costs.
- OPEX contains allocated fixed operating costs and selected variable costs.
  CAPEX must not be added to modeled cost, which already includes annualisation.
- CO2 combines allocated annualised investment emissions and selected operational
  emissions only when the `co2` cost class is supplied; it is not a weighted sum
  with monetary cost. Capacity factor uses selected output / (power × window hours).

Represented hours for fixed-cost allocation are `timestep_resolution *
timestep_weights`. Components supplied without timestamps are allocated estimates;
variable-cost and energy arrays retain their selected timestep totals.

Each enabled node/technology has one cost scope: a single carrier or Shared.
Shared costs are excluded from carrier-exclusive KPIs, charts and detail tables,
while applicable flows/capacities remain. The raw ledger accounts for them once,
reconciles to `cost`, preserves negative/custom cost classes, and separates CAPEX
from annualised investment. Its whole-model table is currently hidden, so visible
carrier totals alone do not give the complete multi-carrier cost. Use raw
`results.cost.sel(costs=...).sum()` or the ledger for the whole-model total.

[Current checkpoint](docs/dashboard-progress-2026-11-07.md) and
[detailed accounting](docs/dashboard-costs-and-time-2026-11-03.md).
