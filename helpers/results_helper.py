"""Accessors for Calliope 0.7 planning results."""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import xarray as xr

ALL_LOCATIONS = "__all_locations__"


class ResultsHelper:
    """Prepare the planning data used by the dashboard callbacks."""

    def __init__(self, results: xr.Dataset, inputs: Optional[xr.Dataset] = None) -> None:
        assert isinstance(results, xr.Dataset)
        assert str(results.attrs.get("calliope_version", "")).startswith("0.7.0")
        self.results = results
        self.inputs = inputs
        self._scenario_ids = ["default"]
        self._time_index = pd.DatetimeIndex(pd.to_datetime(results.timesteps.values))
        self._tech_name_map = self._tech_map("name")
        self._tech_category_map = self._tech_map("base_tech")
        self._tech_color_map = self._tech_map("color")
        self._plan_ts_cache: Dict[tuple, pd.DataFrame] = {}
        self._assets_df: Optional[pd.DataFrame] = None
        self._energy_df: Optional[pd.DataFrame] = None
        self._con_df: Optional[pd.DataFrame] = None
        self._var_cost_df: Optional[pd.DataFrame] = None
        self._emissions_df: Optional[pd.DataFrame] = None
        self._demand_df: Optional[pd.DataFrame] = None

    def _tech_map(self, variable: str) -> Dict[str, str]:
        if self.inputs is None or variable not in self.inputs:
            return {}
        return {
            str(tech): str(value)
            for tech, value in zip(self.inputs.techs.values, self.inputs[variable].values)
        }

    def _humanize_tech(self, tech: str) -> str:
        return self._tech_name_map.get(str(tech), str(tech))

    def _is_transmission(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "transmission"

    def _is_conversion(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "conversion"

    def _is_demand(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "demand"

    def _cost_key(self, dataset: xr.Dataset) -> Optional[str]:
        if "costs" not in dataset.coords:
            return None
        costs = [str(value) for value in dataset.costs.values]
        return "monetary" if "monetary" in costs else (costs[0] if costs else None)

    def _to_frame(self, array: xr.DataArray, value_name: str, cost: Optional[str] = None) -> pd.DataFrame:
        if "costs" in array.dims:
            cost_key = cost or self._cost_key(array.to_dataset(name=value_name))
            if cost_key is not None:
                array = array.sel(costs=cost_key)
        frame = array.to_series().rename(value_name).reset_index()
        frame["scenario_id"] = "default"
        return frame

    def _filter_time(
        self,
        frame: pd.DataFrame,
        start_ts: Optional[pd.Timestamp],
        end_ts: Optional[pd.Timestamp],
    ) -> pd.DataFrame:
        if start_ts is not None:
            frame = frame[frame["timestamp"] >= start_ts]
        if end_ts is not None:
            frame = frame[frame["timestamp"] <= end_ts]
        return frame

    def _filter_by_input_matrix(
        self, frame: pd.DataFrame, variable: str = "definition_matrix"
    ) -> pd.DataFrame:
        """Keep only node/tech/carrier combinations enabled in the inputs."""
        if self.inputs is None or variable not in self.inputs:
            return frame
        enabled = self.inputs[variable].to_series().rename("_enabled").reset_index()
        # Calliope serialises boolean arrays as int8 in NetCDF. h5netcdf keeps
        # those 0/1 values as integers, so explicitly turn them back into a
        # boolean mask before filtering rows.
        enabled = enabled[enabled["_enabled"].astype(bool)].rename(
            columns={"nodes": "location", "techs": "technology_raw", "carriers": "carrier"}
        )
        keys = [key for key in ("location", "technology_raw", "carrier") if key in frame]
        return frame.merge(enabled[keys].drop_duplicates(), on=keys, how="inner")

    def _window_fraction(self, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> float:
        selected = self._time_index[(self._time_index >= start_ts) & (self._time_index <= end_ts)]
        return len(selected) / max(1, len(self._time_index))

    def _hours_in_window(self, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> float:
        selected = self._time_index[(self._time_index >= start_ts) & (self._time_index <= end_ts)]
        if len(selected) > 1:
            step_hours = (selected[1] - selected[0]).total_seconds() / 3600
        else:
            step_hours = 1.0
        return max(1.0, len(selected) * step_hours)

    def _build_assets_df(self) -> pd.DataFrame:
        columns = [
            "scenario_id", "location", "technology", "technology_raw",
            "built_capacity_kw", "capex_eur", "fixed_opex_eur", "category",
        ]
        if "flow_cap" not in self.results:
            return pd.DataFrame(columns=columns)

        capacity = self._to_frame(self.results.flow_cap, "built_capacity_kw")
        capacity = capacity.rename(columns={"nodes": "location", "techs": "technology_raw"})
        capacity = self._filter_by_input_matrix(capacity)
        capacity["built_capacity_kw"] = capacity["built_capacity_kw"].fillna(0.0)
        capacity = capacity.groupby(
            ["scenario_id", "location", "technology_raw"], as_index=False
        )["built_capacity_kw"].max()

        def cost_frame(variable: str, value_name: str) -> pd.DataFrame:
            if variable not in self.results:
                return pd.DataFrame(columns=["scenario_id", "location", "technology_raw", value_name])
            frame = self._to_frame(self.results[variable], value_name)
            frame = frame.rename(columns={"nodes": "location", "techs": "technology_raw"})
            return frame.groupby(
                ["scenario_id", "location", "technology_raw"], as_index=False
            )[value_name].sum()

        capex = cost_frame("cost_investment", "capex_eur")
        total = cost_frame("cost", "total_cost_eur")
        annualised = cost_frame("cost_investment_annualised", "annualised_investment_eur")

        assets = capacity.merge(capex, how="left")
        assets = assets.merge(total, how="left")
        assets = assets.merge(annualised, how="left")
        assets = assets.fillna(0.0)

        variable = self._build_variable_cost_df()
        variable_total = variable.groupby(
            ["scenario_id", "location", "technology_raw"], as_index=False
        )["variable_opex_eur"].sum()
        assets = assets.merge(variable_total, how="left").fillna(0.0)
        assets["fixed_opex_eur"] = (
            assets["total_cost_eur"]
            - assets["annualised_investment_eur"]
            - assets["variable_opex_eur"]
        ).clip(lower=0.0)
        assets["technology"] = assets["technology_raw"].map(self._humanize_tech)
        assets["category"] = assets["technology_raw"].map(self._tech_category_map).fillna("")
        assets = assets[~assets["technology_raw"].map(self._is_transmission)]
        return assets[columns]

    def _build_flow_df(self, variable: str) -> pd.DataFrame:
        columns = [
            "scenario_id", "timestamp", "location", "technology",
            "technology_raw", "carrier", "energy_kwh",
        ]
        if variable not in self.results:
            return pd.DataFrame(columns=columns)
        frame = self._to_frame(self.results[variable], "energy_kwh")
        frame = frame.rename(
            columns={
                "nodes": "location",
                "techs": "technology_raw",
                "carriers": "carrier",
                "timesteps": "timestamp",
            }
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["energy_kwh"] = frame["energy_kwh"].fillna(0.0).abs()
        frame["technology"] = frame["technology_raw"].map(self._humanize_tech)
        role = "carrier_out" if variable == "flow_out" else "carrier_in"
        frame = self._filter_by_input_matrix(frame, role)
        frame = frame[~frame["technology_raw"].map(self._is_transmission)]
        return frame[columns]

    def _build_energy_df(self) -> pd.DataFrame:
        return self._build_flow_df("flow_out")

    def _build_consumption_df(self) -> pd.DataFrame:
        return self._build_flow_df("flow_in")

    def _build_variable_cost_df(self) -> pd.DataFrame:
        columns = [
            "scenario_id", "timestamp", "location", "technology",
            "technology_raw", "variable_opex_eur",
        ]
        if "cost_operation_variable" not in self.results:
            return pd.DataFrame(columns=columns)
        frame = self._to_frame(self.results.cost_operation_variable, "variable_opex_eur")
        frame = frame.rename(
            columns={"nodes": "location", "techs": "technology_raw", "timesteps": "timestamp"}
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["variable_opex_eur"] = frame["variable_opex_eur"].fillna(0.0)
        frame["technology"] = frame["technology_raw"].map(self._humanize_tech)
        frame = self._filter_by_input_matrix(frame)
        frame = frame[~frame["technology_raw"].map(self._is_transmission)]
        return frame[columns]

    def _build_emissions_df(self) -> pd.DataFrame:
        columns = [
            "scenario_id", "timestamp", "location", "technology",
            "technology_raw", "co2_kg",
        ]
        if "cost_operation_variable" not in self.results or "co2" not in self.results.costs:
            return pd.DataFrame(columns=columns)
        frame = self._to_frame(
            self.results.cost_operation_variable, "co2_kg", cost="co2"
        )
        frame = frame.rename(
            columns={"nodes": "location", "techs": "technology_raw", "timesteps": "timestamp"}
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["co2_kg"] = frame["co2_kg"].fillna(0.0)
        frame["technology"] = frame["technology_raw"].map(self._humanize_tech)
        frame = self._filter_by_input_matrix(frame)
        frame = frame[~frame["technology_raw"].map(self._is_transmission)]
        return frame[columns]

    def _build_demand_df(self) -> pd.DataFrame:
        columns = ["scenario_id", "timestamp", "location", "carrier", "demand_kwh"]
        consumption = self._build_consumption_df()
        if consumption.empty:
            return pd.DataFrame(columns=columns)
        demand = consumption[consumption["technology_raw"].map(self._is_demand)].copy()
        demand = demand.rename(columns={"energy_kwh": "demand_kwh"})
        return demand[columns]

    def get_scenarios(self) -> List[str]:
        return list(self._scenario_ids)

    def normalize_scenario(self, scenario: str) -> str:
        return "default"

    def get_timesteps(self) -> List:
        return list(self.results.timesteps.values)

    def get_timesteps_datetime(self) -> pd.DatetimeIndex:
        return self._time_index

    def get_locations(self) -> List[str]:
        return [str(value) for value in self.results.nodes.values]

    def get_technologies(
        self, include_demand: bool = False, include_transmission: bool = False
    ) -> List[str]:
        result = []
        for value in self.results.techs.values:
            tech = str(value)
            if not include_demand and self._is_demand(tech):
                continue
            if not include_transmission and self._is_transmission(tech):
                continue
            result.append(self._humanize_tech(tech))
        return sorted(set(result))

    def get_technology_color_map(self, include_fallback: bool = True) -> Dict[str, str]:
        color_map = {
            self._humanize_tech(tech): color
            for tech, color in self._tech_color_map.items()
            if color and color.lower() not in {"nan", "none"}
        }
        if include_fallback:
            palette = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]
            for index, tech in enumerate(self.get_technologies(True, True)):
                color_map.setdefault(tech, palette[index % len(palette)])
        return color_map

    def get_carriers(self) -> List[str]:
        return [str(value) for value in self.results.carriers.values]

    def normalize_carrier(self, carrier: str) -> str:
        carriers = self.get_carriers()
        for known in carriers:
            if known.lower() == str(carrier).lower():
                return known
        return carriers[0] if carriers else str(carrier)

    def carrier_label(self, carrier: str) -> str:
        return "CO2" if str(carrier).lower() in {"co2", "co₂"} else str(carrier).title()

    def get_plan_assets(self, scenario_id: Optional[str] = None) -> pd.DataFrame:
        del scenario_id
        if self._assets_df is None:
            self._assets_df = self._build_assets_df()
        return self._assets_df.copy()

    def get_plan_energy(
        self,
        scenario_id: Optional[str] = None,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        del scenario_id
        if self._energy_df is None:
            self._energy_df = self._build_energy_df()
        return self._filter_time(self._energy_df.copy(), start_ts, end_ts)

    def get_plan_consumption(
        self,
        scenario_id: Optional[str] = None,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        del scenario_id
        if self._con_df is None:
            self._con_df = self._build_consumption_df()
        return self._filter_time(self._con_df.copy(), start_ts, end_ts)

    def get_plan_variable_costs(
        self,
        scenario_id: Optional[str] = None,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        del scenario_id
        if self._var_cost_df is None:
            self._var_cost_df = self._build_variable_cost_df()
        return self._filter_time(self._var_cost_df.copy(), start_ts, end_ts)

    def get_plan_emissions(
        self,
        scenario_id: Optional[str] = None,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        del scenario_id
        if self._emissions_df is None:
            self._emissions_df = self._build_emissions_df()
        return self._filter_time(self._emissions_df.copy(), start_ts, end_ts)

    def get_plan_demand(
        self,
        scenario_id: Optional[str] = None,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        del scenario_id
        if self._demand_df is None:
            self._demand_df = self._build_demand_df()
        return self._filter_time(self._demand_df.copy(), start_ts, end_ts)

    def resolve_plan_selection(
        self,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> Dict[str, Optional[str]]:
        locations = self.get_locations()
        techs = self.get_technologies()
        if view_mode == "technology":
            return {
                "group_key": "location",
                "selection_key": "technology",
                "selection_value": selected_tech if selected_tech in techs else (techs[0] if techs else ""),
            }
        if selected_location == ALL_LOCATIONS:
            return {
                "group_key": "technology",
                "selection_key": "location",
                "selection_value": None,
            }
        return {
            "group_key": "technology",
            "selection_key": "location",
            "selection_value": selected_location if selected_location in locations else (locations[0] if locations else ""),
        }

    def _selection(
        self, frame: pd.DataFrame, selection: Dict[str, Optional[str]]
    ) -> pd.DataFrame:
        selection_value = selection["selection_value"]
        if selection_value is None:
            return frame
        return frame[frame[selection["selection_key"]] == selection_value]

    def get_plan_kpis(
        self,
        scenario_id: str,
        carrier: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> Dict[str, float]:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        assets = self._selection(self.get_plan_assets(scenario_id), selection)
        energy = self._selection(self.get_plan_energy(scenario_id, start_ts, end_ts), selection)
        variable = self._selection(self.get_plan_variable_costs(scenario_id, start_ts, end_ts), selection)
        emissions = self._selection(self.get_plan_emissions(scenario_id, start_ts, end_ts), selection)
        carrier_key = self.normalize_carrier(carrier)
        return {
            "capacity": float(assets.built_capacity_kw.sum()),
            "capex": float(assets.capex_eur.sum()),
            "opex": float(assets.fixed_opex_eur.sum() * self._window_fraction(start_ts, end_ts) + variable.variable_opex_eur.sum()),
            "production": float(energy.loc[energy.carrier == carrier_key, "energy_kwh"].sum()),
            "co2_kg": float(emissions.co2_kg.sum()),
        }

    def _capacity_for_carrier(self, row: pd.Series, carrier: str) -> float:
        if self.inputs is None:
            return float(row.built_capacity_kw)
        try:
            defined = self.inputs.definition_matrix.sel(
                nodes=row.location, techs=row.technology_raw, carriers=carrier
            ).item()
            return float(row.built_capacity_kw) if defined else 0.0
        except Exception:
            return 0.0

    def get_plan_capacity_group(
        self,
        scenario_id: str,
        carrier: str,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> pd.DataFrame:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        assets = self._selection(self.get_plan_assets(scenario_id), selection).copy()
        if assets.empty:
            return pd.DataFrame(columns=[selection["group_key"], "carrier_capacity_kw"])
        carrier_key = self.normalize_carrier(carrier)
        assets["carrier_capacity_kw"] = assets.apply(
            lambda row: self._capacity_for_carrier(row, carrier_key), axis=1
        )
        assets = assets[assets.carrier_capacity_kw > 0]
        return assets.groupby(selection["group_key"], as_index=False).carrier_capacity_kw.sum().sort_values(
            "carrier_capacity_kw", ascending=False
        )

    def get_plan_cost_group(
        self,
        scenario_id: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> pd.DataFrame:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        assets = self._selection(self.get_plan_assets(scenario_id), selection)
        variable = self._selection(
            self.get_plan_variable_costs(scenario_id, start_ts, end_ts), selection
        )
        grouped = assets.groupby(group_key, as_index=False)[
            ["capex_eur", "fixed_opex_eur", "built_capacity_kw"]
        ].sum()
        grouped["fixed_opex_eur"] *= self._window_fraction(start_ts, end_ts)
        var_group = variable.groupby(group_key, as_index=False).variable_opex_eur.sum()
        return grouped.merge(var_group, on=group_key, how="left").fillna(0.0)

    def get_plan_co2_group(
        self,
        scenario_id: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> pd.DataFrame:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        emissions = self._selection(
            self.get_plan_emissions(scenario_id, start_ts, end_ts), selection
        )
        return emissions.groupby(selection["group_key"], as_index=False).co2_kg.sum()

    def _top_n_grouped_series(
        self, frame: pd.DataFrame, group_key: str, value_key: str, top_n: int
    ) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["group_label", "timestamp", value_key])
        totals = frame.groupby(group_key)[value_key].sum().nlargest(top_n)
        top = set(totals.index)
        frame = frame.copy()
        frame["group_label"] = frame[group_key].where(frame[group_key].isin(top), "Other")
        return frame.groupby(
            ["group_label", pd.Grouper(key="timestamp", freq="h")], as_index=False
        )[value_key].sum()

    def get_plan_co2_timeseries(
        self,
        scenario_id: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
        top_n: int = 5,
    ) -> pd.DataFrame:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        emissions = self._selection(
            self.get_plan_emissions(scenario_id, start_ts, end_ts), selection
        )
        return self._top_n_grouped_series(emissions, selection["group_key"], "co2_kg", top_n)

    def get_plan_production_timeseries(
        self,
        scenario_id: str,
        carrier: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
        top_n: int = 5,
    ) -> pd.DataFrame:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        energy = self._selection(self.get_plan_energy(scenario_id, start_ts, end_ts), selection)
        energy = energy[energy.carrier == self.normalize_carrier(carrier)]
        return self._top_n_grouped_series(energy, selection["group_key"], "energy_kwh", top_n)

    def get_plan_demand_timeseries(
        self,
        scenario_id: str,
        carrier: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> pd.DataFrame:
        if view_mode != "location":
            return pd.DataFrame(columns=["timestamp", "demand_kwh"])
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        carrier_key = self.normalize_carrier(carrier)
        demand = self.get_plan_demand(scenario_id, start_ts, end_ts)
        demand = demand[demand.carrier == carrier_key]
        consumption = self.get_plan_consumption(scenario_id, start_ts, end_ts)
        conversion = consumption[
            (consumption.carrier == carrier_key)
            & consumption.technology_raw.map(self._is_conversion)
        ]
        if selection["selection_value"] is not None:
            demand = demand[demand.location == selection["selection_value"]]
            conversion = conversion[
                conversion.location == selection["selection_value"]
            ]
        demand_series = demand.groupby("timestamp").demand_kwh.sum()
        conversion_series = conversion.groupby("timestamp").energy_kwh.sum()
        combined = demand_series.add(conversion_series, fill_value=0.0)
        return combined.rename("demand_kwh").reset_index()

    def get_plan_detail_table(
        self,
        scenario_id: str,
        carrier: str,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        view_mode: str,
        selected_location: Optional[str],
        selected_tech: Optional[str],
    ) -> pd.DataFrame:
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        assets = self._selection(self.get_plan_assets(scenario_id), selection)
        energy = self._selection(self.get_plan_energy(scenario_id, start_ts, end_ts), selection)
        variable = self._selection(
            self.get_plan_variable_costs(scenario_id, start_ts, end_ts), selection
        )
        emissions = self._selection(
            self.get_plan_emissions(scenario_id, start_ts, end_ts), selection
        )
        table = assets.groupby(group_key, as_index=False)[
            ["built_capacity_kw", "capex_eur", "fixed_opex_eur"]
        ].sum()
        table["fixed_opex_eur"] *= self._window_fraction(start_ts, end_ts)
        var_group = variable.groupby(group_key, as_index=False).variable_opex_eur.sum()
        prod_group = energy[energy.carrier == self.normalize_carrier(carrier)].groupby(
            group_key, as_index=False
        ).energy_kwh.sum()
        co2_group = emissions.groupby(group_key, as_index=False).co2_kg.sum()
        table = table.merge(var_group, how="left").merge(prod_group, how="left").merge(co2_group, how="left")
        table = table.fillna(0.0).rename(columns={group_key: "Name"})
        hours = self._hours_in_window(start_ts, end_ts)
        table["capacity_factor"] = np.where(
            table.built_capacity_kw > 0,
            table.energy_kwh / (table.built_capacity_kw * hours),
            0.0,
        )
        totals = {column: 0.0 for column in table.columns if column != "Name"}
        totals["Name"] = "Total"
        for column in [
            "built_capacity_kw", "capex_eur", "fixed_opex_eur",
            "variable_opex_eur", "energy_kwh", "co2_kg",
        ]:
            totals[column] = float(table[column].sum())
        if totals["built_capacity_kw"] > 0:
            totals["capacity_factor"] = totals["energy_kwh"] / (
                totals["built_capacity_kw"] * hours
            )
        return pd.concat([table, pd.DataFrame([totals])], ignore_index=True)
