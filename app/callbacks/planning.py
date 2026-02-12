from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State

import app_data
from figures import downsample_grouped_frame, downsample_series, empty_figure, format_number, kpi_tile

OTHER_TECH_COLOR = "#b3b3b3"


def _hex_to_rgba(color: str, alpha: float) -> str:
    color = color.strip()
    if not color.startswith("#"):
        return color
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join([c * 2 for c in value])
    if len(value) != 6:
        return color
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _apply_alpha(color: Optional[str], alpha: float) -> Optional[str]:
    if not color:
        return None
    return _hex_to_rgba(color, alpha)


def register_planning_callbacks(app):
    @app.callback(
        Output("plan-selector-label", "children"),
        Output("plan-location-dd", "style"),
        Output("plan-tech-dd", "style"),
        Output("plan-location-dd", "value"),
        Output("plan-tech-dd", "value"),
        Input("plan-view-mode", "value"),
        State("plan-location-dd", "value"),
        State("plan-tech-dd", "value"),
    )
    def update_plan_selector(view_mode: str, current_loc: str, current_tech: str):
        if view_mode == "technology":
            tech_val = current_tech if current_tech in app_data.PLAN_TECHS else (app_data.PLAN_TECHS[0] if app_data.PLAN_TECHS else None)
            loc_val = current_loc if current_loc in app_data.PLAN_LOCATIONS else (app_data.PLAN_LOCATIONS[0] if app_data.PLAN_LOCATIONS else None)
            return (
                "Select technology",
                {"width": "260px", "display": "none"},
                {"width": "260px", "display": "block"},
                loc_val,
                tech_val,
            )
        loc_val = current_loc if current_loc in app_data.PLAN_LOCATIONS else (app_data.PLAN_LOCATIONS[0] if app_data.PLAN_LOCATIONS else None)
        tech_val = current_tech if current_tech in app_data.PLAN_TECHS else (app_data.PLAN_TECHS[0] if app_data.PLAN_TECHS else None)
        return (
            "Select location",
            {"width": "260px", "display": "block"},
            {"width": "260px", "display": "none"},
            loc_val,
            tech_val,
        )

    @app.callback(
        Output("plan-kpi-strip", "children"),
        Output("plan-capacity-bar", "figure"),
        Output("plan-cost-breakdown", "figure"),
        Output("plan-co2-breakdown", "figure"),
        Output("plan-co2-ts", "figure"),
        Output("plan-production-ts", "figure"),
        Output("plan-detail-table", "columns"),
        Output("plan-detail-table", "data"),
        Input("dd-scenario", "value"),
        Input("dd-carrier", "value"),
        Input("rs-time", "value"),
        Input("plan-view-mode", "value"),
        Input("plan-location-dd", "value"),
        Input("plan-tech-dd", "value"),
        Input("plan-cost-norm", "value"),
    )
    def update_plan_dashboard(
        scenario: str,
        carrier: str,
        rng: List[int],
        view_mode: str,
        selected_location: str,
        selected_tech: str,
        cost_norm: str,
    ):
        scenario_key = app_data.RESULTS_HELPER.normalize_scenario(str(scenario))
        carrier_key = app_data.RESULTS_HELPER.normalize_carrier(str(carrier))
        carrier_label = app_data.RESULTS_HELPER.carrier_label(carrier_key)

        i0, i1 = sorted([int(rng[0]), int(rng[1])])
        i0 = max(0, min(app_data.T - 1, i0))
        i1 = max(0, min(app_data.T - 1, i1))
        start_ts = app_data.TIME_INDEX[i0]
        end_ts = app_data.TIME_INDEX[i1]

        selection = app_data.RESULTS_HELPER.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        tech_color_map = app_data.RESULTS_HELPER.get_technology_color_map()

        def resolve_tech_color(label: str, alpha: Optional[float] = None) -> Optional[str]:
            if group_key != "technology":
                return None
            base = OTHER_TECH_COLOR if label == "Other" else tech_color_map.get(label)
            if alpha is None:
                return base
            return _apply_alpha(base, alpha)

        kpi_vals = app_data.RESULTS_HELPER.get_plan_kpis(
            scenario_id=scenario_key,
            carrier=carrier_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )

        kpis = [
            kpi_tile("Investments (CAPEX)", f"€{format_number(kpi_vals['capex'])}"),
            kpi_tile("Operating costs (OPEX)", f"€{format_number(kpi_vals['opex'])}"),
            kpi_tile("Installed capacity", f"{format_number(kpi_vals['capacity'])} kW"),
            kpi_tile(f"Production ({carrier_label})", f"{format_number(kpi_vals['production'])} kWh"),
            kpi_tile("CO2 emissions", f"{format_number(kpi_vals['co2_kg'])} kg"),
        ]

        cap_group = app_data.RESULTS_HELPER.get_plan_capacity_group(
            scenario_id=scenario_key,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        order_keys = cap_group[group_key].tolist() if not cap_group.empty else []
        if cap_group.empty:
            cap_fig = empty_figure("No data for the current selection.")
        else:
            cap_fig = go.Figure()
            bar_colors = [resolve_tech_color(label) for label in cap_group[group_key]] if group_key == "technology" else None
            cap_fig.add_trace(go.Bar(x=cap_group[group_key], y=cap_group["built_capacity_kw"], marker_color=bar_colors))
            title = "Installed capacity by technology (kW)" if view_mode == "location" else "Installed capacity by location (kW)"
            cap_fig.update_layout(
                title=title,
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
                xaxis_title=group_key.title(),
                yaxis_title="kW",
            )

        cost_group = app_data.RESULTS_HELPER.get_plan_cost_group(
            scenario_id=scenario_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        if order_keys:
            cost_group[group_key] = pd.Categorical(cost_group[group_key], categories=order_keys, ordered=True)
            cost_group = cost_group.sort_values(group_key)

        if cost_group.empty:
            cost_fig = empty_figure("No data for the current selection.")
        else:
            if cost_norm == "per_kw":
                denom = cost_group["built_capacity_kw"].replace({0: np.nan})
                cost_group["capex_eur"] = cost_group["capex_eur"] / denom
                cost_group["fixed_opex_eur"] = cost_group["fixed_opex_eur"] / denom
                cost_group["variable_opex_eur"] = cost_group["variable_opex_eur"] / denom
                cost_group = cost_group.fillna(0.0)
                y_title = "€/kW"
            else:
                y_title = "€"

            cost_fig = go.Figure()
            base_colors = [resolve_tech_color(label) for label in cost_group[group_key]] if group_key == "technology" else None
            capex_colors = [_apply_alpha(c, 0.95) for c in base_colors] if base_colors else None
            fixed_colors = [_apply_alpha(c, 0.65) for c in base_colors] if base_colors else None
            var_colors = [_apply_alpha(c, 0.4) for c in base_colors] if base_colors else None
            cost_fig.add_trace(go.Bar(x=cost_group[group_key], y=cost_group["capex_eur"], name="CAPEX", marker_color=capex_colors))
            cost_fig.add_trace(go.Bar(x=cost_group[group_key], y=cost_group["fixed_opex_eur"], name="Fixed OPEX", marker_color=fixed_colors))
            cost_fig.add_trace(go.Bar(x=cost_group[group_key], y=cost_group["variable_opex_eur"], name="Variable OPEX", marker_color=var_colors))
            cost_fig.update_layout(
                barmode="stack",
                title="Cost breakdown (€)" if cost_norm == "absolute" else "Cost breakdown (€/kW)",
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
                yaxis_title=y_title,
                xaxis_title=group_key.title(),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

        co2_group = app_data.RESULTS_HELPER.get_plan_co2_group(
            scenario_id=scenario_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        if order_keys and not co2_group.empty:
            co2_group[group_key] = pd.Categorical(co2_group[group_key], categories=order_keys, ordered=True)
            co2_group = co2_group.sort_values(group_key)

        if co2_group.empty:
            co2_fig = empty_figure("No CO2 data for the current selection.")
        else:
            co2_fig = go.Figure()
            co2_colors = [resolve_tech_color(label) for label in co2_group[group_key]] if group_key == "technology" else None
            co2_fig.add_trace(go.Bar(x=co2_group[group_key], y=co2_group["co2_kg"], name="CO2", marker_color=co2_colors))
            co2_fig.update_layout(
                title="CO2 breakdown (kg)",
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
                yaxis_title="kg",
                xaxis_title=group_key.title(),
            )

        co2_series = app_data.RESULTS_HELPER.get_plan_co2_timeseries(
            scenario_id=scenario_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        if co2_series.empty:
            co2_ts_fig = empty_figure("No CO2 data for the current selection.")
        else:
            co2_series = downsample_grouped_frame(
                co2_series,
                time_col="timestamp",
                value_col="co2_kg",
                group_col="group_label",
                max_points=1200,
                how="mean",
            )
            co2_ts_fig = go.Figure()
            for label in co2_series["group_label"].unique():
                sub = co2_series[co2_series["group_label"] == label]
                line_color = resolve_tech_color(label) if group_key == "technology" else None
                trace_kwargs = dict(x=sub["timestamp"], y=sub["co2_kg"], mode="lines", name=label)
                if line_color:
                    trace_kwargs["line"] = dict(color=line_color)
                co2_ts_fig.add_trace(go.Scattergl(**trace_kwargs))
            co2_ts_fig.update_layout(
                title="CO2 over time",
                height=260,
                margin=dict(l=10, r=10, t=45, b=30),
                xaxis_title="Time",
                yaxis=dict(title="kg", rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

        prod_series = app_data.RESULTS_HELPER.get_plan_production_timeseries(
            scenario_id=scenario_key,
            carrier=carrier_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        if prod_series.empty:
            prod_fig = empty_figure("No data for the current selection.")
        else:
            prod_series = downsample_grouped_frame(
                prod_series,
                time_col="timestamp",
                value_col="energy_kwh",
                group_col="group_label",
                max_points=1200,
                how="mean",
            )
            prod_fig = go.Figure()
            for label in prod_series["group_label"].unique():
                sub = prod_series[prod_series["group_label"] == label]
                line_color = resolve_tech_color(label) if group_key == "technology" else None
                trace_kwargs = dict(x=sub["timestamp"], y=sub["energy_kwh"], mode="lines", name=label)
                if line_color:
                    trace_kwargs["line"] = dict(color=line_color)
                prod_fig.add_trace(go.Scattergl(**trace_kwargs))
            demand_series = app_data.RESULTS_HELPER.get_plan_demand_timeseries(
                scenario_id=scenario_key,
                carrier=carrier_key,
                start_ts=start_ts,
                end_ts=end_ts,
                view_mode=view_mode,
                selected_location=selected_location,
                selected_tech=selected_tech,
            )
            if not demand_series.empty:
                demand_series = (
                    downsample_series(
                        demand_series.set_index("timestamp")["demand_kwh"].sort_index(),
                        max_points=1200,
                        how="mean",
                    )
                    .reset_index()
                    .rename(columns={"demand_kwh": "demand_kwh"})
                )
                prod_fig.add_trace(
                    go.Scattergl(
                        x=demand_series["timestamp"],
                        y=demand_series["demand_kwh"],
                        mode="lines",
                        name="Demand",
                        line=dict(color="#c0392b", dash="dash", width=2),
                    )
                )
            prod_title = "CO2 over time" if carrier_key.lower() == "co2" else "Production over time"
            prod_fig.update_layout(
                title=prod_title,
                height=340,
                margin=dict(l=10, r=10, t=45, b=30),
                xaxis_title="Time",
                yaxis=dict(title="kWh", rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

        table = app_data.RESULTS_HELPER.get_plan_detail_table(
            scenario_id=scenario_key,
            carrier=carrier_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )

        columns = [
            {"name": "Name", "id": "Name"},
            {"name": "Installed capacity (kW)", "id": "built_capacity_kw"},
            {"name": "CAPEX (€)", "id": "capex_eur"},
            {"name": "OPEX fixed (€)", "id": "fixed_opex_eur"},
            {"name": "OPEX variable (€)", "id": "variable_opex_eur"},
            {"name": "CO2 (kg)", "id": "co2_kg"},
            {"name": f"Production ({carrier_label}) kWh", "id": "energy_kwh"},
            {"name": "Capacity factor", "id": "capacity_factor"},
        ]

        def fmt_table_row(row):
            row["built_capacity_kw"] = format_number(row["built_capacity_kw"])
            row["capex_eur"] = format_number(row["capex_eur"])
            row["fixed_opex_eur"] = format_number(row["fixed_opex_eur"])
            row["variable_opex_eur"] = format_number(row["variable_opex_eur"])
            row["co2_kg"] = format_number(row.get("co2_kg", 0.0))
            row["energy_kwh"] = format_number(row["energy_kwh"])
            row["capacity_factor"] = f"{row['capacity_factor'] * 100:.1f}%"
            if "co2_kwh" in row:
                row["co2_kwh"] = format_number(row["co2_kwh"])
            return row

        data = [fmt_table_row(row) for row in table.to_dict("records")]

        return kpis, cap_fig, cost_fig, co2_fig, co2_ts_fig, prod_fig, columns, data
