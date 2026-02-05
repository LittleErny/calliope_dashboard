# Parsing and Visualizing a Calliope based Economic Dispatch Energy Model

This project provides a Dash-based dashboard for visualizing the input and output of Calliope models. It is designed to load Calliope model, save the model information produced from a single model run (inputs, planning results, operate results) to .pkl files, and expose them through interactive maps and charts using Dash.

## Repository Layout

- `app/` Dash application (layouts, callbacks, data loading).
- `helpers/` Python helpers that extract and organize data from Calliope xarray datasets.
- `models/` Model folders and utilities to generate pickle outputs.

## Quick Start

1. Make sure you have Python 3.9+ installed.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Point the app to your pickle files in `app/app_data.py`. (German Scale model by default)
4. Run the dashboard:

```bash
python app/app.py
```

## Notes

- The project assumes Calliope version 0.6.10 for models.
- Calliope is only required for generating the pickle files. The dashboard itself reads the pickle outputs only, not
requiring running the model again.
- Current project's main focus is visualization and interaction with optimization and simulation results, not creating 
or configuring the models themselves.
