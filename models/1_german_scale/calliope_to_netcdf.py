"""Generate Calliope 0.7 German-scale dashboard fixtures."""

from pathlib import Path

import calliope
import pandas as pd


MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / "model.yaml"
PLANNING_PATH = MODEL_DIR / "planning.nc"
OPERATE_PATH = MODEL_DIR / "operate.nc"

NODE_TECHS = {
    "Berlin": ("pv", "wind"),
    "Hamburg": ("pv", "wind", "hydro"),
    "Munich": ("pv", "hydro"),
    "Cologne": ("pv", "wind"),
    "Frankfurt": ("pv",),
    "Leipzig": ("pv", "wind"),
    "Hannover": ("pv", "wind"),
    "Nuremberg": ("pv", "hydro"),
}


def load_timeseries() -> pd.DataFrame:
    """Return the v0.7 data table assembled from the existing city CSVs."""
    series = {}
    for node, supply_techs in NODE_TECHS.items():
        city_data = pd.read_csv(
            MODEL_DIR / "timeseries_data" / f"{node}_timeseries.csv",
            index_col="time",
            parse_dates=True,
        )
        for tech in supply_techs:
            series[(node, tech, "source_use_max")] = city_data[tech]
        # Calliope 0.7 represents demand as positive sink use.
        series[(node, "demand", "sink_use_equals")] = -city_data["demand"]

    table = pd.DataFrame(series)
    table.index.name = "timesteps"
    table.columns = pd.MultiIndex.from_tuples(
        table.columns, names=["nodes", "techs", "parameters"]
    )
    return table


def load_model(scenario: str | None = None):
    return calliope.read_yaml(
        MODEL_PATH,
        scenario=scenario,
        data_table_dfs={"german_timeseries": load_timeseries()},
    )


def solve_and_save(model, output_path: Path) -> None:
    model.build()
    model.solve()
    if model.runtime.termination_condition != "optimal":
        raise RuntimeError(
            f"Model did not solve to optimality: {model.runtime.termination_condition}"
        )
    model.to_netcdf(output_path)
    print(f"Wrote {output_path.name}")


def main() -> None:
    if calliope.__version__ != "0.7.0.dev7":
        raise RuntimeError(f"Expected Calliope 0.7.0.dev7, found {calliope.__version__}")

    solve_and_save(load_model(), PLANNING_PATH)
    solve_and_save(load_model(scenario="operate_fixed"), OPERATE_PATH)


if __name__ == "__main__":
    main()
