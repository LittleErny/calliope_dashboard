"""Select carrier-compatible technologies before aggregating costs/capacities."""

import xarray as xr


def cost_scope(inputs):
    """One exact accounting bucket per node/technology, never a guessed split."""
    matrix = inputs.definition_matrix.astype(bool)
    count = matrix.sum("carriers")
    scope = xr.full_like(count, "Unassigned", dtype=object)
    for carrier in inputs.carriers.values:
        scope = xr.where((count == 1) & matrix.sel(carriers=carrier), str(carrier), scope)
    return xr.where(count > 1, "Shared", scope)


def select_carrier(inputs, results, carrier):
    active = inputs.definition_matrix.sel(carriers=carrier).astype(bool).any("nodes")
    techs = inputs.techs.where(active, drop=True).values
    selected = results.sel(carriers=[carrier], techs=techs).copy()
    # Keep shared technology flows and capacities in both physical views. Its
    # undivided costs live exclusively in the whole-model cost ledger.
    exclusive = cost_scope(inputs).sel(techs=techs) == carrier
    for name, array in selected.data_vars.items():
        if name.startswith("cost") and {"nodes", "techs"}.issubset(array.dims):
            selected[name] = array.where(exclusive, 0.0)
    selected.attrs["cost_scope"] = "exclusive carrier costs; Shared costs excluded"
    return inputs.sel(carriers=[carrier], techs=techs), selected
