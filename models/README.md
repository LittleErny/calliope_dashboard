# Models

Each subfolder in `models/` represents a complete Calliope model setup. The goal of a model folder is to contain everything required to run Calliope and produce the three pickle files used by the dashboard.

## Expected Structure

A typical model folder should contain:

- `model.yaml` Main Calliope model configuration.
- `model_config/techs.yaml` Technology definitions.
- `model_config/locations.yaml` Location and link definitions.
- `scenarios.yaml` Scenario overrides (must include the `operate_fixed` scenario).
- `timeseries_data/` CSV time series data referenced by the YAML files.
- `calliope_to_pkl.py` Script that runs Calliope and writes the pickle outputs.
- Output pickle files (inputs, planning results, operate results).

## Generating Pickle Files

From within a model folder, run:

```bash
python calliope_to_pkl.py
```

This script loads the model, runs 2 simulations in planning and operational modes, and generates three files:

- Inputs pickle (e.g. `german_model_inputs.pkl`)
- Planning results pickle (e.g. `german_model_results_planning.pkl`)
- Operate results pickle (e.g. `german_model_results_operate.pkl`)

## Using a Model in the App

After generating the pickle files, update the paths in `app/app_data.py` to point to the three outputs. The dashboard loads only these pickle files and does not read YAML or CSV files directly. If you update the model, do not forget to run calliope_to_pkl.py again.

## Notes

- Jupyter notebooks are not required for production usage.
- If you add a new model, place it in its own subfolder under `models/` and provide a `calliope_to_pkl.py` script with the same behavior.
- The dashboard labels assume kWh for energy, kW for capacity, EUR for costs, and kg for CO2. Ensure your model outputs use compatible units.
- Calliope is only required for generating pickle files. The dashboard itself reads the pickle outputs only.
