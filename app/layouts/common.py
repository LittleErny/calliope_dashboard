from __future__ import annotations

from dash import dcc, html

import app_data
from figures import APP_BG


def layout_header() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div("Calliope Dashboard", style={"fontSize": "18px", "fontWeight": "800"}),
                ],
                style={"display": "flex", "flexDirection": "column", "gap": "2px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Scenario", style={"fontSize": "11px", "opacity": "0.7"}),
                            dcc.Dropdown(
                                id="dd-scenario",
                                options=[{"label": s, "value": s} for s in app_data.SCENARIOS],
                                value=app_data.SCENARIOS[0] if app_data.SCENARIOS else None,
                                clearable=False,
                                style={"width": "210px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div("Carrier", style={"fontSize": "11px", "opacity": "0.7"}),
                            dcc.Dropdown(
                                id="dd-carrier",
                                options=[{"label": c, "value": c} for c in app_data.CARRIER_OPTIONS],
                                value=app_data.DEFAULT_CARRIER,
                                clearable=False,
                                style={"width": "170px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div("Time window", style={"fontSize": "11px", "opacity": "0.7"}),
                            dcc.RangeSlider(
                                id="rs-time",
                                min=0,
                                max=app_data.T - 1,
                                step=1,
                                value=[0, min(app_data.T - 1, 48)],
                                tooltip={"placement": "bottom", "always_visible": False},
                                updatemode="mouseup",
                            ),
                            html.Div(id="time-label", style={"fontSize": "11px", "opacity": "0.7", "marginTop": "4px"}),
                        ],
                        style={"minWidth": "360px"},
                    ),
                ],
                style={"display": "flex", "gap": "14px", "alignItems": "end"},
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "gap": "16px",
            "alignItems": "center",
            "padding": "14px 16px",
            "background": "white",
            "borderBottom": "1px solid #e9e9e9",
        },
    )


def layout_tabs() -> html.Div:
    return html.Div(
        [
            dcc.Tabs(
                id="tabs-mode",
                value="inputs",
                children=[
                    dcc.Tab(label="Inputs", value="inputs"),
                    dcc.Tab(label="Results: Planning", value="results_planning"),
                    dcc.Tab(label="Results: Operate", value="results_operate"),
                ],
            )
        ],
        style={"padding": "10px 14px", "background": "white", "borderBottom": "1px solid #e9e9e9"},
    )


def layout_root(children) -> html.Div:
    return html.Div(
        children,
        style={"background": APP_BG, "minHeight": "80vh"},
    )
