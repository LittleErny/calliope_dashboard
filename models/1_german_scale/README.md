# Fictional Germany: electricity, heat and two demand scenarios

The Calliope 0.7 model has eight cities and two carriers:

- `electricity`: the original PV, wind, hydro, coal, gas, battery and transmission system;
- `heat`: local gas boilers, solar thermal collectors, and a heat-demand sink in every city.

The heat demand is an illustrative profile equal to **35% of each city's original
electricity demand**. Solar thermal uses that city's existing PV availability
profile and 90% parasitic efficiency. These assumptions exercise the dashboard;
they are not calibrated German heat-demand or solar-thermal measurements.
There are no intercity heat links, so the heat maps show nodes without the
electricity transmission lines. Batteries belong to electricity only.

## Scenarios

| Dashboard label | Calliope scenario | Description |
| --- | --- | --- |
| Baseline | base / `operate_fixed` | Original electricity demand plus illustrative heat demand |
| High demand (+20%) | `high_demand` / `operate_fixed,high_demand` | Both demand profiles multiplied by 1.2; resource availability unchanged |

`high_demand` is a native YAML override selecting the alternative time-series
table. Both tables are constructed deterministically from the original city
CSVs by `calliope_to_netcdf.py`. Planning chooses capacities; operate keeps the
scenario's fixed fleet and optimizes dispatch.

Regenerate all four solved exports:

```bash
conda run -n calliope-dashboard-070 python models/1_german_scale/calliope_to_netcdf.py
```

This writes the baseline `planning.nc` / `operate.nc`, the high-demand pair in
`scenarios/high_demand/`, and `dashboard_scenarios.json`. The dashboard reads the
manifest at startup and switches between preloaded bundles. A normal single
export without a manifest remains supported.

The Carrier selector scopes technologies, capacities, production, costs and CO2
to the selected carrier. In this model each technology belongs to exactly one
carrier, so electricity and heat costs/CO2 add up to the complete model totals.
The Scenario selector changes inputs and results in all three sections without
running another optimization or mutating another browser session's selection.

## Generation and interpretation

The source uses `table` and the `inputs` dimension from the newer Calliope fork,
not the older published Conda schema with the same `0.7.0.dev7` version string.
Install the fork before regeneration, following [environment setup](../../docs/environments.md).
The horizon is 1–14 July 2025 (336 hourly steps). The independently specified
`operate_fixed` fleet is not automatically copied from the Planning optimum.
Both modes permit unmet demand; optimal termination alone does not imply full
coverage. Neither the heat assumptions nor the scenarios are a real German
energy forecast.

Arrowheads are placed near receiving node markers and retain direction when
zoom changes. A year-long coverage check uses the separate annual THD export;
this German fixture only exercises its own two-week horizon. The current
[progress report](../../docs/dashboard-progress-2026-11-07.md) links the numerical
checks, time/coverage behavior, and temporarily hidden whole-model cost UI.
