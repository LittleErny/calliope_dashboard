import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xarray


class ResultsHelper:
    """
    Helper to extract and organize information from Calliope's Model.results.

    The API is intentionally accessor-style (similar to InputsHelper): each public
    method returns a specific slice of information and can be called independently.
    """

    def __init__(self, results: xarray.Dataset, inputs: Optional[xarray.Dataset] = None) -> None:
        assert type(results) is xarray.Dataset
        assert results.calliope_version == "0.6.10"
        self.results = results
        self.inputs = inputs

        self._cost_key = self._pick_cost_key()
        self._scenario_ids = self._resolve_scenarios()
        self._time_index = self._resolve_timesteps()
        self._tech_name_map = self._build_tech_name_map()
        self._tech_category_map = self._build_tech_category_map()
        self._tech_color_map = self._build_tech_color_map()
        self._label_color_map = self._build_label_color_map()

        self._assets_df: Optional[pd.DataFrame] = None
        self._energy_df: Optional[pd.DataFrame] = None
        self._con_df: Optional[pd.DataFrame] = None
        self._var_cost_df: Optional[pd.DataFrame] = None
        self._emissions_df: Optional[pd.DataFrame] = None
        self._demand_df: Optional[pd.DataFrame] = None
        self._plan_ts_cache: Dict[Tuple, pd.DataFrame] = {}
        self._conversion_io_cache: Dict[str, Dict[str, List[str]]] = {}
        self._conversion_ratio_cache: Dict[str, Dict[Tuple[str, str], float]] = {}
        self._energy_eff_max_cache: Dict[str, float] = {}

    def _pick_cost_key(self) -> Optional[str]:
        """Select a default cost dimension key from results (monetary first, else first available)."""
        try:
            costs = [str(x) for x in list(self.results.costs.values)]
        except Exception:
            return None
        for key in ["monetary", "money", "cost"]:
            if key in costs:
                return key
        return costs[0] if costs else None

    def _resolve_cost_key(self, target: str) -> Optional[str]:
        """Resolve a specific cost key name (case-insensitive) from results.costs."""
        try:
            costs = [str(x) for x in list(self.results.costs.values)]
        except Exception:
            return None
        for key in costs:
            if str(key).lower() == str(target).lower():
                return str(key)
        return None

    def _resolve_scenarios(self) -> List[str]:
        """Return scenario ids from results coords/attrs, falling back to a default label."""
        scenarios: List[str] = []
        if "scenarios" in self.results.coords:
            scenarios = [str(x) for x in list(self.results.scenarios.values)]
        if not scenarios:
            attr = self.results.attrs.get("scenario")
            if attr:
                scenarios = [str(attr)]
        return scenarios or ["default"]

    def _resolve_timesteps(self) -> pd.DatetimeIndex:
        """Return timesteps parsed as pandas datetime index (empty if unavailable)."""
        try:
            ts = list(self.results.timesteps.values)
        except Exception:
            return pd.DatetimeIndex([])
        parsed = pd.to_datetime(ts, errors="coerce")
        if parsed.isna().all():
            return pd.to_datetime(ts, errors="ignore")
        return pd.DatetimeIndex(parsed)

    def _build_tech_name_map(self) -> Dict[str, str]:
        """Map raw tech ids to human-friendly names using inputs (empty if inputs missing)."""
        if self.inputs is None:
            return {}
        try:
            tech_ids = list(self.inputs.techs.values)
            names = list(self.inputs.names.values)
        except Exception:
            return {}
        return {str(t): str(n) for t, n in zip(tech_ids, names)}

    def _build_tech_category_map(self) -> Dict[str, str]:
        """Map raw tech ids to parent tech category using inputs (empty if inputs missing)."""
        if self.inputs is None:
            return {}
        try:
            tech_ids = list(self.inputs.techs.values)
            parents = list(self.inputs.inheritance.values)
        except Exception:
            return {}
        return {str(t): str(p) for t, p in zip(tech_ids, parents)}

    def _build_tech_color_map(self) -> Dict[str, str]:
        """Map raw tech ids to colors using inputs.colors when available."""
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

    def _build_label_color_map(self) -> Dict[str, str]:
        """Map humanized tech labels to colors (best effort)."""
        label_map: Dict[str, str] = {}
        if "loc_techs" in self.results.coords:
            for val in self.results.loc_techs.values:
                _, tech = self._split_loc_tech(val)
                if not tech:
                    continue
                base = tech.split(":", 1)[0]
                color = self._tech_color_map.get(base)
                if not color:
                    continue
                label = self._humanize_tech(tech)
                label_map[label] = color
        for tech_id, color in self._tech_color_map.items():
            label = self._humanize_tech(tech_id)
            label_map.setdefault(label, color)
        return label_map

    def _dataarray_to_df(
            self,
            da: xarray.DataArray,
            value_name: str,
            select_cost: bool = False,
            cost_key: Optional[str] = None,
    ) -> pd.DataFrame:
        """Convert a DataArray to a flat DataFrame, optionally selecting a cost slice."""
        if select_cost and "costs" in da.dims:
            key = cost_key or self._cost_key
            if key:
                da = da.sel(costs=key)
            else:
                da = da.isel(costs=0)
        df = da.to_series().rename(value_name).reset_index()
        if "scenarios" in df.columns:
            df = df.rename(columns={"scenarios": "scenario_id"})
        if "scenario_id" not in df.columns:
            df["scenario_id"] = self._scenario_ids[0]
        return df

    def _split_loc_tech(self, loc_tech: str) -> Tuple[str, str]:
        """Split 'loc::tech' into (location, tech)."""
        parts = str(loc_tech).split("::", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", parts[0]

    def _split_loc_tech_carrier(self, loc_tech_carrier: str) -> Tuple[str, str, str]:
        """Split 'loc::tech::carrier' into (location, tech, carrier)."""
        parts = str(loc_tech_carrier).split("::", 2)
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return parts[0], "", parts[1]
        return "", "", parts[0]

    def _humanize_tech(self, tech: str) -> str:
        """Return a display name for a tech (uses inputs name map when available)."""
        base, suffix = (tech.split(":", 1) + [""])[:2]
        label = self._tech_name_map.get(base, base)
        return f"{label} ({suffix})" if suffix else label

    def _is_transmission(self, tech: str) -> bool:
        """Return True if tech category is transmission (requires inputs to be accurate)."""
        base = str(tech).split(":", 1)[0]
        return self._tech_category_map.get(base) == "transmission"

    def _is_conversion(self, tech: str) -> bool:
        """Return True if tech category is conversion/conversion_plus (requires inputs)."""
        base = str(tech).split(":", 1)[0]
        return self._tech_category_map.get(base) in {"conversion", "conversion_plus"}

    def _is_demand(self, tech: str) -> bool:
        """Return True if tech category is demand (requires inputs to be accurate)."""
        base = str(tech).split(":", 1)[0]
        return self._tech_category_map.get(base) == "demand"

    def _filter_scenario(self, df: pd.DataFrame, scenario_id: Optional[str]) -> pd.DataFrame:
        """Filter a dataframe by scenario_id if column exists and value provided."""
        if not scenario_id or "scenario_id" not in df.columns:
            return df
        return df[df["scenario_id"] == scenario_id]

    def _filter_time(
            self,
            df: pd.DataFrame,
            start_ts: Optional[pd.Timestamp],
            end_ts: Optional[pd.Timestamp],
            time_col: str = "timestamp",
    ) -> pd.DataFrame:
        """Filter a dataframe by a timestamp window if the time column exists."""
        if time_col not in df.columns:
            return df
        if start_ts is not None:
            df = df[df[time_col] >= start_ts]
        if end_ts is not None:
            df = df[df[time_col] <= end_ts]
        return df

    def _window_fraction(
            self,
            start_ts: pd.Timestamp,
            end_ts: pd.Timestamp,
    ) -> float:
        """Return the fraction of total timesteps that fall inside [start_ts, end_ts]."""
        window_index = self._time_index[(self._time_index >= start_ts) & (self._time_index <= end_ts)]
        total_steps = max(1, len(self._time_index))
        window_steps = max(1, len(window_index))
        return float(window_steps) / float(total_steps) if total_steps else 1.0

    def _hours_in_window(
            self,
            start_ts: pd.Timestamp,
            end_ts: pd.Timestamp,
    ) -> float:
        """Return total hours represented by the window based on timestep spacing."""
        window_index = self._time_index[(self._time_index >= start_ts) & (self._time_index <= end_ts)]
        if len(window_index) > 1:
            step_hours = (window_index[1] - window_index[0]).total_seconds() / 3600.0
        else:
            step_hours = 1.0
        return max(1.0, len(window_index) * step_hours)

    def _top_n_grouped_series(
            self,
            df: pd.DataFrame,
            group_key: str,
            value_key: str,
            time_key: str,
            freq: str,
            top_n: int,
    ) -> pd.DataFrame:
        """Group a timeseries by top-N groups (others collapsed into 'Other')."""
        if df.empty:
            return pd.DataFrame(columns=["group_label", time_key, value_key])
        totals = df.groupby(group_key)[value_key].sum().sort_values(ascending=False)
        top_keys = set(totals.head(top_n).index.tolist())
        series = df.copy()
        series["group_label"] = series[group_key].apply(lambda x: x if x in top_keys else "Other")
        return (
            series.groupby(["group_label", pd.Grouper(key=time_key, freq=freq)])[value_key]
            .sum()
            .reset_index()
        )

    def get_scenarios(self) -> List[str]:
        """Return all scenario identifiers present in the results."""
        return list(self._scenario_ids)

    def normalize_scenario(self, scenario: str) -> str:
        """Return a known scenario id (case-insensitive), falling back to the first scenario."""
        if scenario in self._scenario_ids:
            return scenario
        for s in self._scenario_ids:
            if str(s).lower() == str(scenario).lower():
                return s
        return self._scenario_ids[0]

    def get_timesteps(self) -> List:
        """Return timesteps as stored in results (raw values)."""
        try:
            return list(self.results.timesteps.values)
        except Exception:
            return []

    def get_timesteps_datetime(self) -> pd.DatetimeIndex:
        """Return timesteps parsed as pandas datetime (falls back to raw if parsing fails)."""
        return self._time_index

    def get_locations(self) -> List[str]:
        """Return all locations present in results."""
        if "locs" in self.results.coords:
            return [str(x) for x in list(self.results.locs.values)]
        locs = set()
        if "loc_techs" in self.results.coords:
            for val in self.results.loc_techs.values:
                loc, _ = self._split_loc_tech(val)
                if loc:
                    locs.add(loc)
        return sorted(locs)

    def get_technologies(
            self,
            include_demand: bool = False,
            include_transmission: bool = False,
    ) -> List[str]:
        """
        Return all technologies present in results.

        Parameters
        ----------
        include_demand : bool
            If False, demand techs are excluded (requires inputs to infer tech categories).
        include_transmission : bool
            If False, transmission techs are excluded.
        """
        techs = set()
        if "loc_techs" in self.results.coords:
            for val in self.results.loc_techs.values:
                _, tech = self._split_loc_tech(val)
                if not tech:
                    continue
                if not include_transmission and self._is_transmission(tech):
                    continue
                if not include_demand and self._is_demand(tech):
                    continue
                techs.add(self._humanize_tech(tech))
        return sorted(techs)

    def get_technology_color_map(self, include_fallback: bool = True) -> Dict[str, str]:
        """
        Return a mapping of humanized technology labels to colors.

        If include_fallback is True, missing tech colors are assigned from a fixed palette
        deterministically (sorted by label) to ensure consistency across charts.
        """
        color_map = dict(self._label_color_map)
        if not include_fallback:
            return color_map

        labels = set(color_map.keys())
        try:
            labels.update(self.get_technologies(include_demand=True, include_transmission=True))
        except Exception:
            pass

        missing = [label for label in labels if label not in color_map]
        category_map = self._categorize_labels(missing)
        for category, labels_in_cat in category_map.items():
            palette = self._category_palette(category)
            for i, label in enumerate(sorted(labels_in_cat)):
                color_map[label] = palette[i % len(palette)]
        return color_map

    def _categorize_labels(self, labels: List[str]) -> Dict[str, List[str]]:
        """Group labels by inferred category using keyword matching."""
        categories: Dict[str, List[str]] = {}
        for label in labels:
            category = self._infer_category(label)
            categories.setdefault(category, []).append(label)
        return categories

    def _infer_category(self, label: str) -> str:
        """Infer a category name from a label using English keyword substrings."""
        text = str(label).lower()
        category_keywords = {
            "solar": ["solar", "pv", "photovoltaic"],
            "wind": ["wind"],
            "hydro": ["hydro", "hydropower", "water", "dam", "river"],
            "coal": ["coal"],
            "gas": ["gas", "ccgt", "gt"],
            "storage": ["storage", "battery"],
            "transmission": ["transmission", "line", "grid", "interconnector"],
            "demand": ["demand", "load"],
        }
        for category, keywords in category_keywords.items():
            for kw in keywords:
                if kw in text:
                    return category
        return "other"

    def _category_palette(self, category: str) -> List[str]:
        """Return a deterministic color palette for a given category name."""
        palettes = {
            "solar": ["#F2C94C", "#F4D35E", "#E9B949", "#E6B422", "#F6E27F"],
            "wind": ["#6FB8E6", "#4C9AD4", "#2F7DBE", "#1F66A5", "#15588F"],
            "hydro": ["#2E6FBE", "#2A76C6", "#1F5A9E", "#164A86", "#0F3A6E"],
            "coal": ["#4B4B4B", "#3C3C3C", "#2E2E2E", "#5A5A5A", "#1F1F1F"],
            "gas": ["#D39C5A", "#C8833E", "#B36C2D", "#9E5A24", "#E1B072"],
            "storage": ["#2A9D8F", "#1F887C", "#3BB2A4", "#14695F", "#5BC8BD"],
            "transmission": ["#8E7CC3", "#7A68B0", "#6A5AA0", "#5A4A90", "#A091D1"],
            "demand": ["#8B0000", "#A61C1C", "#B22222", "#7A0000", "#9E0B0B"],
            "other": [
                "#4C78A8",
                "#F58518",
                "#54A24B",
                "#E45756",
                "#72B7B2",
                "#EECA3B",
                "#B279A2",
                "#FF9DA6",
                "#9D755D",
                "#BAB0AC",
            ],
        }
        return palettes.get(category, palettes["other"])

    def get_carriers(self) -> List[str]:
        """Return all carriers present in results."""
        if "carriers" in self.results.coords:
            return [str(x) for x in list(self.results.carriers.values)]
        carriers = set()
        if "loc_tech_carriers_prod" in self.results.coords:
            for val in self.results.loc_tech_carriers_prod.values:
                _, _, carrier = self._split_loc_tech_carrier(val)
                if carrier:
                    carriers.add(carrier)
        return sorted(carriers)

    def normalize_carrier(self, carrier: str) -> str:
        """Return a known carrier id (case-insensitive), falling back to the first carrier."""
        carriers = self.get_carriers()
        if not carriers:
            return str(carrier)
        if carrier in carriers:
            return carrier
        for c in carriers:
            if str(c).lower() == str(carrier).lower():
                return c
        return carriers[0]

    def carrier_label(self, carrier: str) -> str:
        """Return a display label for a carrier (CO2 is normalized)."""
        if str(carrier).lower() in ["co2", "co₂"]:
            return "CO2"
        return str(carrier).title()

    def _build_assets_df(self) -> pd.DataFrame:
        """Build asset-level planning data (capacity/costs/category) from results/inputs."""
        try:
            cap_df = self._dataarray_to_df(self.results.energy_cap, "built_capacity_kw")
        except Exception:
            cap_df = pd.DataFrame(columns=["loc_techs", "built_capacity_kw", "scenario_id"])

        if "loc_techs" in cap_df.columns:
            cap_df[["location", "technology_raw"]] = cap_df["loc_techs"].apply(
                lambda x: pd.Series(self._split_loc_tech(x))
            )
        else:
            cap_df["location"] = ""
            cap_df["technology_raw"] = ""

        cap_df["technology"] = cap_df["technology_raw"].apply(self._humanize_tech)
        cap_df["built_capacity_kw"] = cap_df["built_capacity_kw"].fillna(0.0)
        cap_df = cap_df[~cap_df["technology_raw"].apply(self._is_transmission)]

        capex_df = pd.DataFrame(columns=["scenario_id", "location", "technology", "capex_eur"])
        capex_source = None
        if hasattr(self.results, "cost_investment"):
            capex_source = self.results.cost_investment
        elif hasattr(self.results, "cost_investment_rhs"):
            capex_source = self.results.cost_investment_rhs
        if capex_source is not None:
            try:
                inv_df = self._dataarray_to_df(capex_source, "capex_eur", select_cost=True)
                inv_df[["location", "technology_raw"]] = inv_df["loc_techs_investment_cost"].apply(
                    lambda x: pd.Series(self._split_loc_tech(x))
                )
                inv_df["technology"] = inv_df["technology_raw"].apply(self._humanize_tech)
                inv_df = inv_df[~inv_df["technology_raw"].apply(self._is_transmission)]
                capex_df = inv_df[["scenario_id", "location", "technology", "capex_eur"]]
            except Exception:
                warnings.warn("Unable to parse capex from results.")

        cost_df = pd.DataFrame(columns=["scenario_id", "location", "technology", "total_cost_eur"])
        if hasattr(self.results, "cost"):
            try:
                tot_df = self._dataarray_to_df(self.results.cost, "total_cost_eur", select_cost=True)
                tot_df[["location", "technology_raw"]] = tot_df["loc_techs_cost"].apply(
                    lambda x: pd.Series(self._split_loc_tech(x))
                )
                tot_df["technology"] = tot_df["technology_raw"].apply(self._humanize_tech)
                tot_df = tot_df[~tot_df["technology_raw"].apply(self._is_transmission)]
                cost_df = tot_df[["scenario_id", "location", "technology", "total_cost_eur"]]
            except Exception:
                warnings.warn("Unable to parse total cost from results.")

        assets = cap_df.merge(capex_df, on=["scenario_id", "location", "technology"], how="left")
        assets = assets.merge(cost_df, on=["scenario_id", "location", "technology"], how="left")
        assets[["capex_eur", "total_cost_eur"]] = assets[["capex_eur", "total_cost_eur"]].fillna(0.0)

        if self.inputs is not None and hasattr(self.inputs, "cost_om_annual"):
            try:
                om_df = self._dataarray_to_df(self.inputs.cost_om_annual, "fixed_opex_rate", select_cost=True)
                om_df[["location", "technology_raw"]] = om_df["loc_techs_investment_cost"].apply(
                    lambda x: pd.Series(self._split_loc_tech(x))
                )
                om_df["technology"] = om_df["technology_raw"].apply(self._humanize_tech)
                om_df = om_df[~om_df["technology_raw"].apply(self._is_transmission)]
                om_df = om_df[["scenario_id", "location", "technology", "fixed_opex_rate"]]
                if om_df["scenario_id"].nunique() == 1 and len(self._scenario_ids) > 1:
                    om_df = pd.concat(
                        [om_df.assign(scenario_id=sc) for sc in self._scenario_ids],
                        ignore_index=True,
                    )
                assets = assets.merge(om_df, on=["scenario_id", "location", "technology"], how="left")
                assets["fixed_opex_eur"] = assets["fixed_opex_rate"] * assets["built_capacity_kw"]
            except Exception:
                warnings.warn("Unable to parse cost_om_annual from inputs.")
                assets["fixed_opex_eur"] = 0.0
        else:
            assets["fixed_opex_eur"] = assets["total_cost_eur"] - assets["capex_eur"]
        assets["fixed_opex_eur"] = assets["fixed_opex_eur"].clip(lower=0.0)
        assets["category"] = assets["technology_raw"].apply(
            lambda x: self._tech_category_map.get(str(x).split(":", 1)[0], "")
        )
        return assets[
            [
                "scenario_id",
                "location",
                "technology",
                "technology_raw",
                "built_capacity_kw",
                "capex_eur",
                "fixed_opex_eur",
                "category",
            ]
        ]

    def _build_energy_df(self) -> pd.DataFrame:
        """Build production time series dataframe from results.carrier_prod."""
        if not hasattr(self.results, "carrier_prod"):
            return pd.DataFrame(
                columns=["scenario_id", "timestamp", "location", "technology", "technology_raw", "carrier",
                         "energy_kwh"]
            )
        prod_df = self._dataarray_to_df(self.results.carrier_prod, "energy_kwh")
        prod_df[["location", "technology_raw", "carrier"]] = prod_df["loc_tech_carriers_prod"].apply(
            lambda x: pd.Series(self._split_loc_tech_carrier(x))
        )
        prod_df["technology"] = prod_df["technology_raw"].apply(self._humanize_tech)
        prod_df["timestamp"] = pd.to_datetime(prod_df["timesteps"], errors="coerce")
        prod_df["energy_kwh"] = prod_df["energy_kwh"].fillna(0.0)
        prod_df = prod_df[~prod_df["technology_raw"].apply(self._is_transmission)]
        return prod_df[
            ["scenario_id", "timestamp", "location", "technology", "technology_raw", "carrier", "energy_kwh"]
        ]

    def _build_consumption_df(self) -> pd.DataFrame:
        """Build consumption time series dataframe from results.carrier_con."""
        if not hasattr(self.results, "carrier_con"):
            return pd.DataFrame(
                columns=["scenario_id", "timestamp", "location", "technology", "technology_raw", "carrier",
                         "energy_kwh"]
            )
        con_df = self._dataarray_to_df(self.results.carrier_con, "energy_kwh")
        con_df[["location", "technology_raw", "carrier"]] = con_df["loc_tech_carriers_con"].apply(
            lambda x: pd.Series(self._split_loc_tech_carrier(x))
        )
        con_df["technology"] = con_df["technology_raw"].apply(self._humanize_tech)
        con_df["timestamp"] = pd.to_datetime(con_df["timesteps"], errors="coerce")
        con_df["energy_kwh"] = con_df["energy_kwh"].fillna(0.0)
        con_df = con_df[~con_df["technology_raw"].apply(self._is_transmission)]
        return con_df[
            ["scenario_id", "timestamp", "location", "technology", "technology_raw", "carrier", "energy_kwh"]
        ]

    def _build_variable_cost_df(self) -> pd.DataFrame:
        """Build variable OPEX time series dataframe from results.cost_var/cost_var_rhs."""
        if not hasattr(self.results, "cost_var") and not hasattr(self.results, "cost_var_rhs"):
            return pd.DataFrame(
                columns=["scenario_id", "timestamp", "location", "technology", "technology_raw", "variable_opex_eur"]
            )
        source = self.results.cost_var if hasattr(self.results, "cost_var") else self.results.cost_var_rhs
        var_df = self._dataarray_to_df(source, "variable_opex_eur", select_cost=True)
        var_df[["location", "technology_raw"]] = var_df["loc_techs_om_cost"].apply(
            lambda x: pd.Series(self._split_loc_tech(x))
        )
        var_df["technology"] = var_df["technology_raw"].apply(self._humanize_tech)
        var_df["timestamp"] = pd.to_datetime(var_df["timesteps"], errors="coerce")
        var_df["variable_opex_eur"] = var_df["variable_opex_eur"].fillna(0.0)
        var_df = var_df[~var_df["technology_raw"].apply(self._is_transmission)]
        return var_df[
            ["scenario_id", "timestamp", "location", "technology", "technology_raw", "variable_opex_eur"]
        ]

    def _build_emissions_df(self) -> pd.DataFrame:
        """Build CO2 time series dataframe using the CO2 cost key if present."""
        if not hasattr(self.results, "cost_var") and not hasattr(self.results, "cost_var_rhs"):
            return pd.DataFrame(
                columns=["scenario_id", "timestamp", "location", "technology", "technology_raw", "co2_kg"]
            )
        co2_key = self._resolve_cost_key("co2")
        if not co2_key:
            return pd.DataFrame(
                columns=["scenario_id", "timestamp", "location", "technology", "technology_raw", "co2_kg"]
            )
        source = self.results.cost_var if hasattr(self.results, "cost_var") else self.results.cost_var_rhs
        co2_df = self._dataarray_to_df(source, "co2_kg", select_cost=True, cost_key=co2_key)
        co2_df[["location", "technology_raw"]] = co2_df["loc_techs_om_cost"].apply(
            lambda x: pd.Series(self._split_loc_tech(x))
        )
        co2_df["technology"] = co2_df["technology_raw"].apply(self._humanize_tech)
        co2_df["timestamp"] = pd.to_datetime(co2_df["timesteps"], errors="coerce")
        co2_df["co2_kg"] = co2_df["co2_kg"].fillna(0.0)
        co2_df = co2_df[~co2_df["technology_raw"].apply(self._is_transmission)]
        return co2_df[
            ["scenario_id", "timestamp", "location", "technology", "technology_raw", "co2_kg"]
        ]

    def _build_demand_df(self) -> pd.DataFrame:
        """Build demand time series dataframe from required_resource and carrier lookup."""
        if not hasattr(self.results, "required_resource"):
            return pd.DataFrame(columns=["scenario_id", "timestamp", "location", "carrier", "demand_kwh"])
        carrier_map = self._build_loc_tech_carrier_map()
        if not carrier_map:
            return pd.DataFrame(columns=["scenario_id", "timestamp", "location", "carrier", "demand_kwh"])

        req_df = self._dataarray_to_df(self.results.required_resource, "demand_kwh")
        req_df[["location", "technology_raw"]] = req_df["loc_techs_balance_demand_constraint"].apply(
            lambda x: pd.Series(self._split_loc_tech(x))
        )
        req_df["carrier"] = req_df["loc_techs_balance_demand_constraint"].map(carrier_map).fillna("")
        req_df["timestamp"] = pd.to_datetime(req_df["timesteps"], errors="coerce")
        req_df["demand_kwh"] = req_df["demand_kwh"].fillna(0.0).abs()
        req_df = req_df[req_df["carrier"] != ""]
        return req_df[
            ["scenario_id", "timestamp", "location", "carrier", "demand_kwh"]
        ]

    def _build_loc_tech_carrier_map(self) -> Dict[str, str]:
        """Build a map from 'loc::tech' to carrier using inputs lookup tables."""
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

    def _get_conversion_io(self, loc_tech: str) -> Dict[str, List[str]]:
        cached = self._conversion_io_cache.get(loc_tech)
        if cached is not None:
            return cached
        io: Dict[str, List[str]] = {"in": [], "out": [], "out_2": []}
        if self.inputs is None or not hasattr(self.inputs, "loc_techs_conversion_plus"):
            self._conversion_io_cache[loc_tech] = io
            return io
        try:
            if loc_tech not in list(self.inputs.loc_techs_conversion_plus.values):
                self._conversion_io_cache[loc_tech] = io
                return io
            lookup = self.inputs.lookup_loc_techs_conversion_plus
            tiers = list(lookup.coords["carrier_tiers"].values)
            for tier in tiers:
                try:
                    vals = lookup.sel(carrier_tiers=tier, loc_techs_conversion_plus=loc_tech).values
                except Exception:
                    continue
                arr = np.asarray(vals).reshape(-1)
                for val in arr:
                    if val is None:
                        continue
                    val_str = str(val)
                    if not val_str or val_str.lower() == "nan":
                        continue
                    parts = val_str.split("::")
                    if len(parts) >= 3:
                        io.setdefault(str(tier), []).append(parts[2])
        except Exception:
            pass
        self._conversion_io_cache[loc_tech] = io
        return io

    def _get_conversion_ratios(self, loc_tech: str) -> Dict[Tuple[str, str], float]:
        cached = self._conversion_ratio_cache.get(loc_tech)
        if cached is not None:
            return cached
        ratios: Dict[Tuple[str, str], float] = {}
        if self.inputs is None or not hasattr(self.inputs, "carrier_ratios") or not hasattr(self.inputs, "loc_tech_carriers_conversion_plus"):
            self._conversion_ratio_cache[loc_tech] = ratios
            return ratios
        prefix = f"{loc_tech}::"
        try:
            tiers = list(self.inputs.carrier_ratios.coords["carrier_tiers"].values)
            for ltc in self.inputs.loc_tech_carriers_conversion_plus.values:
                ltc_str = str(ltc)
                if not ltc_str.startswith(prefix):
                    continue
                carrier = ltc_str.split("::", 2)[2]
                for tier in tiers:
                    try:
                        val = self.inputs.carrier_ratios.sel(
                            carrier_tiers=tier,
                            loc_tech_carriers_conversion_plus=ltc,
                        ).values
                    except Exception:
                        continue
                    arr = np.asarray(val).reshape(-1)
                    if arr.size:
                        try:
                            ratios[(str(tier), carrier)] = float(arr[0])
                        except Exception:
                            continue
        except Exception:
            pass
        self._conversion_ratio_cache[loc_tech] = ratios
        return ratios

    def _get_energy_eff_max(self, loc_tech: str) -> float:
        cached = self._energy_eff_max_cache.get(loc_tech)
        if cached is not None:
            return cached
        if self.inputs is None or not hasattr(self.inputs, "energy_eff"):
            self._energy_eff_max_cache[loc_tech] = 1.0
            return 1.0
        try:
            if "loc_techs" in self.inputs.energy_eff.dims:
                vals = self.inputs.energy_eff.sel(loc_techs=loc_tech).values
            else:
                idx = list(self.inputs.loc_techs.values).index(loc_tech)
                vals = self.inputs.energy_eff.data[idx]
            arr = np.asarray(vals).astype(float)
            eff = float(np.nanmax(arr))
            if eff <= 0 or np.isnan(eff):
                eff = 1.0
        except Exception:
            eff = 1.0
        self._energy_eff_max_cache[loc_tech] = eff
        return eff

    def _capacity_for_carrier(
            self,
            location: str,
            technology_raw: str,
            built_capacity_kw: float,
            carrier_key: str,
    ) -> float:
        try:
            base_cap = float(built_capacity_kw)
        except Exception:
            return 0.0
        if base_cap <= 0:
            return 0.0

        loc_tech = f"{location}::{technology_raw}"
        if self._is_conversion(technology_raw):
            io = self._get_conversion_io(loc_tech)
            ratios = self._get_conversion_ratios(loc_tech)
            if carrier_key in io.get("out", []):
                ratio = ratios.get(("out", carrier_key), 1.0)
                return base_cap * ratio
            if carrier_key in io.get("out_2", []):
                ratio = ratios.get(("out_2", carrier_key), 1.0)
                return base_cap * ratio
            if carrier_key in io.get("in", []):
                eff = self._get_energy_eff_max(loc_tech)
                return base_cap / eff if eff > 0 else base_cap
            return 0.0

        carrier_map = self._build_loc_tech_carrier_map()
        if carrier_map.get(loc_tech) != carrier_key:
            return 0.0
        return base_cap

    def get_plan_assets(self, scenario_id: Optional[str] = None) -> pd.DataFrame:
        """
        Return asset-level planning data.

        Columns: scenario_id, location, technology, technology_raw, built_capacity_kw,
        capex_eur, fixed_opex_eur, category.
        """
        if self._assets_df is None:
            self._assets_df = self._build_assets_df()
        df = self._assets_df.copy()
        scenario_key = self.normalize_scenario(scenario_id) if scenario_id else None
        return self._filter_scenario(df, scenario_key)

    def get_plan_energy(
            self,
            scenario_id: Optional[str] = None,
            start_ts: Optional[pd.Timestamp] = None,
            end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Return production time series data.

        Columns: scenario_id, timestamp, location, technology, technology_raw, carrier, energy_kwh.
        """
        if self._energy_df is None:
            self._energy_df = self._build_energy_df()
        df = self._energy_df.copy()
        scenario_key = self.normalize_scenario(scenario_id) if scenario_id else None
        df = self._filter_scenario(df, scenario_key)
        return self._filter_time(df, start_ts, end_ts)

    def get_plan_consumption(
            self,
            scenario_id: Optional[str] = None,
            start_ts: Optional[pd.Timestamp] = None,
            end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Return consumption time series data.

        Columns: scenario_id, timestamp, location, technology, technology_raw, carrier, energy_kwh.
        """
        if self._con_df is None:
            self._con_df = self._build_consumption_df()
        df = self._con_df.copy()
        scenario_key = self.normalize_scenario(scenario_id) if scenario_id else None
        df = self._filter_scenario(df, scenario_key)
        return self._filter_time(df, start_ts, end_ts)

    def get_plan_variable_costs(
            self,
            scenario_id: Optional[str] = None,
            start_ts: Optional[pd.Timestamp] = None,
            end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Return variable OPEX time series data.

        Columns: scenario_id, timestamp, location, technology, technology_raw, variable_opex_eur.
        """
        if self._var_cost_df is None:
            self._var_cost_df = self._build_variable_cost_df()
        df = self._var_cost_df.copy()
        scenario_key = self.normalize_scenario(scenario_id) if scenario_id else None
        df = self._filter_scenario(df, scenario_key)
        return self._filter_time(df, start_ts, end_ts)

    def get_plan_emissions(
            self,
            scenario_id: Optional[str] = None,
            start_ts: Optional[pd.Timestamp] = None,
            end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Return emissions time series data (CO2 from variable costs).

        Columns: scenario_id, timestamp, location, technology, technology_raw, co2_kg.
        """
        if self._emissions_df is None:
            self._emissions_df = self._build_emissions_df()
        df = self._emissions_df.copy()
        scenario_key = self.normalize_scenario(scenario_id) if scenario_id else None
        df = self._filter_scenario(df, scenario_key)
        return self._filter_time(df, start_ts, end_ts)

    def get_plan_demand(
            self,
            scenario_id: Optional[str] = None,
            start_ts: Optional[pd.Timestamp] = None,
            end_ts: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Return demand time series data.

        Columns: scenario_id, timestamp, location, carrier, demand_kwh.
        """
        if self._demand_df is None:
            self._demand_df = self._build_demand_df()
        df = self._demand_df.copy()
        scenario_key = self.normalize_scenario(scenario_id) if scenario_id else None
        df = self._filter_scenario(df, scenario_key)
        return self._filter_time(df, start_ts, end_ts)

    def resolve_plan_selection(
            self,
            view_mode: str,
            selected_location: Optional[str],
            selected_tech: Optional[str],
    ) -> Dict[str, str]:
        """
        Resolve selection parameters for the planning dashboard.

        Returns a dict with keys: group_key, selection_key, selection_value.
        """
        locations = self.get_locations()
        techs = self.get_technologies()

        if view_mode == "technology":
            group_key = "location"
            selection_key = "technology"
            selection_value = selected_tech if selected_tech in techs else (techs[0] if techs else "")
        else:
            group_key = "technology"
            selection_key = "location"
            selection_value = selected_location if selected_location in locations else (
                locations[0] if locations else "")

        return {
            "group_key": group_key,
            "selection_key": selection_key,
            "selection_value": selection_value,
        }

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
        """Return KPI totals for the current planning selection."""
        scenario_key = self.normalize_scenario(scenario_id)
        carrier_key = self.normalize_carrier(carrier)
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        assets = self.get_plan_assets(scenario_id=scenario_key)
        energy = self.get_plan_energy(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        var_costs = self.get_plan_variable_costs(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        emissions = self.get_plan_emissions(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)

        assets_sel = assets[assets[selection_key] == selection_value]
        energy_sel = energy[energy[selection_key] == selection_value]
        var_sel = var_costs[var_costs[selection_key] == selection_value]
        emissions_sel = emissions[emissions[selection_key] == selection_value]

        window_fraction = self._window_fraction(start_ts, end_ts)

        total_cap = float(assets_sel["built_capacity_kw"].sum())
        total_capex = float(assets_sel["capex_eur"].sum())
        total_fixed = float(assets_sel["fixed_opex_eur"].sum() * window_fraction)
        total_var = float(var_sel["variable_opex_eur"].sum())
        total_prod = float(energy_sel[energy_sel["carrier"] == carrier_key]["energy_kwh"].sum())
        total_co2 = float(emissions_sel["co2_kg"].sum())

        return {
            "capacity": total_cap,
            "capex": total_capex,
            "opex": total_fixed + total_var,
            "production": total_prod,
            "co2_kg": total_co2,
        }

    def get_plan_capacity_group(
            self,
            scenario_id: str,
            carrier: str,
            view_mode: str,
            selected_location: Optional[str],
            selected_tech: Optional[str],
    ) -> pd.DataFrame:
        """Return grouped capacity data for the current selection and carrier."""
        scenario_key = self.normalize_scenario(scenario_id)
        carrier_key = self.normalize_carrier(carrier)
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        assets = self.get_plan_assets(scenario_id=scenario_key)
        assets_sel = assets[assets[selection_key] == selection_value].copy()
        if assets_sel.empty:
            return assets_sel

        assets_sel["carrier_capacity_kw"] = assets_sel.apply(
            lambda row: self._capacity_for_carrier(
                row["location"],
                row["technology_raw"],
                row["built_capacity_kw"],
                carrier_key,
            ),
            axis=1,
        )
        assets_sel = assets_sel[assets_sel["carrier_capacity_kw"] > 0]
        if assets_sel.empty:
            return assets_sel

        return (
            assets_sel.groupby(group_key, as_index=False)["carrier_capacity_kw"]
            .sum()
            .sort_values("carrier_capacity_kw", ascending=False)
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
        """Return grouped cost data (capex/fixed/variable) for the selection."""
        scenario_key = self.normalize_scenario(scenario_id)
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        assets = self.get_plan_assets(scenario_id=scenario_key)
        var_costs = self.get_plan_variable_costs(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)

        assets_sel = assets[assets[selection_key] == selection_value]
        var_sel = var_costs[var_costs[selection_key] == selection_value]

        window_fraction = self._window_fraction(start_ts, end_ts)

        cost_group = assets_sel.groupby(group_key, as_index=False)[
            ["capex_eur", "fixed_opex_eur", "built_capacity_kw"]
        ].sum()
        var_group = var_sel.groupby(group_key, as_index=False)["variable_opex_eur"].sum()
        cost_group = pd.merge(cost_group, var_group, on=group_key, how="left").fillna(0.0)
        cost_group["fixed_opex_eur"] = cost_group["fixed_opex_eur"] * window_fraction
        return cost_group

    def get_plan_co2_group(
            self,
            scenario_id: str,
            start_ts: pd.Timestamp,
            end_ts: pd.Timestamp,
            view_mode: str,
            selected_location: Optional[str],
            selected_tech: Optional[str],
    ) -> pd.DataFrame:
        """Return grouped CO2 totals for the selection."""
        scenario_key = self.normalize_scenario(scenario_id)
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        emissions = self.get_plan_emissions(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        emissions_sel = emissions[emissions[selection_key] == selection_value]
        return emissions_sel.groupby(group_key, as_index=False)["co2_kg"].sum()

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
        """Return grouped CO2 timeseries (top-N + Other) for the selection."""
        scenario_key = self.normalize_scenario(scenario_id)
        cache_key = (
            "co2_ts",
            scenario_key,
            start_ts,
            end_ts,
            view_mode,
            selected_location,
            selected_tech,
            top_n,
        )
        cached = self._plan_ts_cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        emissions = self.get_plan_emissions(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        emissions_sel = emissions[emissions[selection_key] == selection_value]
        res = self._top_n_grouped_series(
            emissions_sel,
            group_key=group_key,
            value_key="co2_kg",
            time_key="timestamp",
            freq="H",
            top_n=top_n,
        )
        self._plan_ts_cache[cache_key] = res
        return res.copy()

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
        """Return grouped production timeseries (top-N + Other) for the selection."""
        scenario_key = self.normalize_scenario(scenario_id)
        carrier_key = self.normalize_carrier(carrier)
        cache_key = (
            "prod_ts",
            scenario_key,
            carrier_key,
            start_ts,
            end_ts,
            view_mode,
            selected_location,
            selected_tech,
            top_n,
        )
        cached = self._plan_ts_cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        energy = self.get_plan_energy(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        energy_sel = energy[energy[selection_key] == selection_value]
        energy_carrier = energy_sel[energy_sel["carrier"] == carrier_key]
        res = self._top_n_grouped_series(
            energy_carrier,
            group_key=group_key,
            value_key="energy_kwh",
            time_key="timestamp",
            freq="H",
            top_n=top_n,
        )
        self._plan_ts_cache[cache_key] = res
        return res.copy()

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
        """
        Return demand timeseries for the current selection.

        Demand is only returned when viewing by location (never for technology view).
        """
        if view_mode != "location":
            return pd.DataFrame(columns=["timestamp", "demand_kwh"])
        scenario_key = self.normalize_scenario(scenario_id)
        carrier_key = self.normalize_carrier(carrier)
        cache_key = (
            "demand_ts",
            scenario_key,
            carrier_key,
            start_ts,
            end_ts,
            view_mode,
            selected_location,
            selected_tech,
        )
        cached = self._plan_ts_cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        selection_value = selection["selection_value"]

        demand = self.get_plan_demand(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        demand_carrier = demand[demand["carrier"] == carrier_key]
        demand_carrier = demand_carrier[demand_carrier["location"] == selection_value]
        demand_ts = (
            demand_carrier.groupby(pd.Grouper(key="timestamp", freq="H"))["demand_kwh"]
            .sum()
        )

        conv_inputs = self.get_plan_consumption(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        conv_inputs = conv_inputs[
            (conv_inputs["carrier"] == carrier_key)
            & (conv_inputs["location"] == selection_value)
            & (conv_inputs["technology_raw"].apply(self._is_conversion))
        ]
        conv_ts = (
            conv_inputs.groupby(pd.Grouper(key="timestamp", freq="H"))["energy_kwh"]
            .sum()
        )
        conv_ts = conv_ts.abs()

        combined = demand_ts.add(conv_ts, fill_value=0.0)
        combined.name = "demand_kwh"
        if combined.empty:
            return pd.DataFrame(columns=["timestamp", "demand_kwh"])
        res = combined.reset_index()
        self._plan_ts_cache[cache_key] = res
        return res.copy()

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
        """Return detail table data for the current selection."""
        scenario_key = self.normalize_scenario(scenario_id)
        carrier_key = self.normalize_carrier(carrier)
        selection = self.resolve_plan_selection(view_mode, selected_location, selected_tech)
        group_key = selection["group_key"]
        selection_key = selection["selection_key"]
        selection_value = selection["selection_value"]

        assets = self.get_plan_assets(scenario_id=scenario_key)
        energy = self.get_plan_energy(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        var_costs = self.get_plan_variable_costs(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)
        emissions = self.get_plan_emissions(scenario_id=scenario_key, start_ts=start_ts, end_ts=end_ts)

        assets_sel = assets[assets[selection_key] == selection_value]
        energy_sel = energy[energy[selection_key] == selection_value]
        var_sel = var_costs[var_costs[selection_key] == selection_value]
        emissions_sel = emissions[emissions[selection_key] == selection_value]

        window_fraction = self._window_fraction(start_ts, end_ts)

        table_assets = assets_sel.groupby(group_key, as_index=False)[
            ["built_capacity_kw", "capex_eur", "fixed_opex_eur"]
        ].sum()
        table_assets["fixed_opex_eur"] = table_assets["fixed_opex_eur"] * window_fraction
        table_var = var_sel.groupby(group_key, as_index=False)["variable_opex_eur"].sum()
        table_prod = energy_sel[energy_sel["carrier"] == carrier_key].groupby(group_key, as_index=False)[
            "energy_kwh"
        ].sum()
        table = table_assets.merge(table_var, on=group_key, how="left").merge(table_prod, on=group_key, how="left")
        co2_group = emissions_sel.groupby(group_key, as_index=False)["co2_kg"].sum()
        if not co2_group.empty:
            table = table.merge(co2_group, on=group_key, how="left")
        if "co2_kg" not in table.columns:
            table["co2_kg"] = 0.0
        table = table.fillna(0.0).rename(columns={group_key: "Name"})

        hours_in_window = self._hours_in_window(start_ts, end_ts)
        table["capacity_factor"] = np.where(
            table["built_capacity_kw"] > 0,
            table["energy_kwh"] / (table["built_capacity_kw"] * hours_in_window),
            0.0,
        )

        if carrier_key.lower() != "co2":
            co2_energy = energy_sel[energy_sel["carrier"].str.lower() == "co2"].groupby(group_key, as_index=False)[
                "energy_kwh"
            ].sum()
            co2_energy.rename(columns={group_key: "Name", "energy_kwh": "co2_kwh"}, inplace=True)
            table = table.merge(co2_energy, on="Name", how="left").fillna(0.0)

        totals = {
            "Name": "Total",
            "built_capacity_kw": table["built_capacity_kw"].sum(),
            "capex_eur": table["capex_eur"].sum(),
            "fixed_opex_eur": table["fixed_opex_eur"].sum(),
            "variable_opex_eur": table["variable_opex_eur"].sum(),
            "energy_kwh": table["energy_kwh"].sum(),
            "capacity_factor": 0.0,
            "co2_kg": table["co2_kg"].sum() if "co2_kg" in table.columns else 0.0,
        }
        if totals["built_capacity_kw"] > 0:
            totals["capacity_factor"] = totals["energy_kwh"] / (totals["built_capacity_kw"] * hours_in_window)
        if "co2_kwh" in table.columns:
            totals["co2_kwh"] = table["co2_kwh"].sum()
        table = pd.concat([table, pd.DataFrame([totals])], ignore_index=True)
        return table
