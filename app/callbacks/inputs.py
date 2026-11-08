from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html
import dash
import dash_leaflet as dl

from app import app_data
from app.figures import DETAIL_CHART_CONFIG, compute_resample_rule, downsample_series, interval_label, style_detail_chart


INPUT_MARKER_COMPONENTS = [
    dl.Marker(
        id=f"inputs-marker-{city}",
        position=coords,
        title=city,
        alt=city,
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
        children=[dl.Tooltip(f"{a} {'↔' if app_data.INPUT_HELPER.allows_transmission_flow(b, a) else '→'} {b}")],
    )
    for a, b in app_data.INPUT_CONNECTIONS
]

INPUT_ARROW_DIRECTIONS = [
    direction
    for a, b in app_data.INPUT_CONNECTIONS
    for direction in [(a, b), (b, a)]
    if app_data.INPUT_HELPER.allows_transmission_flow(*direction)
]

INPUT_ARROWHEADS = [
    dl.Polygon(
        id=f"inputs-head-{a}-{b}",
        positions=[],
        color="#1f1f1f",
        fill=True,
        fillColor="red",
        fillOpacity=0.7,
        weight=1,
    )
    for a, b in INPUT_ARROW_DIRECTIONS
]

INPUT_MARKER_INPUTS = [Input(f"inputs-marker-{c}", "n_clicks", allow_optional=True) for c in app_data.INPUT_CITIES.keys()]
INPUT_ROUTE_INPUTS = [Input(f"inputs-route-{a}-{b}", "n_clicks", allow_optional=True) for a, b in app_data.INPUT_CONNECTIONS]
INPUT_HEAD_INPUTS = [Input(f"inputs-head-{a}-{b}", "n_clicks", allow_optional=True) for a, b in INPUT_ARROW_DIRECTIONS]
INPUT_HEAD_OUTPUTS = [Output(f"inputs-head-{a}-{b}", "positions") for a, b in INPUT_ARROW_DIRECTIONS]

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
        html.H3("Location details"),
        html.P("Select a location on the map to see its details."),
        html.Div(
            id="inputs-techs-list",
            style={"marginTop": "20px", "overflowY": "auto", "flex": "1"},
        ),
    ]


def register_inputs_callbacks(app):
    @app.callback(
        Output("inputs-map-layer", "children"),
        Input("inputs-map", "id"),
        Input("dd-carrier", "value"),
        Input("dd-scenario", "value"),
        State("inputs-map", "zoom"),
    )
    def update_inputs_map(_, carrier, scenario, zoom):
        helper = app_data.get_scenario(scenario, carrier).INPUT_HELPER
        length, width = app_data.head_sizes_for_zoom(zoom)
        lines = []
        for a, b in app_data.INPUT_CONNECTIONS:
            visible = helper.allows_transmission_flow(a, b, carrier) or helper.allows_transmission_flow(b, a, carrier)
            lines.append(dl.Polyline(
                id=f"inputs-route-{a}-{b}",
                positions=[app_data.INPUT_CITIES[a], app_data.INPUT_CITIES[b]] if visible else [],
                color="red", weight=4, opacity=0.7,
                children=[dl.Tooltip(f"{a} {'↔' if helper.allows_transmission_flow(b, a, carrier) else '→'} {b}")],
            ))
        arrows = [dl.Polygon(
            id=f"inputs-head-{a}-{b}",
            positions=app_data.arrowhead_triangle_at_b(app_data.INPUT_CITIES[a], app_data.INPUT_CITIES[b], length, width, zoom=zoom, marker="pin")
            if helper.allows_transmission_flow(a, b, carrier) else [],
            color="#1f1f1f", fill=True, fillColor="red", fillOpacity=0.7, weight=1,
        ) for a, b in INPUT_ARROW_DIRECTIONS]
        return INPUT_MARKER_COMPONENTS + lines + arrows

    if INPUT_HEAD_OUTPUTS:
        @app.callback(INPUT_HEAD_OUTPUTS, Input("inputs-map", "zoom"), Input("dd-carrier", "value"), Input("dd-scenario", "value"))
        def scale_inputs_arrowheads(zoom, carrier, scenario):
            data = app_data.get_scenario(scenario, carrier)
            length, width = app_data.head_sizes_for_zoom(zoom)
            positions_list = []
            for a, b in INPUT_ARROW_DIRECTIONS:
                a_pt = app_data.INPUT_CITIES[a]
                b_pt = app_data.INPUT_CITIES[b]
                tri = app_data.arrowhead_triangle_at_b(a_pt, b_pt, length_m=length, width_m=width, zoom=zoom, marker="pin")
                positions_list.append(tri if data.INPUT_HELPER.allows_transmission_flow(a, b, carrier) else [])
            return positions_list

    @app.callback(
        Output("inputs-info-panel", "children"),
        Output("inputs-selected-city", "data"),
        INPUT_MARKER_INPUTS + INPUT_ROUTE_INPUTS + INPUT_HEAD_INPUTS + [Input("dd-scenario", "value"), Input("dd-carrier", "value")],
        State("inputs-selected-city", "data", allow_optional=True),
    )
    def display_inputs_info(*_):
        scenario, carrier, current_city = _[-3:]
        data = app_data.get_scenario(scenario, carrier)
        ctx = dash.callback_context
        if not ctx.triggered or ctx.triggered[0]["value"] is None:
            return default_inputs_panel(), None

        trig_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trig_id in {"dd-scenario", "dd-carrier"}:
            if not current_city:
                return default_inputs_panel(), None
            trig_id = f"inputs-marker-{current_city}"
        if trig_id.startswith("inputs-marker-"):
            city_name = trig_id.replace("inputs-marker-", "")
            area = data.INPUT_HELPER.get_location_area(city_name)
            area_text = f"Location area: {area}" if np.isfinite(area) else "Location area: not specified"

            return (
                [
                    html.H3(city_name),
                    html.P(area_text),
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
                cap = data.INPUT_HELPER.get_transmission_capacity(a, b)
                return (
                    [
                        html.H3(f"Line {a} {'↔' if app_data.INPUT_HELPER.allows_transmission_flow(b, a) else '→'} {b}"),
                        html.Ul([html.Li(f"Capacity: {cap:,.0f} kW")]),
                    ],
                    None,
                )

        return default_inputs_panel(), None

    @app.callback(
        Output("inputs-techs-list", "children"),
        Input("dd-carrier", "value"),
        Input("inputs-selected-city", "data"),
        Input("applied-time", "data"),
        Input("dd-scenario", "value"),
    )
    def update_inputs_techs_list(selected_carrier, selected_city, rng: List[int], scenario="default"):
        data = app_data.get_scenario(scenario, selected_carrier)
        if not selected_city or not selected_carrier:
            return []

        city_name = selected_city

        n = data.INPUT_T
        i0, i1 = sorted([int(rng[0]), int(rng[1])])
        i0 = max(0, min(n - 1, i0))
        i1 = max(0, min(n - 1, i1))
        x = data.INPUT_TIMESTEPS[i0:i1 + 1] if len(data.INPUT_TIMESTEPS) else np.arange(i0, i1 + 1)
        index = pd.DatetimeIndex(x) if len(x) and isinstance(x[0], (pd.Timestamp, np.datetime64)) else pd.Index(x)
        max_points = 1200
        rule = compute_resample_rule(index, max_points) if isinstance(index, pd.DatetimeIndex) else None

        demand_arrays = [
            -1 * np.array(arr)[i0:i1 + 1] for arr in data.INPUT_HELPER.get_location_demand(city_name, selected_carrier)
        ]

        total_demand = None
        if len(demand_arrays) > 0:
            total_demand = np.sum(np.vstack(demand_arrays), axis=0)
            demand_series = downsample_series(
                pd.Series(total_demand, index=index),
                max_points=max_points,
                how=lambda values: values.sum(min_count=len(values)),
                rule=rule,
            )
            total_demand = demand_series.values
            x_demand = demand_series.index
        else:
            x_demand = index

        supply_dict = data.INPUT_HELPER.get_location_total_max_supply(city_name, selected_carrier)

        loc_techs = data.INPUT_HELPER.get_location_techs(city_name, selected_carrier)
        tech_names = sorted({x[1] for x in loc_techs})
        demand_techs = [t for t in tech_names if data.INPUT_HELPER.tech_is_demand(t)]
        supply_techs = [t for t in tech_names if f"{city_name}::{t}" in supply_dict]

        card_style = {
            "border": "1px solid #dce6e7",
            "borderRadius": "16px",
            "padding": "10px",
            "marginBottom": "12px",
            "backgroundColor": "#fff",
            "boxShadow": "none",
        }

        def apply_layout(fig: go.Figure, title: str) -> go.Figure:
            fig.update_layout(
                title=title,
                xaxis_title=f"Time · energy total per {interval_label(rule)}",
                yaxis_title="Energy (kWh)",
                hovermode="x unified",
                showlegend=False,
                margin=dict(t=40, r=10, b=20, l=40),
            )
            return style_detail_chart(fig)

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

        if total_demand is None:
            children.append(html.Div([
                html.H4(f"{selected_carrier.title()} demand"),
                html.Div("Not specified" if demand_techs else "0 kWh", className="inputs-empty-value"),
                html.P("A demand technology is defined without a fixed demand profile. Its demand may be constrained by bounds instead."
                         if demand_techs else
                         f"No fixed {selected_carrier} demand technology is defined at {city_name} in this scenario."),
            ], className="inputs-empty-card"))

        if not tech_names:
            children.append(html.Div([
                html.H4("Technologies"),
                html.P(f"No {selected_carrier} technologies are defined at {city_name} in this scenario."),
            ], className="inputs-empty-card"))
        elif not supply_techs:
            children.append(html.Div([
                html.H4("Direct supply technologies"),
                html.P("None are defined for this carrier at this location. Conversion, storage or transmission may still deliver energy where configured."),
            ], className="inputs-empty-card"))

        if total_demand is not None:
            fig_d = go.Figure()
            fig_d.add_trace(go.Scattergl(
                y=total_demand,
                x=x_demand,
                name="Demand",
                line=dict(width=2, color="#c0392b"),
                hovertemplate="%{y:.2f} kWh<extra>%{x}</extra>",
            ))
            fig_d = apply_layout(fig_d, f"Demand — {city_name} ({selected_carrier})")

            children.append(
                html.Div(
                    style=card_style,
                    children=[
                        html.H4("Demand", style={"marginBottom": "6px"}),
                        html.P(f"{'Known fixed demand' if np.isnan(demand_arrays).any() else 'Fixed demand'} in the selected period: {float(np.nansum(demand_arrays)):,.2f} kWh"),
                        html.P(f"Demand data is missing for {int(np.isnan(np.vstack(demand_arrays)).any(axis=0).sum())} selected timestep(s). The total is incomplete and affected intervals are shown as gaps.")
                        if np.isnan(demand_arrays).any() else None,
                        html.P("The defined demand profile is zero throughout the selected period.")
                        if not np.any(total_demand) else None,
                        html.P("Other demand technologies have no fixed profile; this chart covers fixed demand only.")
                        if len(demand_arrays) < len(demand_techs) else None,
                        dcc.Graph(responsive=True, config=DETAIL_CHART_CONFIG, figure=fig_d, style={"height": "240px", "width": "100%"}),
                    ],
                )
            )

        for tech in tech_names:
            arr = supply_dict.get(f"{city_name}::{tech}")
            if arr is None:
                continue
            selected_supply = np.asarray(arr)[i0:i1 + 1]
            missing_supply = int(np.isnan(selected_supply).sum())
            if np.isinf(selected_supply).any():
                costs = data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
                info = []
                add_info_li(info, "Output operating cost", costs.get("cost_om_prod"),
                            "Operating cost per unit of energy produced.", prefix="€", suffix=" per kWh")
                children.append(html.Div([
                    html.H4(tech), html.Ul(info),
                    html.P("Maximum supply has no finite upper bound in the model inputs; a finite maximum-supply curve cannot be shown."),
                ], style=card_style))
                continue

            supply_series = downsample_series(
                pd.Series(np.array(arr)[i0:i1 + 1], index=index),
                max_points=max_points,
                how=lambda values: values.sum(min_count=len(values)),
                rule=rule,
            )

            fig_s = go.Figure()
            fig_s.add_trace(go.Scattergl(
                y=supply_series.values,
                x=supply_series.index,
                name=f"{tech} Supply",
                line=dict(width=2, color="#245d7d"),
                hovertemplate="%{y:.2f} kWh<extra>%{x}</extra>",
            ))
            fig_s = apply_layout(fig_s, f"{tech} — {city_name} ({selected_carrier})")

            details_map = data.INPUT_HELPER.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
            cost_map = data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
            tech_children = []

            for key, value in details_map.items():
                val = _to_scalar(value)
                if val is None or math.isnan(val):
                    continue
                if key == "lifetime":
                    tech_children.append(html.Li(f"Lifetime: {val} years"))
                if key == "energy_cap_max":
                    tech_children.append(html.Li(f"Maximum power capacity: {val} kW"))
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
                "Calliope cost_flow_cap: investment cost per unit power capacity (EUR per kW).",
                prefix="€",
                suffix=" per kW",
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
                "Investment cost per unit power capacity and distance (EUR per kW per km).",
                prefix="€",
                suffix=" per kW per km",
            )
            add_info_li(
                tech_children,
                "Output operating cost",
                cost_map.get("cost_om_prod"),
                "Calliope cost_flow_out: operating cost per unit of energy produced (EUR per kWh).",
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
                        html.P(f"Resource data is missing for {missing_supply} selected timestep(s). Affected intervals are shown as gaps; no zero value is assumed.")
                        if missing_supply else None,
                        dcc.Graph(responsive=True, config=DETAIL_CHART_CONFIG, figure=fig_s, style={"height": "240px", "width": "100%"}),
                    ],
                )
            )

        conversion_techs = [t for t in tech_names if data.INPUT_HELPER.tech_is_conversion(t)]
        for tech in conversion_techs:
            # Keep both sides of a conversion visible even when the selected
            # physical carrier view contains only electricity or only heat.
            conversion_helper = app_data.get_scenario(scenario).INPUT_HELPER
            io_map = conversion_helper.get_conversion_tech_io(city_name, tech)
            carriers = {c for lst in io_map.values() for c in lst}
            if not carriers or selected_carrier not in carriers:
                continue

            base_cap = _to_scalar(conversion_helper.get_loc_tech_capacity(city_name, tech))
            if base_cap is not None and not np.isfinite(base_cap):
                base_cap = None
            eff_arr = conversion_helper.get_loc_tech_energy_eff(city_name, tech)
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

            ratio_map = conversion_helper.get_conversion_carrier_ratios(city_name, tech)
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

            style_detail_chart(sankey_fig, axes=False)

            tech_children = []
            if inputs:
                tech_children.append(html.Li(f"Inputs: {', '.join(inputs)}"))
            if outputs:
                tech_children.append(html.Li(f"Outputs: {', '.join(outputs)}"))
            if input_max is not None and not math.isnan(input_max):
                tech_children.append(html.Li(f"Max input: {input_max:.0f} kW"))
            if base_cap is not None and not math.isnan(base_cap):
                for carrier in primary_out:
                    tech_children.append(html.Li(f"Max output ({carrier}): {base_cap:.0f} kW"))
                for carrier in secondary_out:
                    ratio = ratio_map.get(("out_2", carrier), 1.0)
                    tech_children.append(html.Li(f"Max output ({carrier}): {base_cap * ratio:.0f} kW"))

            details_map = data.INPUT_HELPER.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
            cost_map = data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
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
                "Calliope cost_flow_cap: investment cost per unit power capacity (EUR per kW).",
                prefix="€",
                suffix=" per kW",
            )

            details = html.Ul(children=tech_children)
            children.append(
                html.Div(
                    style=card_style,
                    children=[
                        html.H4(tech, style={"marginBottom": "6px"}),
                        details,
                        dcc.Graph(responsive=True, config=DETAIL_CHART_CONFIG, figure=sankey_fig, style={"height": "220px", "width": "100%"})
                        if base_cap is not None and base_cap > 0 else
                        html.P("Maximum conversion power is not specified; no maximum-flow diagram is shown."
                                 if base_cap is None else "Configured conversion power is 0 kW."),
                    ],
                )
            )

        for tech in tech_names:
            if data.INPUT_HELPER.tech_is_storage(tech):
                details_map = data.INPUT_HELPER.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
                cost_map = data.INPUT_HELPER.get_loc_tech_costs(city_name, tech)
                tech_children = []

                for key, value in details_map.items():
                    val = _to_scalar(value)
                    if val is None or math.isnan(val):
                        continue
                    if key == "lifetime":
                        tech_children.append(html.Li(f"Lifetime: {val} years"))
                    if key == "energy_cap_max":
                        tech_children.append(html.Li(f"Maximum discharge power: {val} kW"))
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
                    "Calliope cost_flow_cap: investment cost per unit power capacity (EUR per kW).",
                    prefix="€",
                    suffix=" per kW",
                )
                add_info_li(
                    tech_children,
                    "Storage capacity cost",
                    cost_map.get("cost_storage_cap"),
                    "Calliope cost_storage_cap: investment per unit stored-energy capacity (EUR per kWh).",
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
                    "Investment cost per unit power capacity and distance (EUR per kW per km).",
                    prefix="€",
                    suffix=" per kW per km",
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
