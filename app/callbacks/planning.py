from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State

from app import app_data
from app.figures import (
    downsample_grouped_frame,
    downsample_series,
    empty_figure,
    format_number,
    kpi_tile,
)
from helpers.results_helper import ALL_LOCATIONS

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
        Output("plan-tech-dd", "options"),
        Input("plan-view-mode", "value"),
        Input("dd-carrier", "value"),
        Input("dd-scenario", "value"),
        State("plan-location-dd", "value"),
        State("plan-tech-dd", "value"),
    )
    def update_plan_selector(view_mode: str, carrier, scenario, current_loc: str, current_tech: str):
        techs = app_data.get_scenario(scenario, carrier).RESULTS_HELPER.get_technologies()
        options = [{"label": tech, "value": tech} for tech in techs]
        if view_mode == "technology":
            tech_val = current_tech if current_tech in techs else (techs[0] if techs else None)
            valid_locations = [ALL_LOCATIONS, *app_data.PLAN_LOCATIONS]
            loc_val = current_loc if current_loc in valid_locations else ALL_LOCATIONS
            return (
                "Select technology",
                {"width": "100%", "display": "none"},
                {"width": "100%", "display": "block"},
                loc_val,
                tech_val,
                options,
            )
        valid_locations = [ALL_LOCATIONS, *app_data.PLAN_LOCATIONS]
        loc_val = current_loc if current_loc in valid_locations else ALL_LOCATIONS
        tech_val = current_tech if current_tech in techs else (techs[0] if techs else None)
        return (
            "Select location",
            {"width": "100%", "display": "block"},
            {"width": "100%", "display": "none"},
            loc_val,
            tech_val,
            options,
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
        Input("applied-time", "data"),
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
        data = app_data.get_scenario(scenario, carrier)
        scenario_key = data.RESULTS_HELPER.normalize_scenario(str(scenario))
        carrier_key = data.RESULTS_HELPER.normalize_carrier(str(carrier))
        carrier_label = data.RESULTS_HELPER.carrier_label(carrier_key)

        i0, i1 = sorted([int(rng[0]), int(rng[1])])
        i0 = max(0, min(data.T - 1, i0))
        i1 = max(0, min(data.T - 1, i1))
        start_ts = data.TIME_INDEX[i0]
        end_ts = data.TIME_INDEX[i1]

        selection = data.RESULTS_HELPER.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        tech_color_map = data.RESULTS_HELPER.get_technology_color_map()

        def resolve_tech_color(label: str, alpha: Optional[float] = None) -> Optional[str]:
            if group_key != "technology":
                return None
            base = OTHER_TECH_COLOR if label == "Other" else tech_color_map.get(label)
            if alpha is None:
                return base
            return _apply_alpha(base, alpha)

        kpi_vals = data.RESULTS_HELPER.get_plan_kpis(
            scenario_id=scenario_key,
            carrier=carrier_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )

        kpis = [
            kpi_tile("Carrier-exclusive modeled cost", f"€{format_number(kpi_vals['total_cost'])}", help_id="plan-help-cost", help_text="Cost for the selected period: the period's share of annualised investment, fixed and variable operating costs, and any other modeled costs. Excludes shared costs of technologies linked to multiple carriers."),
            kpi_tile("CAPEX (carrier-exclusive)", f"€{format_number(kpi_vals['capex'])}", help_id="plan-help-capex", help_text="Upfront investment in the selected assets, not the share allocated to the selected period. Excludes shared costs of technologies linked to multiple carriers."),
            kpi_tile("OPEX (carrier-exclusive)", f"€{format_number(kpi_vals['opex'])}", help_id="plan-help-opex", help_text="Fixed and variable operating costs for the selected period. Excludes shared costs of technologies linked to multiple carriers."),
            kpi_tile("Installed capacity", f"{format_number(kpi_vals['capacity'])} kW", help_id="plan-help-capacity", help_text="Total installed capacity of the selected assets. It does not change when you select a shorter time period."),
            kpi_tile(f"Production ({carrier_label})", f"{format_number(kpi_vals['production'])} kWh", help_id="plan-help-production", help_text="Total output of the selected carrier from the selected assets during the selected period."),
            kpi_tile("CO2 emissions", f"{format_number(kpi_vals['co2_kg'])} kg" if "co2" in data.LOADED_RESULTS.costs else "Not provided", help_id="plan-help-co2", help_text="Modeled operational emissions plus the selected period's share of investment-related emissions. Not provided means the model has no CO2 cost class; it does not mean zero emissions."),
        ]

        cap_group = data.RESULTS_HELPER.get_plan_capacity_group(
            scenario_id=scenario_key,
            carrier=carrier_key,
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
            if bar_colors and any(c is None for c in bar_colors):
                bar_colors = None
            cap_fig.add_trace(go.Bar(
                x=cap_group[group_key], y=cap_group["carrier_capacity_kw"],
                orientation="v", marker_color=bar_colors,
                hovertemplate="%{x}<br>%{y:,.6f} kW<extra></extra>",
            ))
            cap_fig.update_layout(
                title=None,
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
                xaxis_title=group_key.title(),
                yaxis_title="kW",
            )

        cost_group = data.RESULTS_HELPER.get_plan_cost_group(
            scenario_id=scenario_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        if order_keys:
            cost_order = order_keys + [k for k in cost_group[group_key].unique() if k not in order_keys]
            cost_group[group_key] = pd.Categorical(cost_group[group_key], categories=cost_order, ordered=True)
            cost_group = cost_group.sort_values(group_key)
        if cost_norm == "per_kw":
            cost_group = cost_group[cost_group.built_capacity_kw > 0].copy()

        if cost_group.empty:
            cost_fig = empty_figure("No data for the current selection.")
        else:
            if cost_norm == "per_kw":
                denom = cost_group["built_capacity_kw"].replace({0: np.nan})
                cost_group["annualised_investment_eur"] = cost_group["annualised_investment_eur"] / denom
                cost_group["fixed_opex_eur"] = cost_group["fixed_opex_eur"] / denom
                cost_group["variable_opex_eur"] = cost_group["variable_opex_eur"] / denom
                cost_group["other_costs_eur"] = cost_group["other_costs_eur"] / denom
                cost_group[["annualised_investment_eur", "fixed_opex_eur", "variable_opex_eur"]] = cost_group[
                    ["annualised_investment_eur", "fixed_opex_eur", "variable_opex_eur"]
                ].fillna(0.0)
                y_title = "€/kW"
            else:
                y_title = "€"

            cost_fig = go.Figure()
            # Hue follows the model technology; opacity encodes the cost type.
            # Neutral proxy swatches explain opacity without suggesting that a
            # cost component has one technology's hue. Grouped legend clicks
            # still toggle the matching component across every bar.
            base_colors = [
                (OTHER_TECH_COLOR if label == "Other" else tech_color_map.get(label, OTHER_TECH_COLOR))
                if group_key == "technology"
                else tech_color_map.get(selection["selection_value"], OTHER_TECH_COLOR)
                for label in cost_group[group_key]
            ]
            components = [
                ("annualised_investment_eur", "Annualised investment", 0.95),
                ("fixed_opex_eur", "Fixed OPEX", 0.65),
                ("variable_opex_eur", "Variable OPEX", 0.4),
            ]
            if cost_group.other_costs_eur.abs().max() > 1e-6:
                components.append(("other_costs_eur", "Other / residual", 0.25))
            for column, label, alpha in components:
                cost_fig.add_trace(go.Bar(
                    x=cost_group[group_key], y=cost_group[column],
                    orientation="v", name=label, legendgroup=column,
                    showlegend=False,
                    marker_color=[_apply_alpha(color, alpha) for color in base_colors],
                ))
            for column, label, alpha in components:
                cost_fig.add_trace(go.Bar(
                    x=[cost_group[group_key].iloc[0]], y=[None], orientation="v", name=label,
                    legendgroup=column, showlegend=True, hoverinfo="skip",
                    marker_color=_apply_alpha("#526477", alpha),
                ))
            cost_fig.update_traces(hovertemplate=f"%{{x}}<br>%{{y:,.9f}} {y_title}<extra>%{{fullData.name}}</extra>")
            cost_fig.update_layout(
                barmode="relative",
                # The card heading and axis already describe the cost units.
                # A second title collides with the wrapped legend on laptops.
                title=None,
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
                xaxis_title=group_key.title(),
                yaxis_title=y_title,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    title=dict(text="Hue = technology · shade = cost type", side="top"),
                    groupclick="togglegroup",
                ),
            )

        co2_group = data.RESULTS_HELPER.get_plan_co2_group(
            scenario_id=scenario_key,
            start_ts=start_ts,
            end_ts=end_ts,
            view_mode=view_mode,
            selected_location=selected_location,
            selected_tech=selected_tech,
        )
        if order_keys and not co2_group.empty:
            co2_order = order_keys + [k for k in co2_group[group_key].unique() if k not in order_keys]
            co2_group[group_key] = pd.Categorical(co2_group[group_key], categories=co2_order, ordered=True)
            co2_group = co2_group.sort_values(group_key)

        if co2_group.empty:
            co2_fig = empty_figure("No CO2 data for the current selection.")
        else:
            co2_fig = go.Figure()
            co2_colors = [resolve_tech_color(label) for label in co2_group[group_key]] if group_key == "technology" else None
            if co2_colors and any(c is None for c in co2_colors):
                co2_colors = None
            co2_fig.add_trace(go.Bar(
                x=co2_group[group_key], y=co2_group["co2_kg"], orientation="v",
                name="CO2", marker_color=co2_colors, width=0.35,
                hovertemplate="%{x}<br>%{y:,.6f} kg<extra></extra>",
            ))
            co2_fig.update_layout(
                title=None,
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
                xaxis_title=group_key.title(),
                yaxis_title="kg",
            )

        co2_series = data.RESULTS_HELPER.get_plan_co2_timeseries(
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
                how="sum",
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
                title=None,
                height=260,
                margin=dict(l=10, r=10, t=45, b=30),
                xaxis_title=f"Time · CO2 total per {co2_series.attrs['interval']}",
                yaxis=dict(title="kg", rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

        prod_series = data.RESULTS_HELPER.get_plan_production_timeseries(
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
                how="sum",
            )
            prod_fig = go.Figure()
            for label in prod_series["group_label"].unique():
                sub = prod_series[prod_series["group_label"] == label]
                line_color = resolve_tech_color(label) if group_key == "technology" else None
                trace_kwargs = dict(x=sub["timestamp"], y=sub["energy_kwh"], mode="lines", name=label)
                if line_color:
                    trace_kwargs["line"] = dict(color=line_color)
                prod_fig.add_trace(go.Scattergl(**trace_kwargs))
            demand_series = data.RESULTS_HELPER.get_plan_demand_timeseries(
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
                        how="sum",
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
            prod_fig.update_layout(
                title="CO2 over time" if carrier_key.lower() == "co2" else None,
                height=340,
                margin=dict(l=10, r=10, t=45, b=30),
                xaxis_title=f"Time · energy total per {prod_series.attrs['interval']}",
                yaxis=dict(title="kWh", rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

        table = data.RESULTS_HELPER.get_plan_detail_table(
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

        from dash.dash_table.Format import Format, Scheme, Group
        for column in columns:
            if column["id"] != "Name":
                column.update(type="numeric", format=Format(precision=6, scheme=Scheme.fixed, group=Group.yes))
        columns[-1]["format"] = Format(precision=2, scheme=Scheme.percentage)
        data = table.to_dict("records")

        # Use the same quiet plot treatment across all planning figures.
        for fig in (cap_fig, cost_fig, co2_fig, co2_ts_fig, prod_fig):
            fig.update_layout(
                paper_bgcolor="white", plot_bgcolor="white",
                font=dict(family="Geist, Arial, sans-serif", size=12, color="#526477"),
                hoverlabel=dict(bgcolor="white", font_color="#263648"),
            )
            fig.update_xaxes(automargin=True, showgrid=False, zeroline=False, linecolor="#dce5ee")
            fig.update_yaxes(automargin=True, gridcolor="#e9edf2", zeroline=False)

        # Compare the series at one timestamp in a shared hover panel.
        for fig, unit in ((prod_fig, "kWh"), (co2_ts_fig, "kg")):
            if fig.data:
                fig.update_layout(hovermode="x unified", hoverlabel=dict(namelength=-1))
                fig.update_traces(hovertemplate=f"%{{y:,.6f}} {unit}<extra>%{{fullData.name}}</extra>")
                fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#9aafb5")

        # Keep category labels readable while retaining vertical bars.
        for fig in (cap_fig, cost_fig, co2_fig):
            fig.update_layout(margin=dict(l=10, r=16, t=35, b=35), bargap=0.28)
            fig.update_xaxes(automargin=True, tickfont=dict(size=11))
            fig.update_yaxes(showgrid=True, gridcolor="#e9edf2", zeroline=True, zerolinecolor="#dce5ee")

        if not cost_group.empty:
            cost_fig.update_layout(height=360, margin=dict(t=100))

        return kpis, cap_fig, cost_fig, co2_fig, co2_ts_fig, prod_fig, columns, data
