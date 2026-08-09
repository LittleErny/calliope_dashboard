from __future__ import annotations

import shutil

import calliope
from pyomo.environ import SolverFactory


def main() -> int:
    assert calliope.__version__ == "0.7.0.dev7"
    assert shutil.which("cbc") is not None, "CBC executable was not found"
    assert SolverFactory("cbc").available(), "Pyomo cannot use CBC"

    model = calliope.examples.national_scale(
        override_dict={"config.init.subset.timesteps": ["2005-01-01", "2005-01-01 23:00"]}
    )
    model.build()
    model.solve()

    assert model.runtime.termination_condition == "optimal"
    assert model.results.sizes["timesteps"] == 24

    print(f"Calliope: {calliope.__version__}")
    print(f"CBC: {shutil.which('cbc')}")
    print("Model smoke test: optimal (24 timesteps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
