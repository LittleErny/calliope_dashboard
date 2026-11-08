from __future__ import annotations

from dash import dcc, html, dash_table

from app import app_data
from helpers.results_helper import ALL_LOCATIONS
from app.costs_view import layout_cost_ledger


CHART_CONFIG = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
}


def layout_results_planning() -> html.Div:
    return html.Div(
        [
            html.Div([
                html.H1("Planning results"),
                html.P("Explore model results by location or technology.")
            ], className="planning-page-heading"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("View", className="planning-filter-label"),
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
                        ], className="planning-view-filter"
                    ),
                    html.Div(
                        [
                            html.Div(id="plan-selector-label", className="planning-filter-label"),
                            dcc.Dropdown(
                                id="plan-location-dd",
                                options=app_data.PLAN_LOCATION_OPTIONS,
                                value=ALL_LOCATIONS,
                                clearable=False,
                                style={"width": "100%"},
                            ),
                            dcc.Dropdown(
                                id="plan-tech-dd",
                                options=[{"label": t, "value": t} for t in app_data.PLAN_TECHS],
                                value=app_data.PLAN_TECHS[0] if app_data.PLAN_TECHS else None,
                                clearable=False,
                                style={"width": "100%", "display": "none"},
                            ),
                        ],
                        className="planning-selection-filter",
                    ),
                ],
                className="planning-toolbar",
            ),
            html.Div(id="plan-kpi-strip"),
            html.P("Carrier-specific costs exclude undivided Shared costs. Modeled cost includes annualised investment; CAPEX is upfront investment.", className="planning-cost-note"),
            html.H2("Breakdown", className="planning-section-heading"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Installed capacity (kW)", style={"fontSize": "13px", "fontWeight": "800", "marginBottom": "6px"}),
                            dcc.Graph(responsive=True, id="plan-capacity-bar", config=CHART_CONFIG, style={"height": "320px"}),
                        ],
                        className="planning-chart-card",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Cost breakdown", style={"fontSize": "13px", "fontWeight": "800"}),
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
                                className="planning-chart-heading",
                            ),
                            dcc.Graph(responsive=True, id="plan-cost-breakdown", config=CHART_CONFIG, style={"height": "320px"}),
                        ],
                        className="planning-chart-card",
                    ),
                    html.Div(
                        [
                            html.Div("CO2 breakdown (kg)", style={"fontSize": "13px", "fontWeight": "800"}),
                            dcc.Graph(responsive=True, id="plan-co2-breakdown", config=CHART_CONFIG, style={"height": "320px"}),
                        ],
                        className="planning-chart-card",
                    ),
                ],
                className="planning-summary-charts",
            ),
            html.H2("Over time", className="planning-section-heading"),
            # Temporarily hidden while the presentation of whole-model costs
            # is being reconsidered. Keep exact accounting and Shared scopes.
            # layout_cost_ledger(),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div([html.Div("Production over time", className="chart-title"), html.Div("Drag to zoom · double-click to reset", className="chart-interaction-hint")], className="chart-title-row"),
                            dcc.Graph(responsive=True, id="plan-production-ts", config=CHART_CONFIG, style={"height": "340px"}),
                        ],
                        className="planning-chart-card",
                    )
                ],
                style={"marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div([html.Div("Operational CO2 over time", className="chart-title"), html.Div("Drag to zoom · double-click to reset", className="chart-interaction-hint")], className="chart-title-row"),
                            dcc.Graph(responsive=True, id="plan-co2-ts", config=CHART_CONFIG, style={"height": "260px"}),
                        ],
                        className="planning-chart-card",
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
                        sort_action="native",
                        style_table={"overflowX": "auto"},
                        style_cell={"fontSize": "12px", "padding": "12px", "border": "0", "borderBottom": "1px solid #e9edf2", "color": "#263648", "textAlign": "right", "whiteSpace": "normal", "height": "auto", "minWidth": "110px"},
                        style_cell_conditional=[{"if": {"column_id": "Name"}, "textAlign": "left", "minWidth": "180px"}],
                        style_header={"fontWeight": "600", "color": "#526477", "background": "#f8fafc", "borderBottom": "1px solid #dce5ee"},
                        style_data_conditional=[
                            {"if": {"filter_query": '{Name} = "Total"'}, "fontWeight": "700"},
                        ],
                    ),
                ],
                className="planning-chart-card planning-details",
            ),
        ]
    )
