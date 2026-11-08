from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html

APP_BG = "#f6f7fb"

DETAIL_CHART_CONFIG = {"displaylogo": False, "responsive": True}


def style_detail_chart(fig: go.Figure, *, axes: bool = True) -> go.Figure:
    """Apply the dashboard's chart treatment without changing trace data."""
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Geist, Arial, sans-serif", size=11, color="#526477"),
        title_font=dict(size=12, color="#263648"),
        hoverlabel=dict(bgcolor="white", font_color="#263648"),
    )
    if axes:
        fig.update_xaxes(automargin=True, showgrid=False)
        fig.update_yaxes(automargin=True, gridcolor="#e9edf2", griddash="solid")
    return fig


def kpi_tile(title: str, value: str, subtitle: str = "", *, help_text: str = "", help_id: str = "") -> html.Div:
    heading = title
    if help_text:
        heading = [
            html.Span(title),
            html.Span(
                ["?", html.Span(help_text, id=help_id, className="coverage-help-tooltip", role="tooltip")],
                className="coverage-help", tabIndex=0, role="button",
                **{"aria-label": f"About {title}", "aria-describedby": help_id},
            ),
        ]
    return html.Div(
        [
            html.Div(heading, className="planning-kpi-heading", style={"fontSize": "12px", "opacity": "0.75"}),
            html.Div(value, style={"fontSize": "22px", "fontWeight": "700", "marginTop": "4px"}),
            html.Div(subtitle, style={"fontSize": "11px", "opacity": "0.7", "marginTop": "2px"}) if subtitle else None,
        ],
        className="planning-kpi",
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


def compute_resample_rule(index: pd.DatetimeIndex, max_points: int):
    if not isinstance(index, pd.DatetimeIndex) or len(index) <= max_points:
        return None
    # Calendar bins also work for irregular time axes; never discard energy
    # by selecting every nth sample.
    for rule in ("1min", "5min", "15min", "30min", "1h", "2h", "3h", "4h", "6h", "12h", "1D", "W-MON", "MS", "QS", "YS"):
        counts = pd.Series(1, index=index).resample(rule, closed="left", label="left").size()
        if counts.gt(0).sum() <= max_points:
            return rule
    return pd.DateOffset(years=max(1, math.ceil((index[-1].year-index[0].year+1)/max_points)))


def interval_label(rule) -> str:
    labels = {"1min": "1 minute", "5min": "5 minutes", "15min": "15 minutes", "30min": "30 minutes",
              "1h": "1 hour", "2h": "2 hours", "3h": "3 hours", "4h": "4 hours", "6h": "6 hours", "12h": "12 hours",
              "1D": "1 day", "W-MON": "1 week (Mon–Sun)", "MS": "1 month", "QS": "1 quarter", "YS": "1 year"}
    return labels.get(rule, str(rule or "original timestep"))


def downsample_series(
    series: pd.Series,
    max_points: int = 1500,
    how: str = "mean",
    rule: Optional[pd.tseries.offsets.BaseOffset] = None,
) -> pd.Series:
    if series is None or series.empty:
        return series
    if rule is None and isinstance(series.index, pd.DatetimeIndex):
        rule = compute_resample_rule(series.index, max_points)
    if rule is not None and isinstance(series.index, pd.DatetimeIndex):
        groups = series.resample(rule, closed="left", label="left")
        return groups.agg(how).loc[groups.size().gt(0)]
    return series


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
    result = pd.concat(frames, ignore_index=True)
    result.attrs["interval"] = interval_label(rule)
    return result
