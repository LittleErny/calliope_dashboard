from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
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


def compute_resample_rule(index: pd.DatetimeIndex, max_points: int) -> Optional[pd.tseries.offsets.BaseOffset]:
    if not isinstance(index, pd.DatetimeIndex) or len(index) <= max_points:
        return None
    sample = index[: min(20, len(index))]
    freq = pd.infer_freq(sample)
    if not freq:
        return None
    try:
        base = pd.tseries.frequencies.to_offset(freq)
    except Exception:
        return None
    factor = int(math.ceil(len(index) / max_points))
    return base * max(1, factor)


def downsample_series(
    series: pd.Series,
    max_points: int = 1500,
    how: str = "mean",
    rule: Optional[pd.tseries.offsets.BaseOffset] = None,
) -> pd.Series:
    if series is None or series.empty or len(series) <= max_points:
        return series
    if rule is None and isinstance(series.index, pd.DatetimeIndex):
        rule = compute_resample_rule(series.index, max_points)
    if rule is not None and isinstance(series.index, pd.DatetimeIndex):
        if how == "sum":
            return series.resample(rule).sum()
        return series.resample(rule).mean()
    stride = int(math.ceil(len(series) / max_points))
    return series.iloc[::max(1, stride)]


def downsample_grouped_frame(
    df: pd.DataFrame,
    time_col: str,
    value_col: str,
    group_col: str,
    max_points: int = 1500,
    how: str = "mean",
) -> pd.DataFrame:
    if df.empty:
        return df
    idx = pd.DatetimeIndex(df[time_col].unique()).sort_values()
    rule = compute_resample_rule(idx, max_points) if len(idx) else None
    frames = []
    for label, sub in df.groupby(group_col):
        series = sub.set_index(time_col)[value_col].sort_index()
        ds = downsample_series(series, max_points=max_points, how=how, rule=rule)
        tmp = ds.reset_index().rename(columns={value_col: value_col})
        tmp[group_col] = label
        frames.append(tmp)
    return pd.concat(frames, ignore_index=True)
