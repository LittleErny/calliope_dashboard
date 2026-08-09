from __future__ import annotations

import shutil
from pathlib import Path

import calliope
from pyomo.environ import SolverFactory


def main() -> int:
    assert calliope.__version__ == "0.6.10"
    assert shutil.which("cbc") is not None, "CBC executable was not found"
    assert SolverFactory("cbc").available(), "Pyomo cannot use CBC"

    project_root = Path(__file__).resolve().parents[1]
    model_path = project_root / "models" / "1_german_scale" / "model.yaml"
    model = calliope.Model(
        str(model_path),
        override_dict={"model.subset_time": ["2025-07-01", "2025-07-01 23:00"]},
    )
    model.run()

    assert model.results.attrs["termination_condition"] == "optimal"
    assert model.results.sizes["timesteps"] == 24

    print(f"Calliope: {calliope.__version__}")
    print(f"CBC: {shutil.which('cbc')}")
    print("Model smoke test: optimal (24 timesteps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
