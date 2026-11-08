"""Exact technology costs for multiobjective inspection."""

import numpy as np
from dash import Input, Output, State, dcc, html, dash_table
from dash.dash_table.Format import Format, Scheme, Group

from app import app_data
from helpers.costs import cost_ledger


def layout_cost_ledger():
    classes = [str(c) for c in app_data.LOADED_RESULTS.costs.values] if "costs" in app_data.LOADED_RESULTS.coords else []
    return html.Div([
        html.H4("All technology costs · whole model", style={"margin": "0 0 8px"}),
        html.P("Exact full-horizon costs across all carriers. Shared technologies are counted once. "
               "The carrier selector above filters physical charts; it does not hide rows here.", style={"fontSize": "12px"}),
        html.Div([
            html.Label(["Cost class", dcc.Dropdown(id="cost-ledger-class", options=classes,
                       value="monetary" if "monetary" in classes else next(iter(classes), None), clearable=False)]),
        ], className="cost-ledger-controls"),
        html.Div(id="cost-ledger-note", style={"fontSize": "12px", "margin": "8px 0"}),
        dash_table.DataTable(id="cost-ledger-table", columns=[], data=[], page_size=12,
                             sort_action="native", filter_action="native",
                             style_table={"overflowX": "auto"}, style_cell={"fontSize": "12px", "padding": "8px", "minWidth": "110px"},
                             style_header={"fontWeight": "700", "whiteSpace": "normal", "height": "auto"}),
        html.P("CAPEX is a separate investment amount; it is not added to annualised investment. "
               "Window costs prorate fixed components by represented hours and keep actual variable costs. "
               "Cost classes are shown separately, without objective weights or conversion to EUR. "
               "Blank components mean not separately exported; Other / unitemized reconciles the remaining cost.",
               style={"fontSize": "12px", "color": "#526475"}),
    ], className="cost-ledger-card")


def register_cost_callbacks(app):
    @app.callback(
        Output("cost-ledger-class", "options"), Output("cost-ledger-class", "value"),
        Input("dd-scenario", "value"), State("cost-ledger-class", "value"),
    )
    def update_cost_classes(scenario, current):
        raw = app_data.get_scenario(scenario).LOADED_RESULTS
        classes = [str(c) for c in raw.costs.values] if "costs" in raw.coords else []
        value = current if current in classes else "monetary" if "monetary" in classes else next(iter(classes), None)
        return [{"label": c, "value": c} for c in classes], value

    @app.callback(
        Output("cost-ledger-table", "columns"), Output("cost-ledger-table", "data"),
        Output("cost-ledger-note", "children"),
        Input("dd-scenario", "value"), Input("applied-time", "data"),
        Input("cost-ledger-class", "value"),
    )
    def update_cost_ledger(scenario, bounds, cost_class):
        bundle = app_data.get_scenario(scenario)
        start, end = bundle.TIME_INDEX[bounds[0]], bundle.TIME_INDEX[bounds[1]]
        frame = cost_ledger(bundle.LOADED_INPUTS, bundle.LOADED_RESULTS, start, end)
        frame = frame.loc[frame.cost_class == cost_class]
        keys = ["technology", "scope", "cost_class"]
        numeric = ["model_total", "investment", "fixed", "variable", "residual", "capex", "window_total"]
        frame = frame.groupby(keys, as_index=False, dropna=False)[numeric].sum(min_count=1)
        frame = frame.sort_values("model_total", ascending=False)
        columns = [{"name": k.replace("_", " ").title(), "id": k} for k in keys if k != "cost_class"]
        labels = {"model_total": "Modeled total · full horizon", "investment": "Annualised investment · full horizon",
                  "fixed": "Fixed OPEX · full horizon", "variable": "Variable OPEX · full horizon", "residual": "Other / unitemized · full horizon",
                  "capex": "CAPEX · separate investment", "window_total": "Selected window · fixed costs prorated"}
        columns += [{"name": labels[k], "id": k, "type": "numeric",
                     "format": Format(precision=6, scheme=Scheme.fixed, group=Group.yes)} for k in numeric]
        units = {"monetary": "EUR", "co2": "kg CO2"}.get(cost_class, f"model units · {cost_class}")
        total = frame.model_total.sum()
        shared = frame.loc[frame.scope == "Shared", "model_total"].sum()
        note = f"NetCDF total: {total:,.9f} {units}. Shared: {shared:,.9f}. Includes demand, transmission, storage, unused technologies and negative costs."
        rows = frame.replace({np.nan: None}).to_dict("records")
        return columns, rows, note
