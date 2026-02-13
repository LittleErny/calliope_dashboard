from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import xarray


@dataclass(frozen=True)
class LineRef:
    """
    Represents a directed transmission line.

    Attributes
    ----------
    line_id : str
        Identifier in the form "A::transmission_tech:B".
    src : str
        Source location (A).
    dst : str
        Destination location (B).
    tech : str
        Base technology name (e.g. "transmission_tech").
    """

    line_id: str
    src: str
    dst: str
    tech: str


class OperateResultsHelper:
    """
    Helper to extract and organize information from Calliope operate-mode results.

    The API is intentionally accessor-style: each public method returns a specific
    slice of information needed by the dashboard.
    """

    def __init__(self, results: xarray.Dataset, inputs: Optional[xarray.Dataset] = None) -> None:
        """
        Initialize helper with operate-mode results and optional inputs.
        """
        assert type(results) is xarray.Dataset
        assert results.calliope_version == "0.6.10"
        self.results = results
        self.inputs = inputs

        self._time_index = self._resolve_timesteps()
        self._carriers = self._resolve_carriers()
        self._tech_category_map = self._build_tech_category_map()
        self._tech_color_map = self._build_tech_color_map()
        self._loc_tech_carrier_map = self._build_loc_tech_carrier_map()
        self._line_index = self._build_line_index()

        self._locations = self._resolve_locations()
        self._prod_df = self._build_carrier_prod_df()
        self._con_df = self._build_carrier_con_df()
        self._demand_df = self._build_required_resource_df()
        self._unmet_df = self._build_unmet_df()
        self._cost_var_df = self._build_cost_var_df()

        self._prod_ts_cache: Dict[Tuple[str, str, str], pd.Series] = {}
        self._con_ts_cache: Dict[Tuple[str, str, str], pd.Series] = {}
        self._prod_loc_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._demand_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._unmet_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._unmet_frac_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._prod_total_cache: Dict[Tuple[str, str, str], float] = {}
        self._prod_total_loc_cache: Dict[Tuple[str, str], float] = {}
        self._conv_con_loc_ts_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._var_cost_loc_cache: Dict[str, float] = {}
        self._line_capacity_cache: Dict[str, float] = {}
        self._line_flow_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._line_load_cache: Dict[Tuple[str, str], pd.Series] = {}
        self._storage_ts_cache: Dict[str, pd.Series] = {}
        self._storage_cap_cache: Dict[str, float] = {}

        self._populate_caches()

    def _resolve_timesteps(self) -> pd.DatetimeIndex:
        """
        Return timesteps parsed as pandas datetime index.

        Returns an empty index if not available.
        """
        try:
            ts = list(self.results.timesteps.values)
        except Exception:
            return pd.DatetimeIndex([])
        parsed = pd.to_datetime(ts, errors="coerce")
        if parsed.isna().all():
            return pd.to_datetime(ts, errors="ignore")
        return pd.DatetimeIndex(parsed)

    def _resolve_carriers(self) -> List[str]:
        """
        Return carrier ids present in results.

        Falls back to an empty list if not available.
        """
        if "carriers" not in self.results.coords:
            return []
        return [str(x) for x in list(self.results.carriers.values)]

    def _build_tech_category_map(self) -> Dict[str, str]:
        """
        Map tech ids to parent categories using inputs.inheritance when available.
        """
        if self.inputs is None or not hasattr(self.inputs, "inheritance"):
            return {}
        try:
            tech_ids = list(self.inputs.techs.values)
            parents = list(self.inputs.inheritance.values)
        except Exception:
            return {}
        return {str(t): str(p) for t, p in zip(tech_ids, parents)}

    def _build_tech_color_map(self) -> Dict[str, str]:
        """
        Map raw tech ids to colors using inputs.colors when available.
        """
        if self.inputs is None or not hasattr(self.inputs, "colors"):
            return {}
        try:
            tech_ids = list(self.inputs.techs.values)
            colors = list(self.inputs.colors.values)
        except Exception:
            return {}
        mapping: Dict[str, str] = {}
        for tech_id, color in zip(tech_ids, colors):
            if color is None:
                continue
            if isinstance(color, (float, np.floating)) and np.isnan(color):
                continue
            color_str = str(color).strip()
            if not color_str or color_str.lower() in {"nan", "none"}:
                continue
            mapping[str(tech_id)] = color_str
        return mapping

    def _build_loc_tech_carrier_map(self) -> Dict[str, str]:
        """
        Build a map from 'loc::tech' to carrier using inputs lookup tables.
        """
        if self.inputs is None:
            return {}
        try:
            loc_techs = list(self.inputs.loc_techs_non_conversion.values)
            lookup = list(self.inputs.lookup_loc_techs.values)
        except Exception:
            return {}
        mapping: Dict[str, str] = {}
        for loc_tech, loc_tech_carrier in zip(loc_techs, lookup):
            parts = str(loc_tech_carrier).split("::", 2)
            if len(parts) == 3:
                mapping[str(loc_tech)] = parts[2]
        return mapping

    def _resolve_locations(self) -> List[str]:
        """
        Return all locations present in results.
        """
        if "locs" in self.results.coords:
            return [str(x) for x in list(self.results.locs.values)]
        locs = set()
        if "loc_techs" in self.results.coords:
            for val in self.results.loc_techs.values:
                loc, _ = self._split_loc_tech(val)
                if loc:
                    locs.add(loc)
        return sorted(locs)

    def _build_carrier_prod_df(self) -> pd.DataFrame:
        """
        Build a flattened dataframe from results.carrier_prod.
        """
        if "carrier_prod" not in self.results.data_vars:
            return pd.DataFrame(columns=["loc_tech_carriers_prod", "timesteps", "energy", "loc", "tech", "carrier"])
        df = self.results.carrier_prod.to_series().rename("energy").reset_index()
        df[["loc", "tech", "carrier"]] = df["loc_tech_carriers_prod"].apply(
            lambda x: pd.Series(self._split_loc_tech_carrier(x))
        )
        return df

    def _build_carrier_con_df(self) -> pd.DataFrame:
        """
        Build a flattened dataframe from results.carrier_con.
        """
        if "carrier_con" not in self.results.data_vars:
            return pd.DataFrame(columns=["loc_tech_carriers_con", "timesteps", "energy", "loc", "tech", "carrier"])
        df = self.results.carrier_con.to_series().rename("energy").reset_index()
        df[["loc", "tech", "carrier"]] = df["loc_tech_carriers_con"].apply(
            lambda x: pd.Series(self._split_loc_tech_carrier(x))
        )
        return df

    def _build_required_resource_df(self) -> pd.DataFrame:
        """
        Build a flattened dataframe from results.required_resource (demand techs).
        """
        if "required_resource" not in self.results.data_vars:
            return pd.DataFrame(
                columns=["loc_techs_balance_demand_constraint", "timesteps", "req", "loc", "tech", "carrier"])
        df = self.results.required_resource.to_series().rename("req").reset_index()
        df[["loc", "tech"]] = df["loc_techs_balance_demand_constraint"].apply(
            lambda x: pd.Series(self._split_loc_tech(x))
        )
        df["carrier"] = df["loc_techs_balance_demand_constraint"].map(self._loc_tech_carrier_map).fillna("")
        return df

    def _build_unmet_df(self) -> pd.DataFrame:
        """
        Build a flattened dataframe from results.unmet_demand.
        """
        if "unmet_demand" not in self.results.data_vars:
            return pd.DataFrame(columns=["loc_carriers", "timesteps", "unmet", "loc", "carrier"])
        df = self.results.unmet_demand.to_series().rename("unmet").reset_index()
        df[["loc", "carrier"]] = df["loc_carriers"].str.split("::", expand=True)
        return df

    def _build_cost_var_df(self) -> pd.DataFrame:
        """
        Build a flattened dataframe from results.cost_var (monetary by default).
        """
        if "cost_var" not in self.results.data_vars:
            return pd.DataFrame(columns=["loc_techs_om_cost", "timesteps", "cost", "loc", "tech"])
        df = self.results.cost_var.to_series().rename("cost").reset_index()
        df[["loc", "tech"]] = df["loc_techs_om_cost"].apply(
            lambda x: pd.Series(self._split_loc_tech(x))
        )
        return df

    def _populate_caches(self) -> None:
        """
        Precompute timeseries and aggregates for fast dashboard access.
        """
        # Production timeseries per loc-tech-carrier
        for (loc, tech, carrier), group in self._prod_df.groupby(["loc", "tech", "carrier"]):
            ts = group.set_index("timesteps")["energy"].reindex(self._time_index, fill_value=0.0)
            key = (loc, tech, carrier)
            self._prod_ts_cache[key] = ts
            self._prod_total_cache[key] = float(ts.sum())
            self._prod_total_loc_cache[(loc, carrier)] = self._prod_total_loc_cache.get((loc, carrier), 0.0) + float(
                ts.sum())
            loc_key = (loc, carrier)
            if loc_key in self._prod_loc_ts_cache:
                self._prod_loc_ts_cache[loc_key] = self._prod_loc_ts_cache[loc_key].add(ts, fill_value=0.0)
            else:
                self._prod_loc_ts_cache[loc_key] = ts.copy()

        # Consumption timeseries per loc-tech-carrier
        for (loc, tech, carrier), group in self._con_df.groupby(["loc", "tech", "carrier"]):
            ts = group.set_index("timesteps")["energy"].reindex(self._time_index, fill_value=0.0)
            self._con_ts_cache[(loc, tech, carrier)] = ts
            base = tech.split(":", 1)[0]
            if self._tech_category_map.get(base) in {"conversion", "conversion_plus"}:
                key = (loc, carrier)
                if key in self._conv_con_loc_ts_cache:
                    self._conv_con_loc_ts_cache[key] = self._conv_con_loc_ts_cache[key].add(ts, fill_value=0.0)
                else:
                    self._conv_con_loc_ts_cache[key] = ts.copy()

        # Demand timeseries per loc-carrier
        for (loc, carrier), group in self._demand_df.groupby(["loc", "carrier"]):
            ts = group.set_index("timesteps")["req"].reindex(self._time_index, fill_value=0.0).abs()
            self._demand_ts_cache[(loc, carrier)] = ts

        # Unmet timeseries per loc-carrier
        for (loc, carrier), group in self._unmet_df.groupby(["loc", "carrier"]):
            ts = group.set_index("timesteps")["unmet"].reindex(self._time_index, fill_value=0.0)
            self._unmet_ts_cache[(loc, carrier)] = ts

        # Unmet fraction cache
        for loc in self._locations:
            for carrier in self._carriers:
                demand_ts = self._demand_ts_cache.get((loc, carrier), pd.Series(index=self._time_index, data=0.0))
                unmet_ts = self._unmet_ts_cache.get((loc, carrier), pd.Series(index=self._time_index, data=0.0))
                denom = demand_ts.replace(0, np.nan)
                frac = (unmet_ts / denom).fillna(0.0).clip(lower=0.0, upper=1.0)
                self._unmet_frac_cache[(loc, carrier)] = frac

        # Storage SOC cache
        if "storage" in self.results.data_vars and "loc_techs_store" in self.results.coords:
            for loc_tech in self.results.loc_techs_store.values:
                key = str(loc_tech)
                try:
                    values = self.results.storage.sel(loc_techs_store=loc_tech).values
                    ts = pd.Series(values, index=self._time_index).reindex(self._time_index, fill_value=0.0)
                except Exception:
                    ts = pd.Series(index=self._time_index, data=0.0)
                self._storage_ts_cache[key] = ts

        # Storage capacity cache
        if "storage_cap" in self.results.data_vars and "loc_techs_store" in self.results.coords:
            for loc_tech in self.results.loc_techs_store.values:
                key = str(loc_tech)
                try:
                    self._storage_cap_cache[key] = float(self.results.storage_cap.sel(loc_techs_store=loc_tech).values)
                except Exception:
                    self._storage_cap_cache[key] = 0.0

        # Variable cost per location (monetary)
        if "costs" in self.results.cost_var.dims if "cost_var" in self.results.data_vars else False:
            try:
                df = self._cost_var_df[self._cost_var_df["costs"] == "monetary"]
            except Exception:
                df = self._cost_var_df
        else:
            df = self._cost_var_df
        for loc, group in df.groupby("loc"):
            self._var_cost_loc_cache[loc] = float(group["cost"].sum())

        # Line capacity cache
        for line_id in self._line_index.keys():
            self._line_capacity_cache[line_id] = self.get_line_capacity(line_id)

        # Line flow/load cache
        for line_id in self._line_index.keys():
            for carrier in self._carriers:
                loc, tech = self._split_loc_tech(line_id)
                con_ts = self._con_ts_cache.get((loc, tech, carrier))

                if con_ts is not None:
                    ts = con_ts.abs()
                else:
                    # For transmission lines, directional flow is represented in carrier_con.
                    # If carrier_con does not exist for this loc_tech_carrier, treat as zero
                    # (do not fall back to carrier_prod, which is the destination end).
                    ts = pd.Series(index=self._time_index, data=0.0)

                self._line_flow_cache[(line_id, carrier)] = ts
                cap = self._line_capacity_cache.get(line_id, 0.0)
                if cap > 0:
                    self._line_load_cache[(line_id, carrier)] = (ts.abs() / cap).clip(lower=0.0, upper=1.0)
                else:
                    self._line_load_cache[(line_id, carrier)] = pd.Series(index=self._time_index, data=0.0)

    def _is_transmission(self, tech: str) -> bool:
        """
        Return True if tech is a transmission tech.
        """
        base = str(tech).split(":", 1)[0]
        category = self._tech_category_map.get(base)
        if category:
            return category == "transmission"
        return "transmission" in base

    def is_storage_tech(self, tech: str) -> bool:
        """
        Return True if tech is a storage tech.
        """
        base = str(tech).split(":", 1)[0]
        category = self._tech_category_map.get(base)
        if category:
            return category == "storage"
        return "storage" in base

    def get_technology_color_map(self) -> Dict[str, str]:
        """
        Return mapping of base tech id to hex color.
        """
        return dict(self._tech_color_map)

    @staticmethod
    def _split_loc_tech(loc_tech: str) -> Tuple[str, str]:
        """
        Split 'loc::tech' into (location, tech).
        """
        parts = str(loc_tech).split("::", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", parts[0]

    @staticmethod
    def _split_loc_tech_carrier(loc_tech_carrier: str) -> Tuple[str, str, str]:
        """
        Split 'loc::tech::carrier' into (location, tech, carrier).
        """
        parts = str(loc_tech_carrier).split("::", 2)
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return parts[0], parts[1], ""
        return "", "", parts[0]

    @staticmethod
    def _split_transmission_loc_tech(loc_tech: str) -> Optional[Tuple[str, str, str]]:
        """
        Split transmission loc_tech into (src, tech_base, dst).

        Returns None if pattern does not match.
        """
        loc, tech = OperateResultsHelper._split_loc_tech(loc_tech)
        if ":" not in tech:
            return None
        tech_base, dst = tech.split(":", 1)
        if not loc or not tech_base or not dst:
            return None
        return loc, tech_base, dst

    def _coerce_window(self, start_idx: int, end_idx: int) -> Tuple[int, int]:
        """
        Normalize and clamp window indices to valid bounds.
        """
        n = len(self._time_index)
        if n <= 0:
            return 0, -1
        i0 = max(0, min(n - 1, int(start_idx)))
        i1 = max(0, min(n - 1, int(end_idx)))
        if i1 < i0:
            i0, i1 = i1, i0
        return i0, i1

    def _slice_series(self, ts: pd.Series, start_idx: int, end_idx: int) -> pd.Series:
        """
        Return a series slice for the given inclusive window indices.
        """
        if ts is None or ts.empty:
            return pd.Series(index=self._time_index, data=0.0)
        i0, i1 = self._coerce_window(start_idx, end_idx)
        if i1 < i0:
            return ts.iloc[0:0]
        return ts.iloc[i0:i1 + 1]

    def _build_line_index(self) -> Dict[str, LineRef]:
        """
        Build a map of directed transmission lines present in results.

        Keys are line_id strings ("A::transmission_tech:B").
        """
        lines: Dict[str, LineRef] = {}
        if "loc_techs" not in self.results.coords:
            return lines
        for val in self.results.loc_techs.values:
            loc_tech = str(val)
            parsed = self._split_transmission_loc_tech(loc_tech)
            if not parsed:
                continue
            src, tech_base, dst = parsed
            if not self._is_transmission(tech_base):
                continue
            line_id = f"{src}::{tech_base}:{dst}"
            lines[line_id] = LineRef(line_id=line_id, src=src, dst=dst, tech=tech_base)
        return lines

    def get_timesteps(self) -> List:
        """
        Return timesteps as stored in results.
        """
        try:
            return list(self.results.timesteps.values)
        except Exception:
            return []

    def get_timesteps_datetime(self) -> pd.DatetimeIndex:
        """
        Return timesteps parsed as pandas datetime.
        """
        return self._time_index

    def get_carriers(self) -> List[str]:
        """
        Return all carriers present in results.
        """
        return list(self._carriers)

    def normalize_carrier(self, carrier: str) -> str:
        """
        Return a known carrier id, falling back to the first carrier.
        """
        if not self._carriers:
            return str(carrier)
        if carrier in self._carriers:
            return carrier
        for c in self._carriers:
            if str(c).lower() == str(carrier).lower():
                return c
        return self._carriers[0]

    def get_location_tech_carrier(self, location: str, tech: str) -> str:
        """
        Return carrier for a non-conversion tech at a location, if known.
        """
        loc_tech = f"{location}::{tech}"
        return str(self._loc_tech_carrier_map.get(loc_tech, ""))

    def get_locations(self) -> List[str]:
        """
        Return all locations present in results.
        """
        return list(self._locations)

    def get_location_techs(self, location: str, include_transmission: bool = False) -> List[str]:
        """
        Return tech ids present at a location.

        Parameters
        ----------
        location : str
            Location name.
        include_transmission : bool
            Whether to include transmission techs.
        """
        techs: List[str] = []
        if "loc_techs" not in self.results.coords:
            return techs
        for val in self.results.loc_techs.values:
            loc, tech = self._split_loc_tech(val)
            if loc != location:
                continue
            base = tech.split(":", 1)[0]
            if not include_transmission and self._is_transmission(base):
                continue
            techs.append(tech)
        return sorted(set(techs))

    def get_location_energy_caps(self, location: str) -> Dict[str, float]:
        """
        Return installed energy capacity per tech at the given location.
        """
        caps: Dict[str, float] = {}
        if "energy_cap" not in self.results.data_vars or "loc_techs" not in self.results.coords:
            return caps
        for loc_tech in self.results.loc_techs.values:
            loc, tech = self._split_loc_tech(loc_tech)
            if loc != location:
                continue
            try:
                caps[tech] = float(self.results.energy_cap.sel(loc_techs=loc_tech).values)
            except Exception:
                caps[tech] = float("nan")
        return caps

    def get_location_total_production(self, location: str, carrier: str) -> float:
        """
        Return total production at a location for a carrier over all timesteps.
        """
        carrier_key = self.normalize_carrier(carrier)
        return float(self._prod_total_loc_cache.get((location, carrier_key), 0.0))

    def get_location_tech_total_production(self, location: str, tech: str, carrier: str) -> float:
        """
        Return total production for a specific tech at a location over all timesteps.
        """
        carrier_key = self.normalize_carrier(carrier)
        return float(self._prod_total_cache.get((location, tech, carrier_key), 0.0))

    def get_location_tech_production_timeseries(self, location: str, tech: str, carrier: str) -> pd.Series:
        """
        Return production timeseries for a specific tech at a location.
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._prod_ts_cache.get((location, tech, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_location_tech_production_window(self, location: str, tech: str, carrier: str, start_idx: int,
                                            end_idx: int) -> pd.Series:
        """
        Return production timeseries for a specific tech at a location within a time window.
        """
        ts = self.get_location_tech_production_timeseries(location, tech, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_location_tech_consumption_timeseries(self, location: str, tech: str, carrier: str) -> pd.Series:
        """
        Return consumption timeseries for a specific tech at a location.
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._con_ts_cache.get((location, tech, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_storage_soc_timeseries(self, location: str, tech: str) -> pd.Series:
        """
        Return storage state of charge timeseries for a storage tech at a location.
        """
        key = f"{location}::{tech}"
        ts = self._storage_ts_cache.get(key)
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_storage_soc_window(self, location: str, tech: str, start_idx: int, end_idx: int) -> pd.Series:
        """
        Return storage SOC timeseries within a time window.
        """
        ts = self.get_storage_soc_timeseries(location, tech)
        return self._slice_series(ts, start_idx, end_idx)

    def get_storage_capacity(self, location: str, tech: str) -> float:
        """
        Return storage capacity (kWh) for a storage tech at a location.
        """
        key = f"{location}::{tech}"
        return float(self._storage_cap_cache.get(key, 0.0))

    def get_location_tech_consumption_window(self, location: str, tech: str, carrier: str, start_idx: int,
                                             end_idx: int) -> pd.Series:
        """
        Return consumption timeseries for a specific tech at a location within a time window.
        """
        ts = self.get_location_tech_consumption_timeseries(location, tech, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_location_demand_timeseries(self, location: str, carrier: str) -> pd.Series:
        """
        Return demand timeseries for a location and carrier (absolute values).
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._demand_ts_cache.get((location, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_location_demand_window(self, location: str, carrier: str, start_idx: int, end_idx: int) -> pd.Series:
        """
        Return demand timeseries for a location and carrier within a time window.
        """
        ts = self.get_location_demand_timeseries(location, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_location_unmet_timeseries(self, location: str, carrier: str) -> pd.Series:
        """
        Return unmet demand timeseries for a location and carrier.
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._unmet_ts_cache.get((location, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_location_unmet_window(self, location: str, carrier: str, start_idx: int, end_idx: int) -> pd.Series:
        """
        Return unmet demand timeseries for a location and carrier within a time window.
        """
        ts = self.get_location_unmet_timeseries(location, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_location_unmet_fraction_timeseries(self, location: str, carrier: str) -> pd.Series:
        """
        Return unmet fraction (unmet / demand) timeseries for a location and carrier.
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._unmet_frac_cache.get((location, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_location_unmet_fraction_window(self, location: str, carrier: str, start_idx: int,
                                           end_idx: int) -> pd.Series:
        """
        Return unmet fraction timeseries within a time window.
        """
        ts = self.get_location_unmet_fraction_timeseries(location, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_location_unmet_fraction_at_timestep(self, location: str, carrier: str, idx: int) -> float:
        """
        Return unmet fraction for a specific timestep index.
        """
        frac = self.get_location_unmet_fraction_timeseries(location, carrier)
        if idx < 0 or idx >= len(frac):
            return 0.0
        return float(frac.iloc[idx])

    def get_location_conversion_consumption_timeseries(self, location: str, carrier: str) -> pd.Series:
        """
        Return total conversion consumption timeseries for a location and carrier.
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._conv_con_loc_ts_cache.get((location, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_location_conversion_consumption_window(self, location: str, carrier: str, start_idx: int,
                                                   end_idx: int) -> pd.Series:
        """
        Return conversion consumption timeseries within a time window.
        """
        ts = self.get_location_conversion_consumption_timeseries(location, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_location_effective_demand_window(self, location: str, carrier: str, start_idx: int,
                                             end_idx: int) -> pd.Series:
        """
        Return demand + conversion-input consumption within a time window.
        """
        demand_ts = self.get_location_demand_window(location, carrier, start_idx, end_idx)
        conv_ts = self.get_location_conversion_consumption_window(location, carrier, start_idx, end_idx).abs()
        return demand_ts.add(conv_ts, fill_value=0.0)

    def get_location_max_unmet_fraction(self, location: str, carrier: str) -> float:
        """
        Return maximum unmet fraction over the window for a location and carrier.
        """
        frac = self.get_location_unmet_fraction_timeseries(location, carrier)
        if frac.empty:
            return 0.0
        return float(frac.max())

    def get_location_max_unmet_fraction_window(self, location: str, carrier: str, start_idx: int,
                                               end_idx: int) -> float:
        """
        Return maximum unmet fraction within a time window.
        """
        frac = self.get_location_unmet_fraction_window(location, carrier, start_idx, end_idx)
        if frac.empty:
            return 0.0
        return float(frac.max())

    def get_location_operate_kpis(self, location: str, carrier: str) -> Dict[str, float]:
        """
        Return basic operate-mode KPIs for a location over the full window.
        """
        demand_ts = self.get_location_demand_timeseries(location, carrier)
        conv_ts = self.get_location_conversion_consumption_timeseries(location, carrier).abs()
        unmet_ts = self.get_location_unmet_timeseries(location, carrier)
        prod_total = self.get_location_total_production(location, carrier)

        kpis = {
            "total_demand": float(demand_ts.add(conv_ts, fill_value=0.0).sum()),
            "total_unmet": float(unmet_ts.sum()),
            "total_production": float(prod_total),
        }

        kpis["total_variable_cost"] = float(self._var_cost_loc_cache.get(location, 0.0))
        return kpis

    def get_location_operate_kpis_window(self, location: str, carrier: str, start_idx: int, end_idx: int) -> Dict[
        str, float]:
        """
        Return operate-mode KPIs for a location within a time window.
        """
        demand_ts = self.get_location_effective_demand_window(location, carrier, start_idx, end_idx)
        unmet_ts = self.get_location_unmet_window(location, carrier, start_idx, end_idx)
        carrier_key = self.normalize_carrier(carrier)

        prod_ts = self._prod_loc_ts_cache.get((location, carrier_key), pd.Series(index=self._time_index, data=0.0))
        prod_ts = self._slice_series(prod_ts, start_idx, end_idx)

        kpis = {
            "total_demand": float(demand_ts.sum()),
            "total_unmet": float(unmet_ts.sum()),
            "total_production": float(prod_ts.sum()),
        }

        if location in self._var_cost_loc_cache:
            # Scale variable cost by the fraction of window covered
            full_ts = len(self._time_index)
            i0, i1 = self._coerce_window(start_idx, end_idx)
            window_steps = max(1, i1 - i0 + 1)
            fraction = float(window_steps) / float(full_ts) if full_ts else 1.0
            kpis["total_variable_cost"] = float(self._var_cost_loc_cache[location]) * fraction
        else:
            kpis["total_variable_cost"] = 0.0
        return kpis

    def get_line_ids(self) -> List[str]:
        """
        Return directed transmission line ids (\"A::tech:B\").
        """
        return sorted(self._line_index.keys())

    def get_physical_lines(self) -> List[Tuple[str, str]]:
        """
        Return undirected physical lines as (A, B) tuples.
        """
        pairs = set()
        for line in self._line_index.values():
            a, b = sorted([line.src, line.dst])
            pairs.add((a, b))
        return sorted(pairs)

    def get_line_ids_for_pair(self, a: str, b: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Return directed line ids for A->B and B->A if they exist.
        """
        a_to_b = None
        b_to_a = None
        for line_id, line in self._line_index.items():
            if line.src == a and line.dst == b:
                a_to_b = line_id
            elif line.src == b and line.dst == a:
                b_to_a = line_id
        return a_to_b, b_to_a

    def get_line_ref(self, line_id: str) -> Optional[LineRef]:
        """
        Return LineRef metadata for a directed line id.
        """
        return self._line_index.get(line_id)

    def get_incoming_line_ids(self, location: str) -> List[str]:
        """
        Return directed line ids whose destination is the given location.
        """
        return [line_id for line_id, line in self._line_index.items() if line.dst == location]

    def get_line_capacity(self, line_id: str) -> float:
        """
        Return installed capacity for a directed line.
        """
        if line_id in self._line_capacity_cache:
            return float(self._line_capacity_cache[line_id])
        if "energy_cap" not in self.results.data_vars or "loc_techs" not in self.results.coords:
            return 0.0
        try:
            return float(self.results.energy_cap.sel(loc_techs=line_id).values)
        except Exception:
            return 0.0

    def get_line_flow_timeseries(self, line_id: str, carrier: str) -> pd.Series:
        """
        Return flow timeseries for a directed line and carrier (carrier_prod).
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._line_flow_cache.get((line_id, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_line_flow_window(self, line_id: str, carrier: str, start_idx: int, end_idx: int) -> pd.Series:
        """
        Return line flow timeseries within a time window.
        """
        ts = self.get_line_flow_timeseries(line_id, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_line_flow_at_timestep(self, line_id: str, carrier: str, idx: int) -> float:
        """
        Return flow value at a given timestep index for a directed line.
        """
        ts = self.get_line_flow_timeseries(line_id, carrier)
        if idx < 0 or idx >= len(ts):
            return 0.0
        return float(ts.iloc[idx])

    def get_line_load_fraction_timeseries(self, line_id: str, carrier: str) -> pd.Series:
        """
        Return load fraction timeseries for a directed line (flow / capacity).
        """
        carrier_key = self.normalize_carrier(carrier)
        ts = self._line_load_cache.get((line_id, carrier_key))
        if ts is None:
            return pd.Series(index=self._time_index, data=0.0)
        return ts

    def get_line_load_fraction_window(self, line_id: str, carrier: str, start_idx: int, end_idx: int) -> pd.Series:
        """
        Return load fraction timeseries within a time window.
        """
        ts = self.get_line_load_fraction_timeseries(line_id, carrier)
        return self._slice_series(ts, start_idx, end_idx)

    def get_line_load_fraction_at_timestep(self, line_id: str, carrier: str, idx: int) -> float:
        """
        Return load fraction at a given timestep index for a directed line.
        """
        ts = self.get_line_load_fraction_timeseries(line_id, carrier)
        if idx < 0 or idx >= len(ts):
            return 0.0
        return float(ts.iloc[idx])

    def get_line_max_load_fraction(self, line_id: str, carrier: str) -> float:
        """
        Return maximum load fraction over the window for a directed line.
        """
        ts = self.get_line_load_fraction_timeseries(line_id, carrier)
        if ts.empty:
            return 0.0
        return float(ts.max())

    def get_line_max_load_fraction_window(self, line_id: str, carrier: str, start_idx: int, end_idx: int) -> float:
        """
        Return maximum load fraction within a time window.
        """
        ts = self.get_line_load_fraction_window(line_id, carrier, start_idx, end_idx)
        if ts.empty:
            return 0.0
        return float(ts.max())

    def get_line_peak_flow_window(self, line_id: str, carrier: str, start_idx: int, end_idx: int) -> float:
        """
        Return peak absolute flow within a time window.
        """
        ts = self.get_line_flow_window(line_id, carrier, start_idx, end_idx)
        return float(ts.abs().max()) if not ts.empty else 0.0

    def get_line_total_flow_window(self, line_id: str, carrier: str, start_idx: int, end_idx: int) -> float:
        """
        Return total absolute flow within a time window.
        """
        ts = self.get_line_flow_window(line_id, carrier, start_idx, end_idx)
        return float(ts.abs().sum())

    def get_line_total_flow(self, line_id: str, carrier: str) -> float:
        """
        Return total absolute flow over the window for a directed line.
        """
        ts = self.get_line_flow_timeseries(line_id, carrier)
        return float(ts.abs().sum())

    def get_line_peak_flow(self, line_id: str, carrier: str) -> float:
        """
        Return peak absolute flow over the window for a directed line.
        """
        ts = self.get_line_flow_timeseries(line_id, carrier)
        return float(ts.abs().max()) if not ts.empty else 0.0
