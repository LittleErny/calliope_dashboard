from __future__ import annotations

from dash import dcc, html, dash_table

from app import app_data
from helpers.results_helper import ALL_LOCATIONS


def layout_results_planning() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("View", style={"fontSize": "12px", "opacity": "0.7"}),
                            dcc.RadioItems(
                                id="plan-view-mode",
                                options=[
                                    {"label": "By Location", "value": "location"},
                                    {"label": "By Technology", "value": "technology"},
                                ],
                                value="location",
                                inline=True,
                                style={"display": "flex", "gap": "12px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(id="plan-selector-label", style={"fontSize": "12px", "opacity": "0.7"}),
                            dcc.Dropdown(
                                id="plan-location-dd",
                                options=app_data.PLAN_LOCATION_OPTIONS,
                                value=ALL_LOCATIONS,
                                clearable=False,
                                style={"width": "260px"},
                            ),
                            dcc.Dropdown(
                                id="plan-tech-dd",
                                options=[{"label": t, "value": t} for t in app_data.PLAN_TECHS],
                                value=app_data.PLAN_TECHS[0] if app_data.PLAN_TECHS else None,
                                clearable=False,
                                style={"width": "260px", "display": "none"},
                            ),
                        ],
                        style={"display": "flex", "flexDirection": "column", "gap": "6px"},
                    ),
                    html.Div(id="plan-kpi-strip", style={"display": "flex", "gap": "10px", "flexWrap": "wrap"}),
                ],
                style={"display": "flex", "gap": "16px", "alignItems": "flex-end"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Installed capacity by category (kW)", style={"fontSize": "13px", "fontWeight": "800", "marginBottom": "6px"}),
                            dcc.Graph(id="plan-capacity-bar", config={"displayModeBar": False, "responsive": False}, style={"height": "320px"}),
                        ],
                        style={"flex": "1", "border": "1px solid #e6e6e6", "borderRadius": "14px", "padding": "10px", "background": "white"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Cost breakdown (€)", style={"fontSize": "13px", "fontWeight": "800"}),
                                    dcc.RadioItems(
                                        id="plan-cost-norm",
                                        options=[
                                            {"label": "Absolute (€)", "value": "absolute"},
                                            {"label": "€/kW", "value": "per_kw"},
                                        ],
                                        value="absolute",
                                        inline=True,
                                        style={"display": "flex", "gap": "10px", "fontSize": "12px"},
                                    ),
                                ],
                                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                            ),
                            dcc.Graph(id="plan-cost-breakdown", config={"displayModeBar": False, "responsive": False}, style={"height": "320px"}),
                        ],
                        style={"flex": "1", "border": "1px solid #e6e6e6", "borderRadius": "14px", "padding": "10px", "background": "white"},
                    ),
                    html.Div(
                        [
                            html.Div("CO2 breakdown (kg)", style={"fontSize": "13px", "fontWeight": "800"}),
                            dcc.Graph(id="plan-co2-breakdown", config={"displayModeBar": False, "responsive": False}, style={"height": "320px"}),
                        ],
                        style={"flex": "1", "border": "1px solid #e6e6e6", "borderRadius": "14px", "padding": "10px", "background": "white"},
                    ),
                ],
                style={"display": "flex", "gap": "12px", "marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Production over time", style={"fontSize": "13px", "fontWeight": "800"}),
                            dcc.Graph(id="plan-production-ts", config={"displayModeBar": False, "responsive": False}, style={"height": "340px"}),
                        ],
                        style={"border": "1px solid #e6e6e6", "borderRadius": "14px", "padding": "10px", "background": "white"},
                    )
                ],
                style={"marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("CO2 over time", style={"fontSize": "13px", "fontWeight": "800"}),
                            dcc.Graph(id="plan-co2-ts", config={"displayModeBar": False, "responsive": False}, style={"height": "260px"}),
                        ],
                        style={"border": "1px solid #e6e6e6", "borderRadius": "14px", "padding": "10px", "background": "white"},
                    )
                ],
                style={"marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div("Details", style={"fontSize": "13px", "fontWeight": "800", "marginBottom": "8px"}),
                    dash_table.DataTable(
                        id="plan-detail-table",
                        columns=[],
                        data=[],
                        page_size=12,
                        style_table={"overflowX": "auto"},
                        style_cell={"fontSize": "12px", "padding": "8px"},
                        style_header={"fontWeight": "700", "background": "#fafafa"},
                        style_data_conditional=[
                            {"if": {"filter_query": '{Name} = "Total"'}, "fontWeight": "700"},
                        ],
                    ),
                ],
                style={"border": "1px solid #e6e6e6", "borderRadius": "14px", "padding": "12px", "background": "white", "marginTop": "10px"},
            ),
        ]
    )
