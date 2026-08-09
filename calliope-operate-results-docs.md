# Calliope 0.7 operate results

Operate results are stored in the `results` group of `operate.nc`. The default
fixture covers 240 hourly timesteps.

| Variable | Meaning | Dashboard use |
| --- | --- | --- |
| `flow_out` | technology output at each timestep | generation and delivered line flow |
| `flow_in` | technology input at each timestep | demand, charging, and conversion input |
| `storage` | storage state of charge | storage charts |
| `unmet_demand` | unmet load | critical/timestep map modes |
| `cost_operation_variable` | variable operating cost | location KPIs |

Fixed `flow_cap` and `storage_cap` are read from the same file's `inputs`
group. Calliope does not repeat those fixed operate parameters in `results`.

## Transmission direction

Calliope 0.7 represents one physical transmission technology at both connected
nodes. The helper exposes two directed `LineRef` objects for the UI. For a
direction A to B, delivered flow is `flow_out` at B for that transmission tech.
This preserves the dashboard's existing directional arrows while respecting
the 0.7 link schema.
