"""Accessors for Calliope 0.7 operate-mode results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr


@dataclass(frozen=True)
class LineRef:
    """A directed view of one Calliope transmission link."""

    line_id: str
    src: str
    dst: str
    tech: str


class OperateResultsHelper:
    """Prepare operate-mode values used by the dashboard callbacks."""

    def __init__(self, results: xr.Dataset, inputs: Optional[xr.Dataset] = None) -> None:
        assert isinstance(results, xr.Dataset)
        assert str(results.attrs.get("calliope_version", "")).startswith("0.7.0")
        self.results = results
        self.inputs = inputs
        self._time_index = pd.DatetimeIndex(pd.to_datetime(results.timesteps.values))
        self._carriers = [str(value) for value in results.carriers.values]
        self._locations = [str(value) for value in results.nodes.values]
        self._tech_category_map = self._tech_map("base_tech")
        self._tech_color_map = self._tech_map("color")

        self._prod_ts_cache: Dict[Tuple[str, str, str], pd.Series] = {}
        self._con_ts_cache: Dict[Tuple[str, str, str], pd.Series] = {}
        self._prod_loc_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._demand_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._unmet_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._unmet_frac_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._conv_con_loc_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._var_cost_ts_cache: Dict[str, pd.Series] = {}
        self._storage_ts_cache: Dict[str, pd.Series] = {}
        self._storage_cap_cache: Dict[str, float] = {}
        self._line_flow_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._line_load_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._line_capacity_cache: Dict[str, float] = {}

        self._line_index = self._build_line_index()
        self._populate_caches()

    def _tech_map(self, variable: str) -> Dict[str, str]:
        if self.inputs is None or variable not in self.inputs:
            return {}
        return {
            str(tech): str(value)
            for tech, value in zip(self.inputs.techs.values, self.inputs[variable].values)
        }

    def _zero_series(self) -> pd.Series:
        return pd.Series(0.0, index=self._time_index, dtype=float)

    def _series(self, variable: str, **selection) -> pd.Series:
        if variable not in self.results:
            return self._zero_series()
        try:
            values = np.asarray(self.results[variable].sel(**selection).values, dtype=float)
            values = np.nan_to_num(values.reshape(-1), nan=0.0)
            return pd.Series(values, index=self._time_index, dtype=float)
        except Exception:
            return self._zero_series()

    def _input_scalar(self, variable: str, **selection) -> float:
        if self.inputs is None or variable not in self.inputs:
            return 0.0
        try:
            array = self.inputs[variable]
            valid_selection = {key: value for key, value in selection.items() if key in array.dims}
            values = np.asarray(array.sel(**valid_selection).values, dtype=float).reshape(-1)
            values = values[np.isfinite(values)]
            return float(values.max()) if values.size else 0.0
        except Exception:
            return 0.0

    def _is_defined(self, node: str, tech: str, carrier: Optional[str] = None) -> bool:
        if self.inputs is None or "definition_matrix" not in self.inputs:
            return False
        try:
            array = self.inputs.definition_matrix.sel(nodes=node, techs=tech)
            if carrier is not None:
                array = array.sel(carriers=carrier)
            return bool(array.any().item())
        except Exception:
            return False

    def _is_transmission(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "transmission"

    def is_storage_tech(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "storage"

    def _is_demand(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "demand"

    def _is_conversion(self, tech: str) -> bool:
        return self._tech_category_map.get(str(tech)) == "conversion"

    def _build_line_index(self) -> Dict[str, LineRef]:
        lines: Dict[str, LineRef] = {}
        if self.inputs is None:
            return lines
        for value in self.results.techs.values:
            tech = str(value)
            if not self._is_transmission(tech):
                continue
            nodes = [node for node in self._locations if self._is_defined(node, tech)]
            if len(nodes) != 2:
                continue
            a, b = sorted(nodes)
            for src, dst in ((a, b), (b, a)):
                line_id = f"{src}::{tech}:{dst}"
                lines[line_id] = LineRef(line_id, src, dst, tech)
        return lines

    def _populate_caches(self) -> None:
        for node in self._locations:
            for tech_value in self.results.techs.values:
                tech = str(tech_value)
                if not self._is_defined(node, tech):
                    continue
                for carrier in self._carriers:
                    if not self._is_defined(node, tech, carrier):
                        continue
                    production = self._series(
                        "flow_out", nodes=node, techs=tech, carriers=carrier
                    ).abs()
                    consumption = self._series(
                        "flow_in", nodes=node, techs=tech, carriers=carrier
                    ).abs()
                    self._prod_ts_cache[(node, tech, carrier)] = production
                    self._con_ts_cache[(node, tech, carrier)] = consumption

                    if not self._is_transmission(tech) and not self._is_demand(tech):
                        key = (node, carrier)
                        self._prod_loc_ts_cache[key] = self._prod_loc_ts_cache.get(
                            key, self._zero_series()
                        ).add(production, fill_value=0.0)
                    if self._is_demand(tech):
                        key = (node, carrier)
                        self._demand_ts_cache[key] = self._demand_ts_cache.get(
                            key, self._zero_series()
                        ).add(consumption, fill_value=0.0)
                    if self._is_conversion(tech):
                        key = (node, carrier)
                        self._conv_con_loc_ts_cache[key] = self._conv_con_loc_ts_cache.get(
                            key, self._zero_series()
                        ).add(consumption, fill_value=0.0)

                if self.is_storage_tech(tech):
                    key = f"{node}::{tech}"
                    self._storage_ts_cache[key] = self._series(
                        "storage", nodes=node, techs=tech
                    )
                    self._storage_cap_cache[key] = self._input_scalar(
                        "storage_cap", nodes=node, techs=tech
                    )

            for carrier in self._carriers:
                self._unmet_ts_cache[(node, carrier)] = self._series(
                    "unmet_demand", nodes=node, carriers=carrier
                ).clip(lower=0.0)
                demand = self._demand_ts_cache.get((node, carrier), self._zero_series())
                unmet = self._unmet_ts_cache[(node, carrier)]
                self._unmet_frac_cache[(node, carrier)] = (
                    unmet / demand.replace(0.0, np.nan)
                ).fillna(0.0).clip(0.0, 1.0)

            if "cost_operation_variable" in self.results:
                cost = self.results.cost_operation_variable.sel(nodes=node)
                if "costs" in cost.dims:
                    key = "monetary" if "monetary" in cost.costs else cost.costs.values[0]
                    cost = cost.sel(costs=key)
                values = cost.sum("techs", skipna=True).values
                self._var_cost_ts_cache[node] = pd.Series(
                    np.nan_to_num(values, nan=0.0), index=self._time_index, dtype=float
                )

        for line_id, line in self._line_index.items():
            capacity = max(
                self._input_scalar("flow_cap", nodes=line.src, techs=line.tech),
                self._input_scalar("flow_cap", nodes=line.dst, techs=line.tech),
                self._input_scalar("flow_cap_max", nodes=line.src, techs=line.tech),
                self._input_scalar("flow_cap_max", nodes=line.dst, techs=line.tech),
            )
            self._line_capacity_cache[line_id] = capacity
            for carrier in self._carriers:
                flow = self._series(
                    "flow_out", nodes=line.dst, techs=line.tech, carriers=carrier
                ).abs()
                self._line_flow_cache[(line_id, carrier)] = flow
                if capacity > 0:
                    self._line_load_cache[(line_id, carrier)] = (flow / capacity).clip(0.0, 1.0)
                else:
                    self._line_load_cache[(line_id, carrier)] = self._zero_series()

    def _coerce_window(self, start_idx: int, end_idx: int) -> Tuple[int, int]:
        if not len(self._time_index):
            return 0, -1
        i0 = max(0, min(len(self._time_index) - 1, int(start_idx)))
        i1 = max(0, min(len(self._time_index) - 1, int(end_idx)))
        return (i1, i0) if i1 < i0 else (i0, i1)

    def _slice_series(self, series: pd.Series, start_idx: int, end_idx: int) -> pd.Series:
        i0, i1 = self._coerce_window(start_idx, end_idx)
        return series.iloc[0:0] if i1 < i0 else series.iloc[i0:i1 + 1]

    def get_timesteps(self) -> List:
        return list(self.results.timesteps.values)

    def get_timesteps_datetime(self) -> pd.DatetimeIndex:
        return self._time_index

    def get_carriers(self) -> List[str]:
        return list(self._carriers)

    def normalize_carrier(self, carrier: str) -> str:
        for known in self._carriers:
            if known.lower() == str(carrier).lower():
                return known
        return self._carriers[0] if self._carriers else str(carrier)

    def get_locations(self) -> List[str]:
        return list(self._locations)

    def get_technology_color_map(self) -> Dict[str, str]:
        return dict(self._tech_color_map)

    def get_location_tech_carrier(self, location: str, tech: str) -> str:
        for carrier in self._carriers:
            if self._is_defined(location, tech, carrier):
                return carrier
        return ""

    def get_location_techs(self, location: str, include_transmission: bool = False) -> List[str]:
        result = []
        for value in self.results.techs.values:
            tech = str(value)
            if not self._is_defined(location, tech):
                continue
            if not include_transmission and self._is_transmission(tech):
                continue
            result.append(tech)
        return sorted(result)

    def get_location_energy_caps(self, location: str) -> Dict[str, float]:
        return {
            tech: self._input_scalar("flow_cap", nodes=location, techs=tech)
            for tech in self.get_location_techs(location, include_transmission=True)
        }

    def get_location_total_production(self, location: str, carrier: str) -> float:
        series = self._prod_loc_ts_cache.get(
            (location, self.normalize_carrier(carrier)), self._zero_series()
        )
        return float(series.sum())

    def get_location_tech_total_production(self, location: str, tech: str, carrier: str) -> float:
        return float(self.get_location_tech_production_timeseries(location, tech, carrier).sum())

    def get_location_tech_production_timeseries(
        self, location: str, tech: str, carrier: str
    ) -> pd.Series:
        return self._prod_ts_cache.get(
            (location, tech, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_location_tech_production_window(
        self, location: str, tech: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_location_tech_production_timeseries(location, tech, carrier),
            start_idx,
            end_idx,
        )

    def get_location_tech_consumption_timeseries(
        self, location: str, tech: str, carrier: str
    ) -> pd.Series:
        return self._con_ts_cache.get(
            (location, tech, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_location_tech_consumption_window(
        self, location: str, tech: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_location_tech_consumption_timeseries(location, tech, carrier),
            start_idx,
            end_idx,
        )

    def get_storage_soc_timeseries(self, location: str, tech: str) -> pd.Series:
        return self._storage_ts_cache.get(f"{location}::{tech}", self._zero_series())

    def get_storage_soc_window(
        self, location: str, tech: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(self.get_storage_soc_timeseries(location, tech), start_idx, end_idx)

    def get_storage_capacity(self, location: str, tech: str) -> float:
        return float(self._storage_cap_cache.get(f"{location}::{tech}", 0.0))

    def get_location_demand_timeseries(self, location: str, carrier: str) -> pd.Series:
        return self._demand_ts_cache.get(
            (location, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_location_demand_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_location_demand_timeseries(location, carrier), start_idx, end_idx
        )

    def get_location_unmet_timeseries(self, location: str, carrier: str) -> pd.Series:
        return self._unmet_ts_cache.get(
            (location, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_location_unmet_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_location_unmet_timeseries(location, carrier), start_idx, end_idx
        )

    def get_location_unmet_fraction_timeseries(self, location: str, carrier: str) -> pd.Series:
        return self._unmet_frac_cache.get(
            (location, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_location_unmet_fraction_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_location_unmet_fraction_timeseries(location, carrier), start_idx, end_idx
        )

    def get_location_unmet_fraction_at_timestep(
        self, location: str, carrier: str, idx: int
    ) -> float:
        series = self.get_location_unmet_fraction_timeseries(location, carrier)
        return float(series.iloc[idx]) if 0 <= idx < len(series) else 0.0

    def get_location_conversion_consumption_timeseries(
        self, location: str, carrier: str
    ) -> pd.Series:
        return self._conv_con_loc_ts_cache.get(
            (location, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_location_conversion_consumption_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_location_conversion_consumption_timeseries(location, carrier),
            start_idx,
            end_idx,
        )

    def get_location_effective_demand_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        demand = self.get_location_demand_window(location, carrier, start_idx, end_idx)
        conversion = self.get_location_conversion_consumption_window(
            location, carrier, start_idx, end_idx
        )
        return demand.add(conversion, fill_value=0.0)

    def get_location_max_unmet_fraction(self, location: str, carrier: str) -> float:
        series = self.get_location_unmet_fraction_timeseries(location, carrier)
        return float(series.max()) if not series.empty else 0.0

    def get_location_max_unmet_fraction_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> float:
        series = self.get_location_unmet_fraction_window(location, carrier, start_idx, end_idx)
        return float(series.max()) if not series.empty else 0.0

    def get_location_operate_kpis(self, location: str, carrier: str) -> Dict[str, float]:
        return self.get_location_operate_kpis_window(
            location, carrier, 0, len(self._time_index) - 1
        )

    def get_location_operate_kpis_window(
        self, location: str, carrier: str, start_idx: int, end_idx: int
    ) -> Dict[str, float]:
        carrier_key = self.normalize_carrier(carrier)
        demand = self.get_location_effective_demand_window(
            location, carrier_key, start_idx, end_idx
        )
        unmet = self.get_location_unmet_window(location, carrier_key, start_idx, end_idx)
        production = self._slice_series(
            self._prod_loc_ts_cache.get((location, carrier_key), self._zero_series()),
            start_idx,
            end_idx,
        )
        variable_cost = self._slice_series(
            self._var_cost_ts_cache.get(location, self._zero_series()), start_idx, end_idx
        )
        return {
            "total_demand": float(demand.sum()),
            "total_unmet": float(unmet.sum()),
            "total_production": float(production.sum()),
            "total_variable_cost": float(variable_cost.sum()),
        }

    def get_line_ids(self) -> List[str]:
        return sorted(self._line_index)

    def get_physical_lines(self) -> List[Tuple[str, str]]:
        return sorted({tuple(sorted((line.src, line.dst))) for line in self._line_index.values()})

    def get_line_ids_for_pair(self, a: str, b: str) -> Tuple[Optional[str], Optional[str]]:
        a_to_b = next(
            (key for key, line in self._line_index.items() if line.src == a and line.dst == b), None
        )
        b_to_a = next(
            (key for key, line in self._line_index.items() if line.src == b and line.dst == a), None
        )
        return a_to_b, b_to_a

    def get_line_ref(self, line_id: str) -> Optional[LineRef]:
        return self._line_index.get(line_id)

    def get_incoming_line_ids(self, location: str) -> List[str]:
        return [key for key, line in self._line_index.items() if line.dst == location]

    def get_line_capacity(self, line_id: str) -> float:
        return float(self._line_capacity_cache.get(line_id, 0.0))

    def get_line_flow_timeseries(self, line_id: str, carrier: str) -> pd.Series:
        return self._line_flow_cache.get(
            (line_id, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_line_flow_window(
        self, line_id: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(self.get_line_flow_timeseries(line_id, carrier), start_idx, end_idx)

    def get_line_flow_at_timestep(self, line_id: str, carrier: str, idx: int) -> float:
        series = self.get_line_flow_timeseries(line_id, carrier)
        return float(series.iloc[idx]) if 0 <= idx < len(series) else 0.0

    def get_line_load_fraction_timeseries(self, line_id: str, carrier: str) -> pd.Series:
        return self._line_load_cache.get(
            (line_id, self.normalize_carrier(carrier)), self._zero_series()
        )

    def get_line_load_fraction_window(
        self, line_id: str, carrier: str, start_idx: int, end_idx: int
    ) -> pd.Series:
        return self._slice_series(
            self.get_line_load_fraction_timeseries(line_id, carrier), start_idx, end_idx
        )

    def get_line_load_fraction_at_timestep(self, line_id: str, carrier: str, idx: int) -> float:
        series = self.get_line_load_fraction_timeseries(line_id, carrier)
        return float(series.iloc[idx]) if 0 <= idx < len(series) else 0.0

    def get_line_max_load_fraction(self, line_id: str, carrier: str) -> float:
        series = self.get_line_load_fraction_timeseries(line_id, carrier)
        return float(series.max()) if not series.empty else 0.0

    def get_line_max_load_fraction_window(
        self, line_id: str, carrier: str, start_idx: int, end_idx: int
    ) -> float:
        series = self.get_line_load_fraction_window(line_id, carrier, start_idx, end_idx)
        return float(series.max()) if not series.empty else 0.0

    def get_line_peak_flow_window(
        self, line_id: str, carrier: str, start_idx: int, end_idx: int
    ) -> float:
        series = self.get_line_flow_window(line_id, carrier, start_idx, end_idx)
        return float(series.max()) if not series.empty else 0.0

    def get_line_total_flow_window(
        self, line_id: str, carrier: str, start_idx: int, end_idx: int
    ) -> float:
        return float(self.get_line_flow_window(line_id, carrier, start_idx, end_idx).sum())

    def get_line_total_flow(self, line_id: str, carrier: str) -> float:
        return float(self.get_line_flow_timeseries(line_id, carrier).sum())

    def get_line_peak_flow(self, line_id: str, carrier: str) -> float:
        series = self.get_line_flow_timeseries(line_id, carrier)
        return float(series.max()) if not series.empty else 0.0
