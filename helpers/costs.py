"""A raw, unweighted ledger for every Calliope cost class and technology."""

import numpy as np
import pandas as pd

from helpers.carriers import cost_scope
from helpers.errors import fail


VARIABLES = {
    "model_total": "cost",
    "capex": "cost_investment",
    "investment": "cost_investment_annualised",
    "fixed": "cost_operation_fixed",
    "variable": "cost_operation_variable",
}


def cost_ledger(inputs, results, start, end):
    """Costs for the full horizon and selected window, without currency guesses.

    The `cost` result is authoritative. Missing components stay unavailable;
    residuals expose costs outside the supplied breakdown. CAPEX is kept
    separate and is never added to annualised investment a second time.
    """
    if "cost" not in results or "costs" not in results.coords:
        fail("Cost results are unavailable: the export has no cost / costs array.")
    index = pd.DatetimeIndex(results.timesteps.values)
    duration = inputs.timestep_resolution.to_series().reindex(index)
    weights = inputs.timestep_weights.to_series().reindex(index) if "timestep_weights" in inputs else 1.0
    represented = duration * weights
    fraction = float(represented.loc[start:end].sum() / represented.sum())
    scopes = cost_scope(inputs)
    enabled = inputs.definition_matrix.astype(bool).any("carriers").to_series()
    tables = {}
    for key, name in VARIABLES.items():
        if name not in results:
            continue
        array = results[name]
        if not {"nodes", "techs", "costs"}.issubset(array.dims):
            fail(f"Cannot account for {name}: expected nodes, techs and costs dimensions.")
        if bool(np.isinf(array).any()):
            fail(f"Invalid infinite values in {name}.")
        full = array.sum("timesteps", skipna=True) if "timesteps" in array.dims else array
        window = array.sel(timesteps=slice(start, end)).sum("timesteps", skipna=True) if "timesteps" in array.dims else array
        tables[key] = (full, window)

    rows = []
    for (node, tech), active in enabled.items():
        if not active:
            continue
        for cls in results.costs.values:
            row = {"location": str(node), "technology": str(tech), "cost_class": str(cls),
                   "scope": str(scopes.sel(nodes=node, techs=tech).item())}
            for key in VARIABLES:
                pair = tables.get(key)
                if pair is None:
                    row[key] = row[f"window_{key}"] = None
                    continue
                full, window = [float(a.sel(nodes=node, techs=tech, costs=cls).fillna(0).sum()) for a in pair]
                row[key] = full
                row[f"window_{key}"] = window if key == "variable" else full if key == "capex" else full * fraction
            components = [row[k] for k in ("investment", "fixed", "variable")]
            row["residual"] = row["model_total"] - sum(v for v in components if v is not None)
            parts = [row[f"window_{k}"] for k in ("investment", "fixed", "variable")]
            row["window_total"] = (sum(v for v in parts if v is not None) + row["residual"] * fraction
                                   if row["variable"] is not None else None)
            rows.append(row)
    frame = pd.DataFrame(rows)
    # Account for every raw result, including accidental nonzero costs on
    # undefined pairs. Failing visibly is safer than quietly losing them.
    for cls in results.costs.values:
        raw = float(results.cost.sel(costs=cls).fillna(0).sum())
        shown = frame.loc[frame.cost_class == str(cls), "model_total"].sum()
        if not np.isclose(raw, shown, rtol=1e-10, atol=1e-6):
            fail(f"Cost reconciliation failed for {cls}: ledger {shown}, NetCDF {raw}.")
    return frame
