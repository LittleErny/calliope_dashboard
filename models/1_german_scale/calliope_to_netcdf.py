"""Generate Calliope 0.7 German-scale dashboard fixtures."""

from pathlib import Path
import json

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


def load_timeseries(demand_multiplier: float = 1.0) -> pd.DataFrame:
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
        series[(node, "demand", "sink_use_equals")] = -city_data["demand"] * demand_multiplier
        # Illustrative summer heat demand; this is not calibrated heating data.
        series[(node, "heat_demand", "sink_use_equals")] = -city_data["demand"] * 0.35 * demand_multiplier
        series[(node, "solar_thermal", "source_use_max")] = city_data["pv"]

    table = pd.DataFrame(series)
    table.index.name = "timesteps"
    table.columns = pd.MultiIndex.from_tuples(
        table.columns, names=["nodes", "techs", "inputs"]
    )
    return table


def load_model(scenario: str | None = None):
    return calliope.read_yaml(
        MODEL_PATH,
        scenario=scenario,
        data_table_dfs={
            "german_timeseries": load_timeseries(),
            "german_high_demand_timeseries": load_timeseries(1.2),
        },
    )


def solve_and_save(model, output_path: Path, scenario_id: str = "default") -> None:
    model.build()
    model.solve()
    if model.runtime.termination_condition != "optimal":
        raise RuntimeError(
            f"Model did not solve to optimality: {model.runtime.termination_condition}"
        )
    model.results.attrs["scenario_id"] = scenario_id
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.to_netcdf(output_path)
    print(f"Wrote {output_path}", flush=True)


def main() -> None:
    if calliope.__version__ != "0.7.0.dev7":
        raise RuntimeError(f"Expected Calliope 0.7.0.dev7, found {calliope.__version__}")

    solve_and_save(load_model(), PLANNING_PATH)
    solve_and_save(load_model(scenario="operate_fixed"), OPERATE_PATH)
    stress_dir = MODEL_DIR / "scenarios" / "high_demand"
    solve_and_save(load_model("high_demand"), stress_dir / "planning.nc", "high_demand")
    solve_and_save(load_model("operate_fixed,high_demand"), stress_dir / "operate.nc", "high_demand")
    (MODEL_DIR / "dashboard_scenarios.json").write_text(json.dumps({
        "default": "default",
        "scenarios": [
            {"id": "default", "label": "Baseline", "planning": "planning.nc", "operate": "operate.nc"},
            {"id": "high_demand", "label": "High demand (+20%)", "planning": "scenarios/high_demand/planning.nc", "operate": "scenarios/high_demand/operate.nc"},
        ],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
