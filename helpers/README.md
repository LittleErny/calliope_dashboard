# Helpers

This folder contains helper classes that expose a stable, readable API for Calliope xarray datasets.

## Files

- `helpers/inputs_helper.py` Accessors for `Model.inputs`.
- `helpers/results_helper.py` Accessors for planning `Model.results`.
- `helpers/operate_results_helper.py` Accessors for operate `Model.results`.

## Responsibilities

- Normalize dataset structures and provide safe access patterns.
- Convert Calliope indices into convenient Python structures.
- Provide domain-specific aggregates used by the dashboard.

## Assumptions

- Datasets come from Calliope 0.6.10.
- Inputs and results are aligned and originate from the same model configuration.
