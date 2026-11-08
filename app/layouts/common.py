from __future__ import annotations

from dash import dcc, html

from app import app_data
from app.time_window import annual_window_limits, initial_time_window, time_marks


def layout_header() -> html.Div:
    initial = initial_time_window(app_data.T)
    durations = (app_data.LOADED_INPUTS.timestep_resolution.to_series().reindex(app_data.TIME_INDEX)
                 if "timestep_resolution" in app_data.LOADED_INPUTS else None)
    limits = annual_window_limits(app_data.TIME_INDEX, durations)
    initial[1] = min(initial[1], limits["max_end"][0]) if app_data.T else 0
    model_name = app_data.get_model_name()
    return html.Div(
        [
            html.Div(
                [
                    html.Div([
                        html.Div("Calliope Dashboard", className="dashboard-title"),
                        html.Div(model_name or "Model", className="dashboard-model-name"),
                        html.Div("Calliope 0.7.0.dev7", className="dashboard-version"),
                    ], className="dashboard-identity"),
                    html.Div([
                    html.Div(
                        [
                            html.Label("Scenario", htmlFor="dd-scenario", className="filter-label"),
                            dcc.Dropdown(
                                id="dd-scenario",
                                options=app_data.SCENARIO_OPTIONS,
                                value=app_data.DEFAULT_SCENARIO,
                                clearable=False,
                                style={"width": "100%"},
                            ),
                        ], className="scenario-filter",
                    ),
                    html.Div(
                        [
                            html.Label("Carrier", htmlFor="dd-carrier", className="filter-label"),
                            dcc.Dropdown(
                                id="dd-carrier",
                                options=[{"label": c, "value": c} for c in app_data.CARRIER_OPTIONS],
                                value=app_data.DEFAULT_CARRIER,
                                clearable=False,
                                style={"width": "100%"},
                            ),
                        ], className="carrier-filter",
                    ),
                    ], className="model-selectors"),
                ],
                className="dashboard-model-heading",
            ),
            html.Div(
                [
                    html.Details(
                        [
                            html.Summary([
                                html.Div([
                                    html.Span("Time period", className="filter-label"),
                                    html.Span(id="applied-time-summary", className="applied-time-summary"),
                                ], className="time-summary-text"),
                                html.Span(id="time-status", role="status", **{"aria-live": "polite"}),
                                html.Span("⌄", className="time-summary-chevron", **{"aria-hidden": "true"}),
                            ], className="time-summary"),
                            dcc.Store(id="applied-time", data=initial),
                            dcc.Store(id="draft-time", data=initial),
                            dcc.Store(id="time-limits", data=limits),
                            dcc.Store(id="time-timestamps", data=app_data.TIME_INDEX.strftime("%d %b %Y %H:%M").tolist()),
                            dcc.Store(id="time-iso", data=app_data.TIME_INDEX.strftime("%Y-%m-%dT%H:%M").tolist()),
                            html.Div("Select up to one year", className="time-editor-hint"),
                            # Keep accessible draft labels without repeating the
                            # same dates visually above the editable fields.
                            html.Span(id="time-start-label", className="sr-only"),
                            html.Span(id="time-end-label", className="sr-only"),
                            html.Div([
                                html.Label([html.Span("From", className="date-field-label"), dcc.Input(
                                    id="time-start-input", type="text", debounce=True,
                                    value=app_data.TIME_INDEX[initial[0]].strftime("%Y-%m-%d %H:%M") if app_data.T else "",
                                    placeholder="YYYY-MM-DD HH:mm")], title="Date and time: YYYY-MM-DD HH:mm"),
                                html.Span("→", className="time-range-arrow", **{"aria-hidden": "true"}),
                                html.Label([html.Span("To", className="date-field-label"), dcc.Input(
                                    id="time-end-input", type="text", debounce=True,
                                    value=app_data.TIME_INDEX[initial[1]].strftime("%Y-%m-%d %H:%M") if app_data.T else "",
                                    placeholder="YYYY-MM-DD HH:mm")], title="Date and time: YYYY-MM-DD HH:mm"),
                                html.Button("Apply", id="apply-time", n_clicks=0, disabled=True),
                            ], className="time-date-inputs"),
                            dcc.RangeSlider(
                                id="rs-time", min=0, max=max(0, app_data.T - 1), step=1,
                                value=initial, marks=time_marks(app_data.TIME_INDEX),
                                allowCross=False, disabled=app_data.T <= 1, updatemode="drag",
                            ),
                            html.Div(id="time-validation", role="status", className="time-validation"),
                        ],
                        className="time-window-control",
                    ),
                ],
                className="dashboard-filters",
            ),
        ],
        className="dashboard-header",
    )


def layout_tabs() -> html.Div:
    return html.Div(
        [
            dcc.Tabs(
                id="tabs-mode",
                value=app_data.DEFAULT_TAB,
                children=[
                    dcc.Tab(label="Inputs", value="inputs"),
                    dcc.Tab(label="Results: Planning", value="results_planning"),
                    dcc.Tab(label="Results: Operate", value="results_operate"),
                ],
            )
        ],
        className="dashboard-nav",
    )


def layout_root(children) -> html.Div:
    return html.Div(
        children,
        className="dashboard-root",
    )
