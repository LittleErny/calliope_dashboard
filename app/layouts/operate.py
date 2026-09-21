from __future__ import annotations

from dash import dcc, html
import dash_leaflet as dl

from app import app_data


def layout_results_operate() -> html.Div:
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-start"},
        children=[
            html.Div(
                style={"flex": "2", "padding": "10px"},
                children=[
                    html.Div("Operate mode", style={"fontSize": "14px", "fontWeight": "800", "marginBottom": "8px"}),
                    dcc.Store(id="operate-selected-entity", data=None),
                    dl.Map(
                        id="operate-map",
                        center=app_data.MAP_CENTER,
                        zoom=app_data.MAP_ZOOM_DEFAULT,
                        style={"width": "100%", "height": "600px"},
                        children=[
                            dl.TileLayer(),
                            dl.LayerGroup(id="operate-map-layer"),
                        ],
                    ),
                    html.Div(
                        style={"display": "flex", "gap": "12px", "alignItems": "center", "marginTop": "10px"},
                        children=[
                            html.Div(
                                [
                                    html.Div("Map mode", style={"fontSize": "12px", "opacity": "0.7"}),
                                    dcc.RadioItems(
                                        id="operate-map-mode",
                                        options=[
                                            {"label": "Timestep", "value": "timestep"},
                                            {"label": "Critical", "value": "critical"},
                                        ],
                                        value="timestep",
                                        inline=True,
                                        style={"display": "flex", "gap": "10px"},
                                    ),
                                ],
                                style={"minWidth": "220px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Timestep", style={"fontSize": "12px", "opacity": "0.7"}),
                                    dcc.Slider(
                                        id="operate-timestep",
                                        min=0,
                                        max=max(0, app_data.OPERATE_T - 1),
                                        step=1,
                                        value=0,
                                        tooltip={"placement": "bottom", "always_visible": False},
                                        marks=None,
                                        updatemode="mouseup",
                                    ),
                                    html.Div(
                                        id="operate-time-label",
                                        style={"fontSize": "11px", "opacity": "0.7", "marginTop": "4px"},
                                    ),
                                ],
                                id="operate-timestep-container",
                                style={"flex": "1"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="operate-info-panel",
                style={
                    "flex": "1",
                    "padding": "10px",
                    "border": "1px solid #e6e6e6",
                    "borderRadius": "12px",
                    "backgroundColor": "white",
                    "display": "flex",
                    "flexDirection": "column",
                    "height": "90vh",
                },
                children=[
                    html.Div(
                        id="operate-info-content",
                        style={"marginTop": "12px", "overflowY": "auto", "flex": "1"},
                    ),
                ],
            ),
        ],
    )
