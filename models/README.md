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
0.7/Pareto branch. It remains available in the `stable/calliope-0.6.10` branch
and the `internship-original` tag.
