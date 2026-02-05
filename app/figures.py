from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from dash import html

APP_BG = "#f6f7fb"


def kpi_tile(title: str, value: str, subtitle: str = "") -> html.Div:
    return html.Div(
        [
            html.Div(title, style={"fontSize": "12px", "opacity": "0.75"}),
            html.Div(value, style={"fontSize": "22px", "fontWeight": "700", "marginTop": "4px"}),
            html.Div(subtitle, style={"fontSize": "11px", "opacity": "0.7", "marginTop": "2px"}) if subtitle else None,
        ],
        style={
            "border": "1px solid #e6e6e6",
            "borderRadius": "14px",
            "padding": "10px 12px",
            "background": "white",
            "minWidth": "180px",
        },
    )


def format_number(x: float) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "0"
    if abs(x) >= 1e9:
        return f"{x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"{x/1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"{x/1e3:.2f}k"
    return f"{x:,.0f}"


def empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14),
            )
        ],
        height=320,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig
