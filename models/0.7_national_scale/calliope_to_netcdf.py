"""Generate the Calliope 0.7 dashboard fixtures."""

from pathlib import Path

import calliope


MODEL_DIR = Path(__file__).resolve().parent
PLANNING_PATH = MODEL_DIR / "planning.nc"
OPERATE_PATH = MODEL_DIR / "operate.nc"


def solve_and_save(model, output_path: Path) -> None:
    """Build, solve, and save one Calliope model."""
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

    solve_and_save(calliope.examples.national_scale(), PLANNING_PATH)
    solve_and_save(calliope.examples.national_scale(scenario="operate"), OPERATE_PATH)


if __name__ == "__main__":
    main()
