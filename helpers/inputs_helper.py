"""Accessors for Calliope 0.7 model inputs."""

from typing import Optional

import numpy as np
import pandas as pd
import xarray as xr
from helpers.errors import fail


class InputsHelper:
    """Expose the input data used by the dashboard callbacks."""

    def __init__(self, inputs: xr.Dataset):
        assert isinstance(inputs, xr.Dataset)
        assert str(inputs.attrs.get("calliope_version", "")).startswith("0.7.0")
        self.inputs = inputs
        self._location_demand_cache: dict[tuple[str, str], list[np.ndarray]] = {}
        self._location_supply_cache: dict[tuple[str, str], dict[str, np.ndarray]] = {}

    def _tech_category(self, tech: str) -> str:
        try:
            return str(self.inputs.base_tech.sel(techs=tech).item())
        except Exception as exc:
            fail(f"Cannot read technology category for {tech}.", exc)

    def _is_defined(self, location: str, tech: str, carrier: Optional[str] = None) -> bool:
        try:
            values = self.inputs.definition_matrix.sel(nodes=location, techs=tech)
            if carrier is not None:
                values = values.sel(carriers=carrier)
            return bool(values.any().item())
        except Exception as exc:
            fail(f"Cannot read technology definition for {location}/{tech}/{carrier}.", exc)

    def _tech_scalar(self, name: str, tech: str, location: Optional[str] = None) -> float:
        if name not in self.inputs:
            return float("nan")
        try:
            values = self.inputs[name]
            selections = {"techs": tech} if "techs" in values.dims else {}
            if location is not None and "nodes" in values.dims:
                selections["nodes"] = location
            if "costs" in values.dims:
                if "monetary" not in values.costs:
                    return float("nan")
                selections["costs"] = "monetary"
            value = np.asarray(values.sel(**selections).values, dtype=float)
            return float(value.reshape(-1)[0])
        except Exception as exc:
            fail(f"Cannot read input {name} for {location}/{tech}.", exc)

    def tech_is_conversion(self, tech_name: str) -> bool:
        return self._tech_category(tech_name) == "conversion"

    def tech_is_storage(self, tech_name: str) -> bool:
        return self._tech_category(tech_name) == "storage"

    def tech_is_demand(self, tech_name: str) -> bool:
        return self._tech_category(tech_name) == "demand"

    def get_locations(self) -> list[str]:
        return [str(value) for value in self.inputs.nodes.values]

    def get_loc_coords(self) -> list[tuple[str, float, float]]:
        result = []
        for location in self.get_locations():
            lon, lat = self.get_location_coordinates(location)
            if np.isfinite(lon) and np.isfinite(lat):
                result.append((location, lon, lat))
        return result

    def get_loc_coords_as_dict(self) -> dict[str, tuple[float, float]]:
        return {name: (lon, lat) for name, lon, lat in self.get_loc_coords()}

    def get_location_coordinates(self, location: str) -> tuple[float, float]:
        if "longitude" not in self.inputs or "latitude" not in self.inputs:
            return float("nan"), float("nan")
        try:
            lon = float(self.inputs.longitude.sel(nodes=location).item())
            lat = float(self.inputs.latitude.sel(nodes=location).item())
            return lon, lat
        except Exception as exc:
            fail(f"Cannot read coordinates for {location}.", exc)

    def get_location_techs(
        self, location: str, carrier_filter: Optional[str] = None
    ) -> list[tuple[str, str, str]]:
        result = []
        carriers = [carrier_filter] if carrier_filter else [str(c) for c in self.inputs.carriers.values]
        for tech in [str(value) for value in self.inputs.techs.values]:
            for carrier in carriers:
                if self._is_defined(location, tech, carrier):
                    result.append((location, tech, carrier))
        return result

    def get_location_carriers(self, location: str) -> list[str]:
        return sorted({item[2] for item in self.get_location_techs(location)})

    def get_location_area(self, location: str) -> float:
        if "available_area" not in self.inputs:
            return float("nan")
        try:
            return float(self.inputs.available_area.sel(nodes=location).item())
        except Exception as exc:
            fail(f"Cannot read available area for {location}.", exc)

    def get_location_demand(self, location: str, carrier: str) -> list[np.ndarray]:
        cache_key = (location, carrier)
        if cache_key in self._location_demand_cache:
            return self._location_demand_cache[cache_key]

        result = []
        if "sink_use_equals" in self.inputs:
            for _, tech, _ in self.get_location_techs(location, carrier):
                if self._tech_category(tech) != "demand":
                    continue
                try:
                    values = self.inputs.sink_use_equals.sel(nodes=location, techs=tech).values
                    values = np.asarray(values, dtype=float)
                    # A demand technology may have bounds without a fixed
                    # profile (e.g. export). That is unspecified, not zero.
                    if np.isnan(values).all():
                        continue
                    if np.isinf(values).any():
                        fail(f"Infinite fixed demand profile for {location}/{tech}.")
                    result.append(-np.abs(values))
                except Exception as exc:
                    fail(f"Cannot read demand for {location}/{tech}.", exc)
        self._location_demand_cache[cache_key] = result
        return result

    def get_location_total_max_supply(self, location: str, carrier: str) -> dict[str, np.ndarray]:
        cache_key = (location, carrier)
        if cache_key in self._location_supply_cache:
            return self._location_supply_cache[cache_key]

        result: dict[str, np.ndarray] = {}
        n_timesteps = len(self.inputs.timesteps)
        for _, tech, _ in self.get_location_techs(location, carrier):
            if self._tech_category(tech) != "supply":
                continue
            capacity = self.get_loc_tech_capacity(location, tech)
            if not np.isfinite(capacity):
                # No capacity bound means unbounded, never zero capacity.
                capacity = float("inf")
            def scalar(name, default):
                value = self._tech_scalar(name, tech, location)
                return value if np.isfinite(value) else default

            # Calliope flow arrays contain energy per timestep. Apply both the
            # resource constraint and the delivered-output capacity constraint.
            duration = np.asarray(self.inputs.timestep_resolution.values, dtype=float)
            parasitic = scalar("flow_out_parasitic_eff", 1.0)
            area = scalar("area_use_max", float("inf"))
            available_area = self.get_location_area(location)
            if np.isfinite(available_area):
                area = min(area, available_area)
            area_per_cap = scalar("area_use_per_flow_cap", 0.0)
            if area_per_cap > 0:
                capacity = min(capacity, area / area_per_cap)
                area = min(area, capacity * area_per_cap)
            values = np.zeros(n_timesteps) if capacity == 0 or parasitic == 0 else capacity * duration * parasitic
            if "source_use_max" in self.inputs:
                try:
                    source = self.inputs.source_use_max
                    selection = {"techs": tech}
                    if "nodes" in source.dims:
                        selection["nodes"] = location
                    resource = np.asarray(
                        source.sel(**selection).values,
                        dtype=float,
                    )
                    if not np.isnan(resource).all():
                        unit = str(self.inputs.source_unit.sel(techs=tech).item()) if "source_unit" in self.inputs else "absolute"
                        scale = capacity if unit == "per_cap" else area if unit == "per_area" else 1.0
                        # Preserve missing timestamps as gaps for the selected
                        # view, rather than inventing zero availability or
                        # rejecting valid dates because of a gap elsewhere.
                        resource = np.where(np.isneginf(resource), 0.0, resource)
                        resource_bound = np.zeros_like(resource)
                        np.multiply(resource, scale, out=resource_bound, where=(resource != 0) & (scale != 0))
                        efficiency = scalar("source_eff", 1.0) * scalar("flow_out_eff", 1.0) * parasitic
                        resource_bound = np.zeros_like(resource_bound) if efficiency == 0 else resource_bound * efficiency
                        values = np.minimum(values, resource_bound)
                except Exception as exc:
                    fail(f"Cannot read supply bounds for {location}/{tech}.", exc)
            result[f"{location}::{tech}"] = values
        self._location_supply_cache[cache_key] = result
        return result

    def get_loc_tech_capacity(self, location: str, tech: str) -> float:
        for name in ("flow_cap_equals", "flow_cap_max"):
            value = self._tech_scalar(name, tech, location)
            if np.isfinite(value):
                return value
        return float("nan")

    def get_loc_tech_energy_eff(self, location: str, tech: str) -> Optional[np.ndarray]:
        del location
        value = self._tech_scalar("flow_out_eff", tech)
        if not np.isfinite(value):
            return None
        return np.asarray([value])

    def get_conversion_tech_io(self, location: str, tech: str) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {"in": [], "out": [], "out_2": []}
        if not self.tech_is_conversion(tech):
            return result
        for carrier in [str(value) for value in self.inputs.carriers.values]:
            try:
                if bool(self.inputs.carrier_in.sel(nodes=location, techs=tech, carriers=carrier).item()):
                    result["in"].append(carrier)
                if bool(self.inputs.carrier_out.sel(nodes=location, techs=tech, carriers=carrier).item()):
                    result["out"].append(carrier)
            except Exception as exc:
                fail(f"Cannot read conversion carriers for {location}/{tech}.", exc)
        return result

    def get_conversion_carrier_ratios(
        self, location: str, tech: str
    ) -> dict[tuple[str, str], float]:
        io = self.get_conversion_tech_io(location, tech)
        return {("out", carrier): 1.0 for carrier in io["out"]}

    def get_loc_tech_carrier_stats(self, location: str, tech: str, carrier: str) -> dict[str, float]:
        del carrier
        details = {
            "energy_cap_max": self.get_loc_tech_capacity(location, tech),
            "energy_eff": self._tech_scalar("flow_out_eff", tech),
            "parasitic_eff": self._tech_scalar("flow_out_parasitic_eff", tech),
            "resource_area_max": self._tech_scalar("area_use_max", tech),
            "lifetime": self._tech_scalar("lifetime", tech),
        }
        if self.tech_is_storage(tech):
            details["storage_cap_max"] = self._tech_scalar("storage_cap_max", tech, location)
        return {key: value for key, value in details.items() if np.isfinite(value)}

    def get_transmission_lines(
        self,
    ) -> list[tuple[tuple[str, float, float], tuple[str, float, float]]]:
        coords = self.get_loc_coords_as_dict()
        result = []
        seen = set()
        for tech in [str(value) for value in self.inputs.techs.values]:
            if self._tech_category(tech) != "transmission":
                continue
            nodes = [node for node in self.get_locations() if self._is_defined(node, tech)]
            if len(nodes) != 2:
                continue
            a, b = sorted(nodes)
            if (a, b) in seen or a not in coords or b not in coords:
                continue
            seen.add((a, b))
            if not self.allows_transmission_flow(a, b):
                a, b = b, a
            result.append(((a, *coords[a]), (b, *coords[b])))
        return result

    def allows_transmission_flow(self, origin: str, destination: str, carrier: Optional[str] = None) -> bool:
        """Read permitted direction from the preprocessed carrier role masks."""
        for tech in self.inputs.techs.values:
            if self._tech_category(str(tech)) != "transmission":
                continue
            if not (self._is_defined(origin, str(tech)) and self._is_defined(destination, str(tech))):
                continue
            incoming = self.inputs.carrier_in.sel(nodes=origin, techs=tech)
            outgoing = self.inputs.carrier_out.sel(nodes=destination, techs=tech)
            if carrier is not None:
                incoming = incoming.sel(carriers=carrier)
                outgoing = outgoing.sel(carriers=carrier)
            if bool((incoming.astype(bool) & outgoing.astype(bool)).any()):
                return True
        return False

    def get_loc_tech_costs(self, location: str, tech: str) -> dict[str, float]:
        return {
            "cost_energy_cap": self._tech_scalar("cost_flow_cap", tech, location),
            "cost_storage_cap": self._tech_scalar("cost_storage_cap", tech, location),
            "cost_depreciation_rate": float("nan"),
            "cost_energy_cap_per_distance": float("nan"),
            "cost_om_con": self._tech_scalar("cost_flow_in", tech, location),
            "cost_om_prod": self._tech_scalar("cost_flow_out", tech, location),
        }

    def get_transmission_capacity(self, origin: str, destination: str) -> float:
        capacities = []
        for tech in [str(value) for value in self.inputs.techs.values]:
            if self._tech_category(tech) != "transmission":
                continue
            if self._is_defined(origin, tech) and self._is_defined(destination, tech):
                for node in (origin, destination):
                    value = self._tech_scalar("flow_cap_max", tech, node)
                    if np.isfinite(value):
                        capacities.append(value)
        return max(capacities) if capacities else float("nan")

    def get_timesteps(self) -> list:
        return list(self.inputs.timesteps.values)

    def get_timesteps_datetime(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(pd.to_datetime(self.get_timesteps()))

    def get_scenarios(self) -> list[str]:
        return ["default"]
