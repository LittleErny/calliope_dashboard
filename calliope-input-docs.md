# Calliope 0.7 `Model.inputs`

`Model.inputs` is an xarray Dataset produced after Calliope has parsed and
validated the model definition. The dashboard reads this processed structure
instead of parsing YAML itself.

## Main dimensions

- `nodes`: model locations.
- `techs`: technology identifiers.
- `carriers`: energy carriers.
- `timesteps`: model timestamps.
- `costs`: monetary or environmental cost classes.

This is the main schema change from 0.6: node, technology, and carrier are
separate dimensions instead of strings such as `node::tech::carrier`.

## Variables used by the dashboard

| Calliope 0.7 variable | Meaning | Dashboard use |
| --- | --- | --- |
| `definition_matrix` | valid node/tech/carrier combinations | topology and filters |
| `latitude`, `longitude` | node coordinates | maps |
| `base_tech` | supply, demand, storage, conversion, transmission | technology grouping |
| `name`, `color` | display metadata by technology | labels and chart colors |
| `carrier_in`, `carrier_out` | input and output carriers | conversion and flow direction |
| `flow_cap_max` | maximum flow capacity | input cards and line limits |
| `storage_cap_max` | maximum storage energy | storage cards |
| `flow_out_eff`, `flow_in_eff` | flow efficiency | input details |
| `source_use_max` | supply resource profile | maximum supply chart |
| `sink_use_equals` | fixed demand profile | demand chart |
| `lifetime` | technology lifetime | input details |
| `cost_flow_cap` | capacity investment parameter | cost details |
| `cost_flow_in`, `cost_flow_out` | variable flow cost parameters | cost details |
| `distance` | transmission distance | link metadata |
| `timestep_resolution`, `timestep_weights` | time representation | aggregation context |

Not every variable exists for every model or technology. Helpers return an
empty collection or `NaN` for optional values instead of assuming that a model
defines all possible constraints.

## Operate inputs

Operate mode keeps fixed capacities in its inputs. The dashboard reads
`flow_cap` and `storage_cap` from the operate NetCDF `inputs` group because
those arrays are not repeated in operate `results`.
