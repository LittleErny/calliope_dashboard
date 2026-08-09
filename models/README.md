# Models

Each dashboard model folder contains two solved Calliope 0.7 files:

- `planning.nc`: planning inputs, results, and metadata;
- `operate.nc`: operate inputs, results, and metadata.

The default `0.7_national_scale` folder uses Calliope's built-in example and
includes a small generator script. Run it through the project environment:

```bash
make generate
```

For another model, add a folder with a similarly simple generator that calls
`model.build()`, `model.solve()`, checks for an optimal termination condition,
and calls `model.to_netcdf(...)` for both modes.

Set `CALLIOPE_DASHBOARD_MODEL_DIR` to the new folder when running the app. The
dashboard never reads model YAML or CSV files directly.

`mainkofen_case_study` is the original Calliope 0.6 model and is retained as
historical project material. Its pickle files are used by the stable 0.6 branch,
not by this branch.
