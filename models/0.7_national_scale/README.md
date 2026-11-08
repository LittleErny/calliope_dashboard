# Calliope 0.7 example data

This directory contains the dashboard fixture for the Calliope 0.7 branch.
It uses Calliope's built-in `national_scale` example, so the source model is
versioned together with Calliope itself instead of being copied into this
repository.

The dashboard reads two generated files:

- `planning.nc` contains the normal planning-mode solution.
- `operate.nc` contains the operate-mode solution.

Regenerate both files after changing Calliope or the example model:

```bash
conda run -n calliope-dashboard-070 python models/0.7_national_scale/calliope_to_netcdf.py
```

The files use Calliope 0.7's native NetCDF format and contain the `inputs`,
`results`, and `attrs` groups.

`make generate` at repository root targets the German example instead.
To view this model, pass `--model-dir models/0.7_national_scale` to the dashboard.
The exact national example inputs and horizon come from the imported Calliope
checkout, so record its source path/commit when regenerating these fixtures.
The current multi-scenario/carrier regression audit targets the German example;
see the [checkpoint](../../docs/dashboard-progress-2026-11-07.md).
