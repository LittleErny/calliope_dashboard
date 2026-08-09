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
class display zero/empty CO2 components.

Transmission technology values are excluded from local generation and asset
charts. They are visualized separately as map links.
