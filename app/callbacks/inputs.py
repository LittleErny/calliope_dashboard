from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html
import dash
import dash_leaflet as dl

import app_data
from figures import compute_resample_rule, downsample_series


INPUT_MARKER_COMPONENTS = [
    dl.Marker(
        id=f"inputs-marker-{city}",
        position=coords,
        children=[dl.Tooltip(city), dl.Popup([html.B(city)])],
    )
    for city, coords in app_data.INPUT_CITIES.items()
]

INPUT_ROUTE_LINES = [
    dl.Polyline(
        id=f"inputs-route-{a}-{b}",
        positions=[app_data.INPUT_CITIES[a], app_data.INPUT_CITIES[b]],
        color="red",
        weight=4,
        opacity=0.7,
        children=[dl.Tooltip(f"{a} → {b}")],
    )
    for a, b in app_data.INPUT_CONNECTIONS
]

INPUT_ARROWHEADS = [
    dl.Polygon(
        id=f"inputs-head-{a}-{b}",
        positions=[],
        color="red",
        fill=True,
        fillColor="red",
        fillOpacity=0.7,
        weight=2,
    )
    for a, b in app_data.INPUT_CONNECTIONS
]

INPUT_MARKER_INPUTS = [Input(f"inputs-marker-{c}", "n_clicks") for c in app_data.INPUT_CITIES.keys()]
INPUT_ROUTE_INPUTS = [Input(f"inputs-route-{a}-{b}", "n_clicks") for a, b in app_data.INPUT_CONNECTIONS]
INPUT_HEAD_INPUTS = [Input(f"inputs-head-{a}-{b}", "n_clicks") for a, b in app_data.INPUT_CONNECTIONS]
INPUT_HEAD_OUTPUTS = [Output(f"inputs-head-{a}-{b}", "positions") for a, b in app_data.INPUT_CONNECTIONS]

def _to_scalar(value):
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    try:
        arr = np.asarray(value)
    except Exception:
        return None
    if arr.size == 0:
        return None
    if arr.size == 1:
        return float(arr.reshape(-1)[0])
    if not np.issubdtype(arr.dtype, np.number):
        return None
    if np.isnan(arr).all():
        return None
    return float(np.nanmean(arr))


def default_inputs_panel() -> List[html.Component]:
    return [
        html.H3("Location Info"),
        html.P("Click a city to see details here."),
        html.Div(
            id="inputs-techs-list",
            style={"marginTop": "20px", "overflowY": "auto", "flex": "1"},
        ),
    ]


def register_inputs_callbacks(app):
    @app.callback(
        Output("inputs-map-layer", "children"),
        Input("inputs-map", "id"),
    )
    def update_inputs_map(_):
        return INPUT_MARKER_COMPONENTS + INPUT_ROUTE_LINES + INPUT_ARROWHEADS

    if INPUT_HEAD_OUTPUTS:
        @app.callback(INPUT_HEAD_OUTPUTS, Input("inputs-map", "zoom"))
        def scale_inputs_arrowheads(zoom):
            length, width = app_data.head_sizes_for_zoom(zoom)
            positions_list = []
            for a, b in app_data.INPUT_CONNECTIONS:
                a_pt = app_data.INPUT_CITIES[a]
                b_pt = app_data.INPUT_CITIES[b]
                tri = app_data.arrowhead_triangle_at_b(a_pt, b_pt, length_m=length, width_m=width)
                positions_list.append(tri)
            return positions_list

    @app.callback(
        Output("inputs-info-panel", "children"),
        Output("inputs-selected-city", "data"),
        INPUT_MARKER_INPUTS + INPUT_ROUTE_INPUTS + INPUT_HEAD_INPUTS,
    )
    def display_inputs_info(*_):
        ctx = dash.callback_context
        if not ctx.triggered or ctx.triggered[0]["value"] is None:
            return default_inputs_panel(), None

        trig_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trig_id.startswith("inputs-marker-"):
            city_name = trig_id.replace("inputs-marker-", "")
            area = app_data.INPUT_HELPER.get_location_area(city_name)
            carriers = app_data.INPUT_HELPER.get_location_carriers(city_name)
            if not carriers:
                return default_inputs_panel(), None

            return (
                [
                    html.H3(f"{city_name}, Germany"),
                    html.P(f"Location area: {area}"),
                    html.Div(
                        id="inputs-techs-list",
                        style={"marginTop": "20px", "overflowY": "auto", "flex": "1"},
                    ),
                ],
                city_name,
            )

        if trig_id.startswith("inputs-route-") or trig_id.startswith("inputs-head-"):
            prefix = "inputs-route-" if trig_id.startswith("inputs-route-") else "inputs-head-"
            tail = trig_id.replace(prefix, "")
            parts = tail.split("-")
            if len(parts) >= 2:
                a, b = parts[0], parts[1]
                cap = app_data.INPUT_HELPER.get_transmission_capacity(a, b)
                return (
                    [
                        html.H3(f"Line {a} → {b}"),
                        html.Ul([html.Li(f"Capacity: {cap:,.0f} kW")]),
                    ],
                    None,
                )

        return default_inputs_panel(), None

    @app.callback(
        Output("inputs-techs-list", "children"),
        Input("dd-carrier", "value"),
        Input("inputs-selected-city", "data"),
        Input("rs-time", "value"),
    )
    def update_inputs_techs_list(selected_carrier, selected_city, rng: List[int]):
        if not selected_city or not selected_carrier:
            return []

        city_name = selected_city
        available_carriers = app_data.INPUT_HELPER.get_location_carriers(city_name)
        if selected_carrier not in available_carriers:
            return [html.P(f"Carrier '{selected_carrier}' is not available at {city_name}.")]

        n = app_data.INPUT_T
        i0, i1 = sorted([int(rng[0]), int(rng[1])])
        i0 = max(0, min(n - 1, i0))
        i1 = max(0, min(n - 1, i1))
        x = app_data.INPUT_TIMESTEPS[i0:i1 + 1] if len(app_data.INPUT_TIMESTEPS) else np.arange(i0, i1 + 1)
        index = pd.DatetimeIndex(x) if len(x) and isinstance(x[0], (pd.Timestamp, np.datetime64)) else pd.Index(x)
        max_points = 1200
        rule = compute_resample_rule(index, max_points) if isinstance(index, pd.DatetimeIndex) else None

        demand_arrays = [
            -1 * np.array(arr)[i0:i1 + 1] for arr in app_data.INPUT_HELPER.get_location_demand(city_name, selected_carrier)
        ]

        total_demand = None
        if len(demand_arrays) > 0:
            total_demand = np.sum(np.vstack(demand_arrays), axis=0)
            demand_series = downsample_series(
                pd.Series(total_demand, index=index),
                max_points=max_points,
                how="mean",
                rule=rule,
            )
            total_demand = demand_series.values
            x_demand = demand_series.index
        else:
            x_demand = index

        supply_dict = app_data.INPUT_HELPER.get_location_total_max_supply(city_name, selected_carrier)

        loc_techs = app_data.INPUT_HELPER.get_location_techs(city_name, selected_carrier)
        tech_names = sorted({x[1] for x in loc_techs})

        card_style = {
            "border": "1px solid #ccc",
            "borderRadius": "6px",
            "padding": "10px",
            "marginBottom": "12px",
            "backgroundColor": "#fff",
            "boxShadow": "0 1px 2px rgba(0,0,0,0.06)",
        }

        def apply_layout(fig: go.Figure, title: str) -> go.Figure:
            fig.update_layout(
                title=title,
                xaxis_title="Time step",
                yaxis_title="Energy (kWh)",
                hovermode="x unified",
                showlegend=False,
                margin=dict(t=40, r=10, b=20, l=40),
            )
            fig.update_xaxes(tickformat="%Y-%m-%d %H:%M")
            fig.update_xaxes(showgrid=True, gridwidth=1, griddash="dot")
            fig.update_yaxes(showgrid=True, gridwidth=1, griddash="dot")
            return fig

        def add_info_li(items, label: str, value, help_text: str, fmt: str = "{:.4g}", prefix: str = "", suffix: str = ""):
            value = _to_scalar(value)
            if value is None or math.isnan(value):
                return
            items.append(
                html.Li(
                    [
                        f"{label}: {prefix}{fmt.format(float(value))}{suffix}",
                        html.Span(" (?)", title=help_text, style={"cursor": "help", "opacity": "0.7"}),
                    ]
                )
            )

        children = []

        if total_demand is not None:
            fig_d = go.Figure()
            fig_d.add_trace(go.Scattergl(
                y=total_demand,
                x=x_demand,
                name="Demand",
                line=dict(width=2),
                hovertemplate="%{y:.2f} kWh<extra>%{x}</extra>",
            ))
            fig_d = apply_layout(fig_d, f"Demand — {city_name} ({selected_carrier})")

            children.append(
                html.Div(
                    style=card_style,
                    children=[
                        html.H4("Demand", style={"marginBottom": "6px"}),
                        dcc.Graph(figure=fig_d, style={"height": "240px", "width": "100%"}),
                    ],
                )
            )

        for tech in tech_names:
            arr = supply_dict.get(f"{city_name}::{tech}")
            if arr is None:
                continue

            supply_series = downsample_series(
                pd.Series(np.array(arr)[i0:i1 + 1], index=index),
                max_points=max_points,
                how="mean",
                rule=rule,
            )

            fig_s = go.Figure()
            fig_s.add_trace(go.Scattergl(
                y=supply_series.values,
                x=supply_series.index,
                name=f"{tech} Supply",
                line=dict(width=2),
                hovertemplate="%{y:.2f} MWh<extra>%{x}</extra>",
            ))
            fig_s = apply_layout(fig_s, f"{tech} — {city_name} ({selected_carrier})")

            details_map = app_data.INPUT_HELPER.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
            cost_map = app_data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
            tech_children = []

            for key, value in details_map.items():
                val = _to_scalar(value)
                if val is None or math.isnan(val):
                    continue
                if key == "lifetime":
                    tech_children.append(html.Li(f"Lifetime: {val} years"))
                if key == "energy_cap_max":
                    tech_children.append(html.Li(f"Maximum Energy Capacity: {val} kWh"))
                if key == "energy_con":
                    tech_children.append(html.Li(f"Energy Consumption: {val} kWh"))
                if key == "energy_eff":
                    tech_children.append(html.Li(f"Energy Efficiency: {val * 100}%"))
                if key == "parasitic_eff":
                    tech_children.append(html.Li(f"Parasitic Efficiency: {val * 100}%"))
                if key == "resource_area_max":
                    tech_children.append(html.Li(f"Maximum Resource Area: {val} m²"))
                if key == "resource_eff":
                    tech_children.append(html.Li(f"Resource Efficiency: {val * 100}%"))

            add_info_li(
                tech_children,
                "Upfront cost",
                cost_map.get("cost_energy_cap"),
                "Calliope cost_energy_cap: investment cost per unit capacity (EUR per kWh).",
                prefix="€",
                suffix=" per kWh",
            )
            add_info_li(
                tech_children,
                "Depreciation rate",
                cost_map.get("cost_depreciation_rate"),
                "Calliope cost_depreciation_rate: annual depreciation rate (fraction).",
                fmt="{:.3f}",
            )
            add_info_li(
                tech_children,
                "Line cost per distance",
                cost_map.get("cost_energy_cap_per_distance"),
                "Calliope cost_energy_cap_per_distance: investment cost per unit distance (EUR per kWh per km).",
                prefix="€",
                suffix=" per kWh per km",
            )
            add_info_li(
                tech_children,
                "Operational cost",
                cost_map.get("cost_om_con"),
                "Calliope cost_om_con: operational cost per unit of energy consumed (EUR per kWh).",
                prefix="€",
                suffix=" per kWh",
            )

            details = html.Ul(children=tech_children)

            children.append(
                html.Div(
                    style=card_style,
                    children=[
                        html.H4(tech, style={"marginBottom": "6px"}),
                        details,
                        dcc.Graph(figure=fig_s, style={"height": "240px", "width": "100%"}),
                    ],
                )
            )

        conversion_techs = [t for t in tech_names if app_data.INPUT_HELPER.tech_is_conversion(t)]
        for tech in conversion_techs:
            io_map = app_data.INPUT_HELPER.get_conversion_tech_io(city_name, tech)
            carriers = {c for lst in io_map.values() for c in lst}
            if not carriers or selected_carrier not in carriers:
                continue

            base_cap = _to_scalar(app_data.INPUT_HELPER.get_loc_tech_capacity(city_name, tech))
            eff_arr = app_data.INPUT_HELPER.get_loc_tech_energy_eff(city_name, tech)
            eff_max = None
            if eff_arr is not None:
                try:
                    eff_max = float(np.nanmax(np.asarray(eff_arr)))
                except Exception:
                    eff_max = None
            input_max = None
            if base_cap is not None and not math.isnan(base_cap):
                if eff_max is not None and eff_max > 0:
                    input_max = base_cap / eff_max
                else:
                    input_max = base_cap

            ratio_map = app_data.INPUT_HELPER.get_conversion_carrier_ratios(city_name, tech)
            inputs = io_map.get("in", [])
            primary_out = io_map.get("out", [])
            secondary_out = io_map.get("out_2", [])
            outputs = primary_out + secondary_out

            tech_label = f"{tech} (conversion)"
            node_labels = inputs + [tech_label] + outputs
            node_colors = []
            for label in node_labels:
                if label == tech_label:
                    node_colors.append("#8e44ad")
                elif label in inputs:
                    node_colors.append("#2d74da")
                else:
                    node_colors.append("#2ecc71")

            src_idx = []
            tgt_idx = []
            values = []

            input_val = input_max if input_max is not None and not math.isnan(input_max) else (base_cap or 0.0)
            if inputs:
                per_input = input_val / max(1, len(inputs))
                for i, _ in enumerate(inputs):
                    src_idx.append(i)
                    tgt_idx.append(len(inputs))
                    values.append(per_input)

            for j, carrier in enumerate(outputs):
                ratio = ratio_map.get(("out_2", carrier), 1.0 if carrier in secondary_out else 1.0)
                out_val = (base_cap or 0.0) * ratio if base_cap is not None else 0.0
                src_idx.append(len(inputs))
                tgt_idx.append(len(inputs) + 1 + j)
                values.append(out_val)

            sankey_fig = go.Figure(
                data=[
                    go.Sankey(
                        node=dict(label=node_labels, pad=10, thickness=12, color=node_colors),
                        link=dict(source=src_idx, target=tgt_idx, value=values),
                    )
                ]
            )
            sankey_fig.update_layout(
                title="Conversion flow (max)",
                height=220,
                margin=dict(l=10, r=10, t=35, b=10),
            )

            tech_children = []
            if inputs:
                tech_children.append(html.Li(f"Inputs: {', '.join(inputs)}"))
            if outputs:
                tech_children.append(html.Li(f"Outputs: {', '.join(outputs)}"))
            if input_max is not None and not math.isnan(input_max):
                tech_children.append(html.Li(f"Max input: {input_max:.0f} kWh"))
            if base_cap is not None and not math.isnan(base_cap):
                for carrier in primary_out:
                    tech_children.append(html.Li(f"Max output ({carrier}): {base_cap:.0f} kWh"))
                for carrier in secondary_out:
                    ratio = ratio_map.get(("out_2", carrier), 1.0)
                    tech_children.append(html.Li(f"Max output ({carrier}): {base_cap * ratio:.0f} kWh"))

            details_map = app_data.INPUT_HELPER.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
            cost_map = app_data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
            for key, value in details_map.items():
                val = _to_scalar(value)
                if val is None or math.isnan(val):
                    continue
                if key == "lifetime":
                    tech_children.append(html.Li(f"Lifetime: {val} years"))
                if key == "energy_eff":
                    tech_children.append(html.Li(f"Energy Efficiency: {val * 100}%"))

            add_info_li(
                tech_children,
                "Upfront cost",
                cost_map.get("cost_energy_cap"),
                "Calliope cost_energy_cap: investment cost per unit capacity (EUR per kWh).",
                prefix="€",
                suffix=" per kWh",
            )

            details = html.Ul(children=tech_children)
            children.append(
                html.Div(
                    style=card_style,
                    children=[
                        html.H4(tech, style={"marginBottom": "6px"}),
                        details,
                        dcc.Graph(figure=sankey_fig, style={"height": "220px", "width": "100%"}),
                    ],
                )
            )

        for tech in tech_names:
            if app_data.INPUT_HELPER.tech_is_storage(tech):
                details_map = app_data.INPUT_HELPER.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
                cost_map = app_data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
                tech_children = []

                for key, value in details_map.items():
                    val = _to_scalar(value)
                    if val is None or math.isnan(val):
                        continue
                    if key == "lifetime":
                        tech_children.append(html.Li(f"Lifetime: {val} years"))
                    if key == "energy_cap_max":
                        tech_children.append(html.Li(f"Maximum Discharge Power: {val} kWh"))
                    if key == "energy_con":
                        tech_children.append(html.Li(f"Energy Consumption: {val} kWh"))
                    if key == "energy_eff":
                        tech_children.append(html.Li(f"Energy Efficiency: {val * 100}%"))
                    if key == "parasitic_eff":
                        tech_children.append(html.Li(f"Parasitic Efficiency: {val * 100}%"))
                    if key == "resource_area_max":
                        tech_children.append(html.Li(f"Maximum Resource Area: {val} m²"))
                    if key == "resource_eff":
                        tech_children.append(html.Li(f"Resource Efficiency: {val * 100}%"))
                    if key == "storage_cap_max":
                        tech_children.append(html.Li(f"Max Storage Capacity: {val} kWh"))

                add_info_li(
                    tech_children,
                    "Upfront cost",
                    cost_map.get("cost_energy_cap"),
                    "Calliope cost_energy_cap: investment cost per unit capacity (EUR per kWh).",
                    prefix="€",
                    suffix=" per kWh",
                )
                add_info_li(
                    tech_children,
                    "Depreciation rate",
                    cost_map.get("cost_depreciation_rate"),
                    "Calliope cost_depreciation_rate: annual depreciation rate (fraction).",
                    fmt="{:.3f}",
                )
                add_info_li(
                    tech_children,
                    "Line cost per distance",
                    cost_map.get("cost_energy_cap_per_distance"),
                    "Calliope cost_energy_cap_per_distance: investment cost per unit distance (EUR per kWh per km).",
                    prefix="€",
                    suffix=" per kWh per km",
                )
                add_info_li(
                    tech_children,
                    "Operational cost",
                    cost_map.get("cost_om_con"),
                    "Calliope cost_om_con: operational cost per unit of energy consumed (EUR per kWh).",
                    prefix="€",
                    suffix=" per kWh",
                )

                details = html.Ul(children=tech_children)
                children.append(
                    html.Div(
                        style=card_style,
                        children=[
                            html.H4(tech, style={"marginBottom": "6px"}),
                            details,
                        ],
                    )
                )

        return children
