# Models

Each dashboard model folder contains two solved Calliope 0.7 files:

- `planning.nc`: planning inputs, results, and metadata;
- `operate.nc`: operate inputs, results, and metadata.

The default `1_german_scale` folder contains the fictional German-scale model
and its generator script. Run it through the project environment:

```bash
make generate
```

For another model, add a folder with a similarly simple generator that calls
`model.build()`, `model.solve()`, checks for an optimal termination condition,
and calls `model.to_netcdf(...)` for both modes.

Set `CALLIOPE_DASHBOARD_MODEL_DIR` to the new folder when running the app. The
dashboard never reads model YAML or CSV files directly.

The original Calliope 0.6 Mainkofen material is intentionally absent from this
0.7 branch. It remains available in the `stable/calliope-0.6.10` branch
and the `internship-original` tag.

## Current model families

`make generate` regenerates **only `1_german_scale`**, including its Baseline and
High demand pairs. Use the generator inside `0.7_national_scale` explicitly for
the built-in national model. The German source now requires the local fork's
`table` / `inputs` schema; see [environment setup](../docs/environments.md).

An optional `dashboard_scenarios.json` lists scenario IDs, labels, and relative
Planning/Operate paths. Shared controls require common nodes, coordinates, map connections and time axes.
Investment scenarios may enable different technologies and carriers. The Carrier
selector updates to each scenario; a stale unavailable carrier waits for the
selector update instead of being rendered as zero or mislabeled data.

Planning and Operate need not have the same capacity assumptions: the German
`operate_fixed` fleet is specified independently. In the separate THD heat-pump
workflow, Operate capacities were instead copied from the new Planning solution.
The dashboard only reads the exports and does not enforce a solve workflow.

A current THD heat-pump pair is maintained in the sibling model repository under
`scenario_results/dashboard_heat_pump_2026-11-07/`; pass its directory with
`--model-dir`. It is a separate Git repository and is not bundled here. Its
runner locally overrides Operate's missing `flow_cap` default to zero to avoid
invalid PV resource bounds; the dashboard does not apply that model-math workaround.
