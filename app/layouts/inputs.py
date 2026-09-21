from __future__ import annotations

from dash import dcc, html
import dash_leaflet as dl

from app import app_data


def layout_inputs() -> html.Div:
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-start"},
        children=[
            html.Div(
                style={"flex": "2", "padding": "10px"},
                children=[
                    html.Div("Model inputs", style={"fontSize": "14px", "fontWeight": "800", "marginBottom": "8px"}),
                    dcc.Store(id="inputs-selected-city", data=None),
                    dl.Map(
                        id="inputs-map",
                        center=app_data.MAP_CENTER,
                        zoom=app_data.MAP_ZOOM_DEFAULT,
                        style={"width": "100%", "height": "600px"},
                        children=[
                            dl.TileLayer(),
                            dl.LayerGroup(id="inputs-map-layer"),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="inputs-info-panel",
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
                    html.H3("Location Info"),
                    html.P("Click a city to see details here."),
                    html.Div(
                        id="inputs-techs-list",
                        style={"marginTop": "20px", "overflowY": "auto", "flex": "1"},
                    ),
                ],
            ),
        ],
    )
