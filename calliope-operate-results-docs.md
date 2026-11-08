# Calliope 0.7 operate results

Operate results are stored in the `results` group of `operate.nc`. The default
German fixture covers 336 hourly timesteps (1–14 July 2025). The separately
exported THD heat-pump pair covers 8760 hourly timesteps in 2025.

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

Sending-end loading divides `flow_in` by the fixed/solved flow capacity and
`timestep_resolution`. A line energy series in kWh is divided by its timestep
hours before being labeled kW. Original peaks are retained when long series are
averaged for display. Arrowheads sit near the receiving marker and follow the
actual transmission direction; heat hides electricity-only links.

## Demand coverage and storage

Coverage allocates met demand proportionally between local output and incoming
flows at each original timestep, then sums the allocated energy into readable
calendar bins. It estimates contributions; it does not trace electricity origins.
Auto selects the smallest supported interval with at most 60 nonempty bars
(1/2/3/4/6/12 hours, day, Monday–Sunday week, month, quarter, year). Edge bins
contain only selected data. Hourly keeps all original steps, including sub-hourly
steps where applicable; it does not synthesize missing hours. The card supports
full screen and upper-right hover/focus help. Applied selection is capped at one
calendar year even for longer exports.

Storage charge/discharge bars sum energy. Aggregated SOC displays end-of-bin
state and original min/max rather than summing storage state. Variable OPEX is
read from `cost_operation_variable`; it excludes investment and follows the same
carrier-exclusive/Shared accounting as Planning.

## Genuine dispatch versus a copied solution

The German `operate_fixed` fleet is defined independently of Planning. The THD
annual runner fixes its fleet from Planning and solves rolling dispatch. The
single-solution Python API instead copies its supplied solution into
both export filenames and never performs an Operate optimisation. For genuine
separate results, supply the externally solved pair through `--model-dir`.

Unexpected failures clear affected outputs and show an error with an Operate
missing-run/export hint. Switching tabs clears the banner. Optional omitted
unmet-demand slack is a defined zero; an optimal solve with enabled slack can
still have unmet demand. See [current progress](docs/dashboard-progress-2026-11-07.md).
