from __future__ import annotations

from dash import ClientsideFunction, Input, Output, State, html

from app import app_data
from app.layouts.inputs import layout_inputs
from app.layouts.operate import layout_results_operate
from app.layouts.planning import layout_results_planning


def layout_for_tab(tab_value: str):
    """Build the page for a dashboard tab."""
    if tab_value == "inputs":
        return layout_inputs()
    if tab_value == "results_planning":
        return layout_results_planning()
    if tab_value == "results_operate":
        return layout_results_operate()
    return html.Div("Unknown mode")


def register_common_callbacks(app):
    @app.callback(
        Output("dd-carrier", "options"),
        Output("dd-carrier", "value"),
        Input("dd-scenario", "value"),
        State("dd-carrier", "value"),
    )
    def update_scenario_carriers(scenario, current):
        data = app_data.get_scenario(scenario)
        carriers = data.INPUT_HELPER.inputs.carriers.values.tolist()
        selected = current if current in carriers else (carriers[0] if carriers else None)
        return [{"label": carrier, "value": carrier} for carrier in carriers], selected

    app.clientside_callback(
        "function(n, tab){return [{display:'none'}, ''];}",
        Output("data-error-banner", "style"),
        Output("data-error-message", "children"),
        Input("dismiss-data-error", "n_clicks"),
        Input("tabs-mode", "value"),
        prevent_initial_call=True,
    )
    @app.callback(
        Output("page-content", "children"),
        Input("tabs-mode", "value"),
    )
    def render_page(tab_value: str):
        return layout_for_tab(tab_value)

    # Draft changes stay in the browser. Only Apply changes the store consumed
    # by the expensive charts and maps, including when another filter changes.
    app.clientside_callback(
        ClientsideFunction(namespace="timeWindow", function_name="edit"),
        Output("rs-time", "value"),
        Output("draft-time", "data"),
        Output("time-start-label", "children"),
        Output("time-end-label", "children"),
        Output("time-status", "children"),
        Output("apply-time", "disabled"),
        Output("time-start-input", "value"),
        Output("time-end-input", "value"),
        Output("time-validation", "children"),
        Output("time-status", "title"),
        Input("rs-time", "value"),
        Input("applied-time", "data"),
        Input("time-start-input", "value"),
        Input("time-end-input", "value"),
        State("time-timestamps", "data"),
        State("time-limits", "data"),
        State("draft-time", "data"),
        State("time-iso", "data"),
    )
    app.clientside_callback(
        """function(applied, timestamps) {
            if (!applied || !timestamps || !timestamps.length) return 'No timesteps';
            return timestamps[applied[0]] + ' – ' + timestamps[applied[1]];
        }""",
        Output("applied-time-summary", "children"),
        Input("applied-time", "data"),
        State("time-timestamps", "data"),
    )
    app.clientside_callback(
        "function(clicks, draft) { return draft.slice(); }",
        Output("applied-time", "data"),
        Input("apply-time", "n_clicks"),
        State("rs-time", "value"),
        prevent_initial_call=True,
    )
