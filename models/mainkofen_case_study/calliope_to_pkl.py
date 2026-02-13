from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

# Script-local configuration (edit if needed).
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "biomass_model.yaml"
INPUTS_PKL = BASE_DIR / "mainkofen_model_inputs.pkl"
RESULTS_PKL = BASE_DIR / "mainkofen_model_results_planning.pkl"
RESULTS_OPERATE_PKL = BASE_DIR / "mainkofen_model_results_operate.pkl"

def _split_loc_tech(loc_tech: str) -> Tuple[str, str]:
    if "::" not in loc_tech:
        return loc_tech, loc_tech
    return tuple(loc_tech.split("::", 1))  # type: ignore[return-value]


def _build_operate_overrides(model) -> Dict:
    overrides: Dict = {"locations": {}}
    if "energy_cap" in model.results and "energy_prod" in model.inputs:
        energy_cap = model.results["energy_cap"]
        energy_prod = model.inputs["energy_prod"]
        for loc_tech in energy_cap.coords["loc_techs"].values:
            cap = energy_cap.sel(loc_techs=loc_tech).item()
            prod_flag = energy_prod.sel(loc_techs=loc_tech).item()
            if not np.isfinite(prod_flag):
                continue
            if not np.isfinite(cap):
                continue
            loc, tech = _split_loc_tech(str(loc_tech))
            constraints = (
                overrides.setdefault("locations", {})
                .setdefault(loc, {})
                .setdefault("techs", {})
                .setdefault(tech, {})
                .setdefault("constraints", {})
            )
            constraints["energy_cap_equals"] = float(cap)

    if "storage_cap" in model.results:
        storage_cap = model.results["storage_cap"]
        dim = "loc_techs_store" if "loc_techs_store" in storage_cap.dims else "loc_techs"
        for loc_tech in storage_cap.coords[dim].values:
            cap = storage_cap.sel({dim: loc_tech}).item()
            if not np.isfinite(cap):
                continue
            loc, tech = _split_loc_tech(str(loc_tech))
            constraints = (
                overrides.setdefault("locations", {})
                .setdefault(loc, {})
                .setdefault("techs", {})
                .setdefault(tech, {})
                .setdefault("constraints", {})
            )
            constraints["storage_cap_equals"] = float(cap)

    if not overrides.get("locations"):
        return {}
    return overrides


def main() -> int:
    if not MODEL_PATH.exists():
        print(f"Model file not found: {MODEL_PATH}", file=sys.stderr)
        return 1

    try:
        import calliope  # type: ignore
    except ImportError:
        print("Calliope is not installed. Install it before running this script.", file=sys.stderr)
        return 1

    model = calliope.Model(str(MODEL_PATH))
    model.run()

    INPUTS_PKL.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PKL.parent.mkdir(parents=True, exist_ok=True)

    with open(INPUTS_PKL, "wb") as f:
        pickle.dump(model.inputs, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(RESULTS_PKL, "wb") as f:
        pickle.dump(model.results, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"Saved inputs to: {INPUTS_PKL}")
    print(f"Saved results to: {RESULTS_PKL}")

    operate_overrides = _build_operate_overrides(model)
    if operate_overrides:
        operate_model = calliope.Model(
            str(MODEL_PATH), scenario="operate_fixed", override_dict=operate_overrides
        )
        print("Operate overrides applied from planning results.")
    else:
        operate_model = calliope.Model(str(MODEL_PATH), scenario="operate_fixed")
        print("Operate overrides not applied (no capacity data found).")
    operate_model.run()

    with open(RESULTS_OPERATE_PKL, "wb") as f:
        pickle.dump(operate_model.results, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"Saved operate results to: {RESULTS_OPERATE_PKL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
