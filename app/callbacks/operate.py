from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, MATCH
import dash
import dash_leaflet as dl

import app_data
from figures import compute_resample_rule, downsample_series


UNMET_GREEN = (46, 204, 113)
UNMET_DARK_RED = (70, 0, 0)
UNMET_RED = (255, 0, 0)
LOAD_GREEN = (27, 94, 32)
LOAD_YELLOW = (255, 179, 0)
LOAD_RED = (183, 28, 28)

LINE_MIN_WIDTH = 2
LINE_MAX_WIDTH = 8
FLOW_EPS = 1e-6


def _lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> str:
    """
    Linearly interpolate between two RGB colors and return hex.
    """
    t = max(0.0, min(1.0, float(t)))
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    b_ = int(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02x}{g:02x}{b_:02x}"


def _scale_line_width(value: float, vmin: float, vmax: float) -> float:
    """
    Scale line width within [LINE_MIN_WIDTH, LINE_MAX_WIDTH] based on capacity.
    """
    if vmax <= vmin:
        return (LINE_MIN_WIDTH + LINE_MAX_WIDTH) / 2
    t = (value - vmin) / (vmax - vmin)
    return LINE_MIN_WIDTH + t * (LINE_MAX_WIDTH - LINE_MIN_WIDTH)


def _format_kwh(x: float) -> str:
    """
    Format kWh values with compact units.
    """
    if x >= 1e9:
        return f"{x/1e9:.2f}B"
    if x >= 1e6:
        return f"{x/1e6:.2f}M"
    if x >= 1e3:
        return f"{x/1e3:.2f}k"
    return f"{x:.0f}"


def _format_eur(x: float) -> str:
    """
    Format EUR values with compact units.
    """
    return f"€{_format_kwh(x)}"


def _unmet_to_color(unmet_fraction: float) -> str:
    """
    Map unmet fraction to a green->dark-red->red color ramp.

    0-10%: green to dark red
    10-100%: dark red to red
    """
    f = max(0.0, min(1.0, float(unmet_fraction)))
    if f <= 0.1:
        return _lerp_color(UNMET_GREEN, UNMET_DARK_RED, f / 0.1 if f > 0 else 0.0)
    # Use a strong gamma to make mid-range changes more visible on the map.
    t = (f - 0.1) / 0.9
    return _lerp_color(UNMET_DARK_RED, UNMET_RED, t ** 0.2)


def _load_to_color(load_fraction: float) -> str:
    """
    Map load fraction to a green->yellow->red color ramp.

    0–70%: green -> yellow
    70–90%: yellow -> red
    90–100%: deep red
    """
    f = max(0.0, min(1.0, float(load_fraction)))
    if f <= 0.7:
        return _lerp_color(LOAD_GREEN, LOAD_YELLOW, f / 0.7 if f > 0 else 0.0)
    if f <= 0.9:
        return _lerp_color(LOAD_YELLOW, LOAD_RED, (f - 0.7) / 0.2)
    return _lerp_color(LOAD_RED, (120, 0, 0), (f - 0.9) / 0.1)


def _build_location_markers(unmet_map: Dict[str, float]) -> List[dl.CircleMarker]:
    """
    Build colored location markers based on unmet fraction.
    """
    markers: List[dl.CircleMarker] = []
    for city, coords in app_data.INPUT_CITIES.items():
        unmet = float(unmet_map.get(city, 0.0))
        color = _unmet_to_color(unmet)
        tooltip = f"{city}: unmet {unmet * 100:.1f}%"
        markers.append(
            dl.CircleMarker(
                id=f"operate-marker-{city}",
                center=coords,
                radius=12,
                pathOptions={
                    "color": "#1f1f1f",
                    "weight": 1,
                    "fill": True,
                    "fillColor": color,
                    "fillOpacity": 1.0,
                },
                children=[dl.Tooltip(tooltip)],
            )
        )
    return markers


def _resolve_operate_window(rs_time: List[int]) -> Tuple[int, int]:
    """
    Resolve operate timesteps indices for the global time window.
    """
    if not app_data.OPERATE_T or not app_data.TIME_INDEX.size:
        return 0, max(0, app_data.OPERATE_T - 1)
    i0, i1 = sorted([int(rs_time[0]), int(rs_time[1])])
    i0 = max(0, min(len(app_data.TIME_INDEX) - 1, i0))
    i1 = max(0, min(len(app_data.TIME_INDEX) - 1, i1))
    t0 = app_data.TIME_INDEX[i0]
    t1 = app_data.TIME_INDEX[i1]

    mask = (app_data.OPERATE_TIMESTEPS >= t0) & (app_data.OPERATE_TIMESTEPS <= t1)
    if not mask.any():
        return 0, max(0, app_data.OPERATE_T - 1)
    indices = np.where(mask)[0]
    return int(indices[0]), int(indices[-1])


def _build_line_components(
    mode: str,
    carrier: str,
    timestep_idx: int,
    start_idx: int,
    end_idx: int,
    zoom: Optional[float],
) -> Tuple[List[dl.Polyline], List[dl.Polygon]]:
    """
    Build polylines and arrowheads for transmission lines.
    """
    helper = app_data.OPERATE_HELPER
    connections = app_data.OPERATE_CONNECTIONS

    capacities = []
    for a, b in connections:
        a_to_b, b_to_a = helper.get_line_ids_for_pair(a, b)
        cap = 0.0
        for line_id in [a_to_b, b_to_a]:
            if not line_id:
                continue
            cap = max(cap, helper.get_line_capacity(line_id))
        capacities.append(cap)

    cap_min = min(capacities) if capacities else 0.0
    cap_max = max(capacities) if capacities else 0.0

    line_components: List[dl.Polyline] = []
    arrow_components: List[dl.Polygon] = []

    length_m, width_m = app_data.head_sizes_for_zoom(zoom)

    for (a, b), cap in zip(connections, capacities):
        a_coords = app_data.INPUT_CITIES[a]
        b_coords = app_data.INPUT_CITIES[b]

        a_to_b, b_to_a = helper.get_line_ids_for_pair(a, b)

        load_vals = []
        flow_vals = {}
        for line_id in [a_to_b, b_to_a]:
            if not line_id:
                continue
            if mode == "critical":
                load_vals.append(helper.get_line_max_load_fraction_window(line_id, carrier, start_idx, end_idx))
                flow_vals[line_id] = helper.get_line_peak_flow_window(line_id, carrier, start_idx, end_idx)
            else:
                load_vals.append(helper.get_line_load_fraction_at_timestep(line_id, carrier, timestep_idx))
                flow_vals[line_id] = helper.get_line_flow_at_timestep(line_id, carrier, timestep_idx)
        load = max(load_vals) if load_vals else 0.0

        color = _load_to_color(load)
        weight = _scale_line_width(cap, cap_min, cap_max)
        tooltip = f"{a} ↔ {b} | load {load * 100:.1f}%"

        line_components.append(
            dl.Polyline(
                id=f"operate-route-{a}-{b}",
                positions=[a_coords, b_coords],
                pathOptions={"color": color, "weight": weight, "opacity": 0.8},
                children=[dl.Tooltip(tooltip)],
            )
        )

        # Arrowheads for A -> B
        if a_to_b and flow_vals.get(a_to_b, 0.0) > FLOW_EPS:
            tri = app_data.arrowhead_triangle_at_b(a_coords, b_coords, length_m=length_m, width_m=width_m)
        else:
            tri = []
        arrow_components.append(
            dl.Polygon(
                id=f"operate-head-{a}-{b}",
                positions=tri,
                pathOptions={
                    "color": color,
                    "weight": 2,
                    "fill": True,
                    "fillColor": color,
                    "fillOpacity": 0.8,
                },
            )
        )

        # Arrowheads for B -> A
        if b_to_a and flow_vals.get(b_to_a, 0.0) > FLOW_EPS:
            tri = app_data.arrowhead_triangle_at_b(b_coords, a_coords, length_m=length_m, width_m=width_m)
        else:
            tri = []
        arrow_components.append(
            dl.Polygon(
                id=f"operate-head-{b}-{a}",
                positions=tri,
                pathOptions={
                    "color": color,
                    "weight": 2,
                    "fill": True,
                    "fillColor": color,
                    "fillOpacity": 0.8,
                },
            )
        )

    return line_components, arrow_components


def _default_operate_panel_content() -> List[html.Component]:
    """
    Default content for the operate info panel (inner content only).
    """
    return [
        html.H3("Selection Info"),
        html.P("Click a location or a transmission line to see details here."),
    ]


def _build_demand_unmet_card(location: str, carrier: str, start_idx: int, end_idx: int) -> html.Div:
    """
    Build a stacked bar card for demand coverage by tech + unmet.
    """
    helper = app_data.OPERATE_HELPER
    demand_ts = helper.get_location_demand_window(location, carrier, start_idx, end_idx)
    unmet_ts = helper.get_location_unmet_window(location, carrier, start_idx, end_idx)

    if demand_ts.empty:
        return html.Div()

    max_points = 1200
    rule = compute_resample_rule(demand_ts.index, max_points)
    demand_ts = downsample_series(demand_ts, max_points=max_points, how="mean", rule=rule)
    unmet_ts = downsample_series(unmet_ts, max_points=max_points, how="mean", rule=rule)
    unmet_ts = unmet_ts.reindex(demand_ts.index, fill_value=0.0)
    met_ts = (demand_ts - unmet_ts).clip(lower=0.0)

    techs = helper.get_location_techs(location, include_transmission=False)
    tech_series: Dict[str, pd.Series] = {}
    tech_totals: Dict[str, float] = {}
    tech_labels: Dict[str, str] = {}
    tech_base_map: Dict[str, str] = {}

    for tech in techs:
        prod_ts = helper.get_location_tech_production_window(location, tech, carrier, start_idx, end_idx)
        prod_ts = downsample_series(prod_ts, max_points=max_points, how="mean", rule=rule)
        if prod_ts.sum() <= 0:
            continue
        tech_series[tech] = prod_ts
        tech_totals[tech] = float(prod_ts.sum())
        tech_labels[tech] = tech
        tech_base_map[tech] = tech.split(":", 1)[0]

    # Add imports from other locations (incoming transmission lines)
    for line_id in helper.get_incoming_line_ids(location):
        line_ref = helper.get_line_ref(line_id)
        if not line_ref:
            continue
        import_ts = helper.get_line_flow_window(line_id, carrier, start_idx, end_idx).clip(lower=0.0)
        import_ts = downsample_series(import_ts, max_points=max_points, how="mean", rule=rule)
        if import_ts.sum() <= 0:
            continue
        label = f"Import from {line_ref.src}"
        tech_series[label] = import_ts
        tech_totals[label] = float(import_ts.sum())
        tech_labels[label] = label
        tech_base_map[label] = line_ref.tech

    total_prod_ts = None
    for ts in tech_series.values():
        if total_prod_ts is None:
            total_prod_ts = ts.copy()
        else:
            total_prod_ts = total_prod_ts.add(ts, fill_value=0.0)
    if total_prod_ts is None:
        total_prod_ts = pd.Series(index=demand_ts.index, data=0.0)

    total_demand = demand_ts.replace(0, np.nan)

    # Determine order by total production over the window (descending)
    ordered_techs = [t for t, _ in sorted(tech_totals.items(), key=lambda x: x[1], reverse=True)]

    tech_color_map = helper.get_technology_color_map()
    fallback_palette = [
        "#2d74da",
        "#6FB8E6",
        "#F9D956",
        "#2A9D8F",
        "#D9A15C",
        "#4E4E4E",
        "#8E7CC3",
        "#54A24B",
        "#F58518",
    ]
    import_palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    import_color_map: Dict[str, str] = {}
    import_sources = sorted(
        {
            label.replace("Import from ", "")
            for label in tech_labels.values()
            if label.startswith("Import from ")
        }
    )
    for i, src in enumerate(import_sources):
        import_color_map[f"Import from {src}"] = import_palette[i % len(import_palette)]

    unmet_pct = (unmet_ts / total_demand * 100).fillna(0.0)
    fig = go.Figure()
    # Add met demand components
    for i, tech in enumerate(ordered_techs):
        prod_ts = tech_series[tech]
        share = (prod_ts / total_prod_ts.replace(0, np.nan)).fillna(0.0)
        alloc_ts = (met_ts * share).fillna(0.0)
        pct = (alloc_ts / total_demand * 100).fillna(0.0)
        label = tech_labels.get(tech, tech)
        if label.startswith("Import from "):
            color = import_color_map.get(label, fallback_palette[i % len(fallback_palette)])
        else:
            base = tech_base_map.get(tech, tech.split(":", 1)[0])
            color = tech_color_map.get(base, fallback_palette[i % len(fallback_palette)])
        fig.add_trace(
            go.Bar(
                x=alloc_ts.index,
                y=alloc_ts.values,
                name=label,
                marker_color=color,
                customdata=pct.values,
                hovertemplate="Tech: %{fullData.name}<br>%{y:.0f} kWh<br>%{customdata:.1f}% of demand<extra></extra>",
            )
        )

    fig.add_trace(
        go.Bar(
            x=demand_ts.index,
            y=unmet_ts.values,
            name="Unmet demand",
            marker_color="#c0392b",
            customdata=unmet_pct.values,
            hovertemplate="Tech: %{fullData.name}<br>%{y:.0f} kWh<br>%{customdata:.1f}% of demand<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="stack",
        title=None,
        height=320,
        margin=dict(t=20, r=10, b=20, l=40),
        xaxis_title="Time",
        yaxis_title="kWh",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
    )

    card_style = {
        "border": "1px solid #ccc",
        "borderRadius": "6px",
        "padding": "10px",
        "marginBottom": "12px",
        "backgroundColor": "#fff",
        "boxShadow": "0 1px 2px rgba(0,0,0,0.06)",
    }

    return html.Div(
        style=card_style,
        children=[
            html.H4("Demand coverage", style={"marginBottom": "6px"}),
            dcc.Graph(figure=fig, style={"height": "320px", "width": "100%"}),
        ],
    )


def _build_line_timeseries_figure(a: str, b: str, carrier: str, start_idx: int, end_idx: int) -> go.Figure:
    """
    Build a flow timeseries figure for a transmission line (both directions).
    """
    helper = app_data.OPERATE_HELPER
    a_to_b, b_to_a = helper.get_line_ids_for_pair(a, b)
    cap = 0.0
    series = []

    if a_to_b:
        ts = helper.get_line_flow_window(a_to_b, carrier, start_idx, end_idx)
        cap = max(cap, helper.get_line_capacity(a_to_b))
        if ts.abs().sum() > FLOW_EPS:
            series.append((f"{a} → {b}", ts))
    if b_to_a:
        ts = helper.get_line_flow_window(b_to_a, carrier, start_idx, end_idx)
        cap = max(cap, helper.get_line_capacity(b_to_a))
        if ts.abs().sum() > FLOW_EPS:
            series.append((f"{b} → {a}", ts))

    max_points = 1200
    rule = compute_resample_rule(series[0][1].index, max_points) if series else None

    fig = go.Figure()
    for label, ts in series:
        ts = downsample_series(ts, max_points=max_points, how="mean", rule=rule)
        pct = (ts.values / cap * 100) if cap > 0 else np.zeros(len(ts))
        fig.add_trace(
            go.Scattergl(
                x=ts.index,
                y=ts.values,
                mode="lines",
                name=label,
                customdata=pct,
                hovertemplate="%{y:.0f} kWh<br>%{customdata:.1f}% of capacity<extra></extra>",
            )
        )

    if cap > 0:
        cap_index = series[0][1].index if series else app_data.OPERATE_TIMESTEPS
        cap_index = downsample_series(
            pd.Series(np.zeros(len(cap_index)), index=cap_index),
            max_points=max_points,
            how="mean",
            rule=rule,
        ).index
        fig.add_trace(
            go.Scattergl(
                x=cap_index,
                y=[cap] * len(cap_index),
                mode="lines",
                name="Max capacity",
                line=dict(color="#c0392b", dash="dash"),
            )
        )

    if len(series) == 2:
        title = f"Transmission flow — {a} ↔ {b}"
    elif len(series) == 1:
        title = f"Transmission flow — {series[0][0]}"
    else:
        title = f"Transmission flow — {a} ↔ {b}"

    fig.update_layout(
        title=title,
        height=280,
        margin=dict(l=10, r=10, t=45, b=30),
        xaxis_title="Time",
        yaxis_title="kWh",
        yaxis=dict(range=[0, cap * 1.05 if cap > 0 else None]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _build_storage_figure(
    location: str,
    tech: str,
    carrier: str,
    start_idx: int,
    end_idx: int,
    mode: str,
) -> go.Figure:
    """
    Build a storage figure for SOC or charge/discharge.
    """
    helper = app_data.OPERATE_HELPER
    soc_ts = helper.get_storage_soc_window(location, tech, start_idx, end_idx)
    storage_cap = helper.get_storage_capacity(location, tech)

    if mode == "flow":
        charge_ts = helper.get_location_tech_consumption_window(location, tech, carrier, start_idx, end_idx).abs()
        discharge_ts = helper.get_location_tech_production_window(location, tech, carrier, start_idx, end_idx).abs()
        max_points = 1200
        base_index = charge_ts.index if not charge_ts.empty else discharge_ts.index
        rule = compute_resample_rule(base_index, max_points) if len(base_index) else None
        charge_ts = downsample_series(charge_ts, max_points=max_points, how="mean", rule=rule)
        discharge_ts = downsample_series(discharge_ts, max_points=max_points, how="mean", rule=rule)

        fig = go.Figure()
        if not charge_ts.empty:
            fig.add_trace(
                go.Bar(
                    x=charge_ts.index,
                    y=charge_ts.values,
                    name="Charge",
                    marker_color="#2ecc71",
                    hovertemplate="Charge: %{y:.0f} kWh<extra></extra>",
                )
            )
        if not discharge_ts.empty:
            fig.add_trace(
                go.Bar(
                    x=discharge_ts.index,
                    y=-discharge_ts.values,
                    name="Discharge",
                    marker_color="#e74c3c",
                    hovertemplate="Discharge: %{y:.0f} kWh<extra></extra>",
                )
            )

        max_val = 0.0
        if not charge_ts.empty:
            max_val = max(max_val, float(charge_ts.max()))
        if not discharge_ts.empty:
            max_val = max(max_val, float(discharge_ts.max()))

        fig.update_layout(
            barmode="overlay",
            height=280,
            margin=dict(t=35, r=10, b=25, l=40),
            xaxis_title="Time",
            yaxis_title="kWh",
            yaxis=dict(range=[-max_val * 1.1 if max_val > 0 else None, max_val * 1.1 if max_val > 0 else None]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        return fig

    # Default: SOC
    max_points = 1200
    rule = compute_resample_rule(soc_ts.index, max_points) if not soc_ts.empty else None
    soc_ts = downsample_series(soc_ts, max_points=max_points, how="mean", rule=rule)
    pct = (soc_ts / storage_cap * 100) if storage_cap > 0 else np.zeros(len(soc_ts))
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=soc_ts.index,
            y=soc_ts.values,
            mode="lines",
            name="SOC",
            line=dict(color="#2A9D8F", width=2),
            fill="tozeroy",
            customdata=pct,
            hovertemplate="SOC: %{y:.0f} kWh<br>%{customdata:.1f}% of capacity<extra></extra>",
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(t=35, r=10, b=25, l=40),
        xaxis_title="Time",
        yaxis_title="kWh",
        yaxis=dict(range=[0, storage_cap * 1.05 if storage_cap > 0 else None]),
        showlegend=False,
    )
    return fig


def _build_storage_card(location: str, tech: str, carrier: str, start_idx: int, end_idx: int) -> html.Div:
    """
    Build a storage technology card with SOC/flow toggle and summary.
    """
    helper = app_data.OPERATE_HELPER
    soc_ts = helper.get_storage_soc_window(location, tech, start_idx, end_idx)
    storage_cap = helper.get_storage_capacity(location, tech)
    energy_caps = helper.get_location_energy_caps(location)
    power_cap = float(energy_caps.get(tech, 0.0)) if energy_caps else 0.0

    charge_ts = helper.get_location_tech_consumption_window(location, tech, carrier, start_idx, end_idx).abs()
    discharge_ts = helper.get_location_tech_production_window(location, tech, carrier, start_idx, end_idx).abs()

    max_soc = float(soc_ts.max()) if not soc_ts.empty else 0.0
    min_soc = float(soc_ts.min()) if not soc_ts.empty else 0.0
    avg_soc = float(soc_ts.mean()) if not soc_ts.empty else 0.0
    total_charge = float(charge_ts.sum()) if not charge_ts.empty else 0.0
    total_discharge = float(discharge_ts.sum()) if not discharge_ts.empty else 0.0
    cycles = (total_discharge / storage_cap) if storage_cap > 0 else 0.0

    summary = html.Ul(
        [
            html.Li(f"Power cap: {_format_kwh(power_cap)} kW"),
            html.Li(f"Storage cap: {_format_kwh(storage_cap)} kWh"),
            html.Li(f"Max SOC: {_format_kwh(max_soc)} kWh"),
            html.Li(f"Min SOC: {_format_kwh(min_soc)} kWh"),
            html.Li(f"Average SOC: {_format_kwh(avg_soc)} kWh"),
            html.Li(f"Total charge: {_format_kwh(total_charge)} kWh"),
            html.Li(f"Total discharge: {_format_kwh(total_discharge)} kWh"),
            html.Li(f"Cycles (approx): {cycles:.2f}"),
        ]
    )

    card_style = {
        "border": "1px solid #ccc",
        "borderRadius": "6px",
        "padding": "10px",
        "marginBottom": "12px",
        "backgroundColor": "#fff",
        "boxShadow": "0 1px 2px rgba(0,0,0,0.06)",
    }

    return html.Div(
        style=card_style,
        children=[
            html.H4(tech, style={"marginBottom": "6px"}),
            summary,
            dcc.RadioItems(
                id={"type": "operate-storage-mode", "location": location, "tech": tech},
                options=[
                    {"label": "SOC (kWh)", "value": "soc"},
                    {"label": "Charge/Discharge", "value": "flow"},
                ],
                value="soc",
                inline=True,
                style={"display": "flex", "gap": "12px", "marginBottom": "8px"},
            ),
            dcc.Graph(
                id={"type": "operate-storage-graph", "location": location, "tech": tech},
                figure=_build_storage_figure(location, tech, carrier, start_idx, end_idx, "soc"),
                style={"height": "280px", "width": "100%"},
            ),
        ],
    )


def _build_location_cards(location: str, carrier: str, start_idx: int, end_idx: int) -> List[html.Div]:
    """
    Build location cards (demand + storage only).
    """
    helper = app_data.OPERATE_HELPER
    cards: List[html.Div] = []

    demand_card = _build_demand_unmet_card(location, carrier, start_idx, end_idx)
    if demand_card.children:
        cards.append(demand_card)

    techs = helper.get_location_techs(location, include_transmission=False)
    storage_techs = []
    for tech in techs:
        base = tech.split(":", 1)[0]
        if helper.is_storage_tech(base):
            storage_techs.append(tech)

    for tech in storage_techs:
        cards.append(_build_storage_card(location, tech, carrier, start_idx, end_idx))

    return cards


def register_operate_callbacks(app):
    @app.callback(
        Output("operate-map-layer", "children"),
        Input("operate-map-mode", "value"),
        Input("operate-timestep", "value"),
        Input("dd-carrier", "value"),
        Input("operate-map", "zoom"),
        Input("rs-time", "value"),
    )
    def update_operate_map(mode: str, timestep_idx: int, carrier: str, zoom: Optional[float], rs_time: List[int]):
        carrier_key = app_data.OPERATE_HELPER.normalize_carrier(str(carrier))
        start_idx, end_idx = _resolve_operate_window(rs_time)
        local_idx = int(timestep_idx) if timestep_idx is not None else 0
        local_idx = max(0, min(max(0, end_idx - start_idx), local_idx))
        t_idx = start_idx + local_idx

        if mode == "critical":
            unmet_map = {
                loc: app_data.OPERATE_HELPER.get_location_max_unmet_fraction_window(loc, carrier_key, start_idx, end_idx)
                for loc in app_data.INPUT_CITIES.keys()
            }
        else:
            unmet_map = {
                loc: app_data.OPERATE_HELPER.get_location_unmet_fraction_at_timestep(loc, carrier_key, t_idx)
                for loc in app_data.INPUT_CITIES.keys()
            }

        markers = _build_location_markers(unmet_map)
        lines, arrows = _build_line_components(mode, carrier_key, t_idx, start_idx, end_idx, zoom)
        return markers + lines + arrows

    @app.callback(
        Output("operate-time-label", "children"),
        Input("operate-timestep", "value"),
        Input("rs-time", "value"),
    )
    def update_operate_time_label(timestep_idx: int, rs_time: List[int]):
        if not app_data.OPERATE_T:
            return ""
        start_idx, end_idx = _resolve_operate_window(rs_time)
        local_idx = int(timestep_idx) if timestep_idx is not None else 0
        local_idx = max(0, min(max(0, end_idx - start_idx), local_idx))
        idx = start_idx + local_idx
        ts = app_data.OPERATE_TIMESTEPS[idx]
        if isinstance(ts, (pd.Timestamp, np.datetime64)):
            label = pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M")
        else:
            label = str(ts)
        return label

    @app.callback(
        Output("operate-timestep-container", "style"),
        Input("operate-map-mode", "value"),
    )
    def toggle_operate_timestep_visibility(mode: str):
        base_style = {"flex": "1"}
        if mode == "critical":
            return {**base_style, "display": "none"}
        return base_style

    @app.callback(
        Output({"type": "operate-storage-graph", "location": MATCH, "tech": MATCH}, "figure"),
        Input({"type": "operate-storage-mode", "location": MATCH, "tech": MATCH}, "value"),
        Input("dd-carrier", "value"),
        Input("rs-time", "value"),
        State({"type": "operate-storage-mode", "location": MATCH, "tech": MATCH}, "id"),
    )
    def update_storage_graph(mode: str, carrier: str, rs_time: List[int], storage_id: Dict):
        location = storage_id.get("location")
        tech = storage_id.get("tech")
        carrier_key = app_data.OPERATE_HELPER.normalize_carrier(str(carrier))
        start_idx, end_idx = _resolve_operate_window(rs_time)
        return _build_storage_figure(location, tech, carrier_key, start_idx, end_idx, mode)

    @app.callback(
        Output("operate-timestep", "max"),
        Output("operate-timestep", "value"),
        Output("operate-timestep", "marks"),
        Input("rs-time", "value"),
        State("operate-timestep", "value"),
    )
    def sync_operate_timestep_slider(rs_time: List[int], current_value: Optional[int]):
        start_idx, end_idx = _resolve_operate_window(rs_time)
        window_len = max(1, end_idx - start_idx + 1)
        max_val = window_len - 1
        if current_value is None:
            return max_val, 0, {}
        return max_val, min(int(current_value), max_val), {}

    marker_inputs = [Input(f"operate-marker-{c}", "n_clicks") for c in app_data.INPUT_CITIES.keys()]
    route_inputs = [Input(f"operate-route-{a}-{b}", "n_clicks") for a, b in app_data.OPERATE_CONNECTIONS]
    head_inputs = []
    for a, b in app_data.OPERATE_CONNECTIONS:
        head_inputs.append(Input(f"operate-head-{a}-{b}", "n_clicks"))
        head_inputs.append(Input(f"operate-head-{b}-{a}", "n_clicks"))

    @app.callback(
        Output("operate-selected-entity", "data"),
        marker_inputs + route_inputs + head_inputs,
        State("operate-selected-entity", "data"),
    )
    def capture_operate_selection(*args):
        ctx = dash.callback_context
        current = args[-1] if args else None
        if not ctx.triggered or ctx.triggered[0]["value"] is None:
            return current

        trig_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trig_id.startswith("operate-marker-"):
            city = trig_id.replace("operate-marker-", "")
            return {"type": "location", "location": city}
        if trig_id.startswith("operate-route-"):
            tail = trig_id.replace("operate-route-", "")
            parts = tail.split("-")
            if len(parts) >= 2:
                return {"type": "line", "a": parts[0], "b": parts[1]}
        if trig_id.startswith("operate-head-"):
            tail = trig_id.replace("operate-head-", "")
            parts = tail.split("-")
            if len(parts) >= 2:
                return {"type": "line", "a": parts[0], "b": parts[1]}

        return current

    @app.callback(
        Output("operate-info-content", "children"),
        Input("operate-selected-entity", "data"),
        Input("dd-carrier", "value"),
        Input("rs-time", "value"),
    )
    def update_operate_info(selection: Optional[Dict], carrier: str, rs_time: List[int]):
        if not selection:
            return _default_operate_panel_content()

        carrier_key = app_data.OPERATE_HELPER.normalize_carrier(str(carrier))
        start_idx, end_idx = _resolve_operate_window(rs_time)

        if selection.get("type") == "line":
            a = selection.get("a")
            b = selection.get("b")
            if not a or not b:
                return _default_operate_panel_content()

            fig = _build_line_timeseries_figure(a, b, carrier_key, start_idx, end_idx)
            helper = app_data.OPERATE_HELPER
            a_to_b, b_to_a = helper.get_line_ids_for_pair(a, b)
            cap = max(helper.get_line_capacity(a_to_b or ""), helper.get_line_capacity(b_to_a or ""))
            peak = 0.0
            total = 0.0
            a_to_b_total = 0.0
            b_to_a_total = 0.0
            if a_to_b:
                peak = max(peak, helper.get_line_peak_flow_window(a_to_b, carrier_key, start_idx, end_idx))
                a_to_b_total = helper.get_line_total_flow_window(a_to_b, carrier_key, start_idx, end_idx)
                total += a_to_b_total
            if b_to_a:
                peak = max(peak, helper.get_line_peak_flow_window(b_to_a, carrier_key, start_idx, end_idx))
                b_to_a_total = helper.get_line_total_flow_window(b_to_a, carrier_key, start_idx, end_idx)
                total += b_to_a_total

            if a_to_b_total > FLOW_EPS and b_to_a_total > FLOW_EPS:
                title = f"Line {a} ↔ {b}"
            elif a_to_b_total > FLOW_EPS:
                title = f"Line {a} → {b}"
            elif b_to_a_total > FLOW_EPS:
                title = f"Line {b} → {a}"
            else:
                title = f"Line {a} ↔ {b}"

            summary = html.Ul(
                [
                html.Li(f"Max capacity: {_format_kwh(cap)} kW"),
                html.Li(f"Peak flow: {_format_kwh(peak)} kWh"),
                html.Li(f"Total flow: {_format_kwh(total)} kWh"),
                ]
            )

            return [
                html.H3(title),
                summary,
                dcc.Graph(figure=fig, style={"height": "300px"}),
            ]

        if selection.get("type") == "location":
            location = selection.get("location")
            if not location:
                return _default_operate_panel_content()

            helper = app_data.OPERATE_HELPER
            kpis = helper.get_location_operate_kpis_window(location, carrier_key, start_idx, end_idx)
            unmet_pct = 0.0
            if kpis["total_demand"] > 0:
                unmet_pct = kpis["total_unmet"] / kpis["total_demand"]
            summary = html.Ul(
                [
                    html.Li(f"Total demand: {_format_kwh(kpis['total_demand'])} kWh"),
                    html.Li(f"Total production: {_format_kwh(kpis['total_production'])} kWh"),
                    html.Li(f"Total unmet: {_format_kwh(kpis['total_unmet'])} kWh"),
                    html.Li(f"Unmet share: {unmet_pct * 100:.1f}%"),
                    html.Li(f"Variable OPEX: {_format_eur(kpis['total_variable_cost'])}"),
                ]
            )

            tech_cards = _build_location_cards(location, carrier_key, start_idx, end_idx)

            return [
                html.H3(f"{location}"),
                html.H4("Location summary"),
                summary,
                html.H4("Technologies"),
                html.Div(tech_cards),
            ]

        return _default_operate_panel_content()
