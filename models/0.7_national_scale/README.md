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
make generate
```

The files use Calliope 0.7's native NetCDF format and contain the `inputs`,
`results`, and `attrs` groups.
