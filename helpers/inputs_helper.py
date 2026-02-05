# inputs_helper.py
import warnings

import xarray
import numpy as np


class InputsHelper:
    """
    A helper class to extract and organize information from Calliope's Model.inputs.

    This class wraps around the xarray.Dataset stored in `model.inputs`
    and provides user-friendly access to locations, technologies, and
    their associated parameters such as efficiency, lifetime, and resource
    time series.

    Parameters
    ----------
    inputs : calliope.Model.inputs
        A Calliope model.inputs instance of type xarray.Dataset.
    """

    def __init__(self, inputs: xarray.Dataset):
        # Making sure we got correct data (basically just some random checks)
        assert type(inputs) is xarray.Dataset
        assert inputs.calliope_version == "0.6.10"
        self.inputs = inputs

    def get_locations(self) -> list[str]:
        """
        Return all locations in the model.

        Returns
        -------
        list of str
            A list of location names (strings) present in `model.inputs.locs`.
        """
        return list(self.inputs.locs.values)

    def get_loc_coords(self) -> list[tuple[str, float, float]]:
        """
        Return all locations in the model with their names and lon/lat coordinates.

        The function assumes that only 2D space is used. If coordinate names include
        'lat' and 'lon', those are used to return (lon, lat) consistently. Otherwise,
        the raw coordinate order is used.

        Returns:
            list[tuple[str, float, float]]: A list of tuples, each containing
            the location name (str), the longitude (float), and the latitude (float).

        Example:
        helper.get_loc_coords()
        [('N1', 5, 7), ('X3', 5, 3), ('X1', 2, 7), ('X2', 8, 7)]
        """

        assert len(self.inputs.coordinates) == 2  # The function works correctly iff only 2D space is used

        loc_names = self.get_locations()

        coords = self.inputs.loc_coordinates.data
        coord_names = [str(x) for x in self.inputs.coordinates.values]
        if "lat" in coord_names and "lon" in coord_names:
            lat_idx = coord_names.index("lat")
            lon_idx = coord_names.index("lon")
        else:
            lon_idx, lat_idx = 0, 1

        coords_lon = coords[lon_idx]
        coords_lat = coords[lat_idx]

        return list(zip(loc_names, coords_lon, coords_lat))

    def get_loc_coords_as_dict(self) -> dict[str, tuple[int, int]]:
        # ToDo: write docstring
        coords = self.get_loc_coords()
        loc_coords_as_dict = {x[0]: (x[1], x[2]) for x in coords}
        return loc_coords_as_dict

    def get_location_techs(self, location: str, carrier_filter: str = None) -> list[tuple[str, str, str]]:
        """
        Return technologies located in a specific location.

        Args:
            location (str): The location name to query.
            carrier_filter (str, optional): If provided, restrict results to technologies
                associated with this carrier (for example, 'electricity' or 'heat').
                Defaults to None (no carrier filtering).

        Returns:
            list[tuple[str, str, str]]: A list of (location, technology, carrier) tuples.

        Raises:
            ValueError: If `carrier_filter` is provided but the pair (location, carrier_filter)
                is not present in `self.inputs.loc_carriers.data` (this bubbles up from
                `list.index()`).
        """

        loc_carriers = [(i.split('::')[0], i.split('::')[1]) for i in self.inputs.loc_carriers.data]

        loc_tech_carrier = list(self.inputs.lookup_loc_carriers.data)

        # if exact carrier is specified
        if carrier_filter is not None:

            idx = loc_carriers.index((location, carrier_filter))

            target_loc_tech_carrier = loc_tech_carrier[idx].split(',')

            return [tuple(i for i in j.split('::')) for j in target_loc_tech_carrier]

        else:
            target_loc_tech_carrier = []
            for i, (loc, carrier) in enumerate(loc_carriers):
                if loc == location:
                    target_loc_tech_carrier += loc_tech_carrier[i].split(',')

            return [tuple(i for i in j.split('::')) for j in target_loc_tech_carrier]

    def get_location_carriers(self, location: str) -> list[str]:
        """
        Return a sorted list of unique carriers associated with a given location.

        Parameters
        ----------
        location : str
            The name or identifier of the location for which to retrieve
            the associated carriers.

        Returns
        -------
        list[str]
            A sorted list of unique carrier names (strings) associated with
            technologies present at the specified location.

        Raises
        ------
        AssertionError
            If the provided location does not exist in `self.inputs.locs.data`.

        """

        loc_techs = self.get_location_techs(location)
        return list(sorted(list(set([x[2] for x in loc_techs]))))

    def get_location_area(self, location: str) -> float:
        """
        Return the total available area for a given location.

        This function looks up the index of the provided location in
        `self.inputs.locs.data` and returns the corresponding value from
        `self.inputs.available_area.data`.

        Parameters
        ----------
        location : str
            The name of the location to look up.

        Returns
        -------
        float
            The total available area corresponding to the given location.

        Raises
        ------
        AssertionError
            If the provided location does not exist in `self.inputs.locs.data`.
        """
        # Locate the indices where the location matches
        matches = np.where(self.inputs.locs.data == location)[0]

        # Assert that the location exists
        assert matches.size > 0, f"Location '{location}' not found in locs.data"

        # Get the first matching index and return the corresponding area
        idx = matches[0]
        try:
            area = self.inputs.available_area.data[idx]
            return area
        except AttributeError:
            warnings.warn("No available area found for location '{}'".format(location))
            return np.nan

    def get_location_coordinates(self, location: str) -> tuple[float, float]:
        """
        Return the (lon, lat) coordinates of the specified location.

        Parameters
        ----------
        location : str
            The name or identifier of the location to look up.

        Returns
        -------
        tuple[int, int]
            A tuple containing the (lon, lat) coordinates of the location.

        Raises
        ------
        AssertionError
            If the provided location does not exist.
        """

        # Locate the indices where the location matches
        matches = np.where(self.inputs.locs.data == location)[0]

        # Assert that the location exists
        assert matches.size > 0, f"Location '{location}' not found in locs.data"

        coord_names = [str(x) for x in self.inputs.coordinates.values]
        if "lat" in coord_names and "lon" in coord_names:
            lat_idx = coord_names.index("lat")
            lon_idx = coord_names.index("lon")
        else:
            lon_idx, lat_idx = 0, 1

        lon = self.inputs.loc_coordinates.data[lon_idx][matches[0]]
        lat = self.inputs.loc_coordinates.data[lat_idx][matches[0]]

        return lon, lat

    def get_location_demand(self, location: str, carrier: str) -> list[np.ndarray]:
        """
        Return the demand timeseries for a specific carrier at the given location.

        This function looks up all demand technologies associated with the given
        `location` and `carrier`. Because a location can have multiple demand
        technologies for the same carrier (e.g., multiple demand sectors or
        disaggregated loads), the function returns a list of NumPy arrays,
        each representing a demand timeseries. If no demand technologies exist
        for the given `(location, carrier)`, the function returns an empty list.
        This function excludes non-demand technologies (e.g. PV) from the results.

        Parameters
        ----------
        location : str
            The name or identifier of the location to look up.
        carrier : str
            The name of the energy carrier (e.g., "electricity", "heat") whose
            demand timeseries should be retrieved.

        Returns
        -------
        list[np.ndarray]
            A list of demand timeseries (as NumPy arrays). Each array corresponds
            to a demand technology at the given location for the specified carrier.
            If multiple demand technologies exist, multiple arrays are returned.

        Raises
        ------
        AssertionError
            If the provided location does not exist in `self.inputs.locs.data`.
        """

        # Locate the indices where the location matches
        matches = np.where(self.inputs.locs.data == location)[0]

        # Assert that the location exists
        assert matches.size > 0, f"Location '{location}' not found in locs.data"

        # ToDo: add assert about carrier name

        ltc_list = self.get_location_techs(location, carrier)  # [(loc, tech, carr),]

        # Exclude non-demand techs from the list
        target_loc_tech = list(filter(
            lambda x: self.inputs.inheritance.data[list(self.inputs.techs.data).index(x[1].split(':')[0])] == 'demand',
            ltc_list))

        # Transform selection into strings
        target_loc_tech = [f"{i[0]}::{i[1]}" for i in target_loc_tech]

        target_indexes = list(filter(lambda i: self.inputs.loc_techs_finite_resource.data[i] in target_loc_tech,
                                     range(len(self.inputs.loc_techs_finite_resource.data))))

        # Extract timeseries
        return [self.inputs.resource.data[i] for i in target_indexes]

    def get_location_total_max_supply(self, location: str, carrier: str) -> dict[str, np.ndarray]:
        """
        Return the total potential supply timeseries for a given carrier at a specific location.
        Convertion techs are not included in this function.

        This function collects all supply technologies at the specified `location` that produce
        the given `carrier`, and returns a dictionary mapping each technology to its potential
        timeseries. It separates technologies into:

        1. **Finite-resource supply technologies**: These have a resource limit (e.g., PV, wind,
           or other technologies constrained by timeseries data). Their timeseries is taken
           directly from `self.inputs.resource`.

        2. **Infinite-resource supply technologies**: These are not constrained by a resource
           timeseries (e.g., gas supply). For these, the timeseries is filled with the
           maximum capacity of the technology (`self.inputs.energy_cap_max`) for every timestep.

        Parameters
        ----------
        location : str
            The location name for which to retrieve supply timeseries.
        carrier : str
            The energy carrier (e.g., 'electricity', 'heat') whose supply should be retrieved.

        Returns
        -------
        dict[str, np.ndarray]
            A dictionary where keys are the supply technology identifiers in the form
            `"location::tech_name"`, and values are NumPy arrays of the same length representing
            the timeseries of potential max supply for each technology.

        Notes
        -----
        - This function does **not** account for energy received through transmission or
          conversion technologies. The returned timeseries represent the potential supply
          **at the location itself**.
        - Infinite-resource technologies are represented with a constant array equal to
          their `energy_cap_max` across all timesteps.
        - Raises an AssertionError if the `location` does not exist in `self.inputs.locs.data`.
        """

        # Locate the indices where the location matches
        matches = np.where(self.inputs.locs.data == location)[0]

        # Assert that the location exists
        assert matches.size > 0, f"Location '{location}' not found in locs.data"

        # ToDo: add assert about carrier name

        ltc_list = self.get_location_techs(location, carrier)  # [(loc, tech, carr),]

        # Exclude non-supply techs from the list
        target_loc_tech = list(filter(
            lambda x: self.inputs.inheritance.data[list(self.inputs.techs.data).index(x[1].split(':')[0])].split('.')[
                          -1] in ("supply", "supply_plus"),
            ltc_list))

        # find the target indexes for the inputs.resource array
        finite_resource_lt_strings = [f"{i[0]}::{i[1]}" for i in target_loc_tech]
        target_indexes = list(
            filter(lambda i: self.inputs.loc_techs_finite_resource.data[i] in finite_resource_lt_strings,
                   range(len(self.inputs.loc_techs_finite_resource.data))))

        finite_resource_timeseries = {self.inputs.loc_techs_finite_resource.data[i]: self.inputs.resource.data[i] for i
                                      in target_indexes}

        n_timesteps = len(self.inputs.timesteps)

        # find out which of supply techs do not depend on timeseries
        infinite_resource_ltc = list(
            filter(lambda x: f"{x[0]}::{x[1]}" not in self.inputs.loc_techs_finite_resource.data, target_loc_tech))

        infinite_resource_timeseries = {f"{x[0]}::{x[1]}": np.full(n_timesteps, self.inputs.energy_cap_max.data[
            list(self.inputs.loc_techs.data).index(f"{x[0]}::{x[1]}")]) for x in infinite_resource_ltc}

        return finite_resource_timeseries | infinite_resource_timeseries

    def tech_is_storage(self, tech_name: str) -> bool:
        return \
                list(self.inputs.inheritance.data)[list(self.inputs.techs.data).index(tech_name.split(':')[0])].split(
                    '.')[
                    -1] == "storage"

    def get_loc_tech_carrier_stats(self, location, tech, carrier):
        # Extract the parent(type) of the current tech
        tech_type = self.inputs.inheritance.data[list(self.inputs.techs.data).index(tech)].split('.')[-1]

        details = {}

        if tech_type == "supply_plus":
            loc_tech_search_str = f"{location}::{tech}"
            loc_tech_index = list(self.inputs.loc_techs.data).index(loc_tech_search_str)

            # energy_cap_max
            details["energy_cap_max"] = self.inputs.energy_cap_max.data[loc_tech_index]

            # energy_con
            details["energy_con"] = self.inputs.energy_con.data[loc_tech_index]

            # energy_eff
            details["energy_eff"] = self.inputs.energy_eff.data[loc_tech_index]

            # parasitic_eff
            loc_techs_supply_plus_search_str = loc_tech_search_str  # apparently those are the same
            if loc_tech_search_str in list(self.inputs.loc_techs_supply_plus.data):
                loc_techs_supply_plus_index = list(self.inputs.loc_techs_supply_plus.data).index(
                    loc_techs_supply_plus_search_str)
                details["parasitic_eff"] = self.inputs.parasitic_eff.data[loc_techs_supply_plus_index]

            # resource_area_max
            resource_area_max_search_str = loc_tech_search_str  # apparently those are the same
            if resource_area_max_search_str in list(self.inputs.loc_techs_area.data):
                resource_area_max_index = list(self.inputs.loc_techs_area.data).index(resource_area_max_search_str)
                details["resource_area_max"] = self.inputs.resource_area_max.data[resource_area_max_index]

            # resource_eff
            resource_eff_search_str = loc_tech_search_str
            if resource_eff_search_str in list(self.inputs.resource_eff.data):
                resource_eff_index = list(self.inputs.resource_eff.data).index(resource_eff_search_str)
                details["resource_eff"] = self.inputs.resource_eff.data[resource_eff_index]

            # lifetime
            details["lifetime"] = self.inputs.lifetime.data[loc_tech_index]


        elif tech_type == "supply":
            raise NotImplementedError

        elif tech_type == "storage":
            loc_tech_search_str = f"{location}::{tech}"
            loc_tech_index = list(self.inputs.loc_techs.data).index(loc_tech_search_str)

            # energy_cap_max
            details["energy_cap_max"] = self.inputs.energy_cap_max.data[loc_tech_index]

            # storage_cap_max
            loc_techs_store_search_str = loc_tech_search_str
            if loc_techs_store_search_str in list(self.inputs.loc_techs_store.data):
                loc_techs_store_index = list(self.inputs.loc_techs_store.data).index(loc_techs_store_search_str)
                details["storage_cap_max"] = self.inputs.storage_cap_max.data[loc_techs_store_index]

            # energy_con
            details["energy_con"] = self.inputs.energy_con.data[loc_tech_index]

            # energy_eff
            details["energy_eff"] = self.inputs.energy_eff.data[loc_tech_index]

            # resource_eff
            resource_eff_search_str = loc_tech_search_str
            if resource_eff_search_str in list(self.inputs.resource_eff.data):
                resource_eff_index = list(self.inputs.resource_eff.data).index(resource_eff_search_str)
                details["resource_eff"] = self.inputs.resource_eff.data[resource_eff_index]

            # lifetime
            details["lifetime"] = self.inputs.lifetime.data[loc_tech_index]

            # resource_area_max
            resource_area_max_search_str = loc_tech_search_str  # apparently those are the same
            if resource_area_max_search_str in list(self.inputs.loc_techs_area.data):
                resource_area_max_index = list(self.inputs.loc_techs_area.data).index(resource_area_max_search_str)
                details["resource_area_max"] = self.inputs.resource_area_max.data[resource_area_max_index]



        elif tech_type == "transmission":
            raise NotImplementedError

        elif tech_type == "conversion":
            raise NotImplementedError

        else:
            raise NotImplementedError
        return details

    def get_transmission_lines(self) -> list[
        tuple[
            tuple[str, float, float],
            tuple[str, float, float]
        ]
    ]:

        candidates = list(self.inputs.loc_techs_transmission.data)

        # After that we have to filter out those which are not able to transmiss because of one_way=True
        try:
            for i, tech in enumerate(self.inputs.loc_techs.data):
                one_way = True if self.inputs.one_way.data[i] == 1 else False
                if one_way:
                    if int(self.inputs.energy_prod.data[
                               i]) == 1:  # It means that the energy does not flow in this direction
                        # Delete this tech from the candidate list
                        del candidates[candidates.index(tech)]
        except AttributeError:
            warnings.warn("No one way transmissions found; assuming all transmission lines are bidirectional")

        # can_to_return = set(candidates)
        # del_can = set(self.inputs.loc_techs_transmission.data).difference(can_to_return)
        # print("deleted:", del_can)
        res = [(
            transmission.split("::")[0],
            transmission.split("::")[1].split(":")[1],
        ) for transmission in candidates]  # [(from, to), ..]

        coords_dict = self.get_loc_coords_as_dict()

        res = [((x[0], coords_dict[x[0]][0], coords_dict[x[0]][1]), (x[1], coords_dict[x[1]][0], coords_dict[x[1]][1]))
               for x in res]
        return res

    def get_loc_tech_costs(self, location: str, tech: str) -> dict[str, float]:
        """
        Return cost parameters for a given location and technology.

        Returns a dict with keys:
            cost_energy_cap, cost_depreciation_rate, cost_energy_cap_per_distance, cost_om_con
        Missing values are returned as NaN.
        """
        loc_tech_key = f"{location}::{tech}"
        res = {
            "cost_energy_cap": np.nan,
            "cost_depreciation_rate": np.nan,
            "cost_energy_cap_per_distance": np.nan,
            "cost_om_con": np.nan,
        }

        try:
            inv_keys = list(self.inputs.loc_techs_investment_cost.data)
            if loc_tech_key in inv_keys:
                idx = inv_keys.index(loc_tech_key)
                res["cost_energy_cap"] = self.inputs.cost_energy_cap.data[0][idx]
                res["cost_depreciation_rate"] = self.inputs.cost_depreciation_rate.data[0][idx]
                res["cost_energy_cap_per_distance"] = self.inputs.cost_energy_cap_per_distance.data[0][idx]
        except AttributeError:
            warnings.warn("Investment cost fields not found in inputs.")

        try:
            om_keys = list(self.inputs.loc_techs_om_cost.data)
            if loc_tech_key in om_keys:
                idx = om_keys.index(loc_tech_key)
                res["cost_om_con"] = self.inputs.cost_om_con.data[0][idx]
        except AttributeError:
            warnings.warn("OM cost fields not found in inputs.")

        return res

    def get_transmission_capacity(self, origin: str, destination: str) -> float:
        """
        Return transmission capacity (energy_cap_max) for a directed line.
        """
        line_id = f"{origin}::transmission_tech:{destination}"
        if "loc_techs" not in self.inputs.coords:
            return float("nan")
        try:
            idx = list(self.inputs.loc_techs.values).index(line_id)
        except ValueError:
            return float("nan")
        try:
            return float(self.inputs.energy_cap_max.values[idx])
        except Exception:
            return float("nan")

    def get_timesteps(self) -> list[str]:
        """
        Return all timesteps in the model.

        Returns
        -------
        list of str
            A list of timestep labels present in `model.inputs.timesteps`.
        """
        return list(self.inputs.timesteps.values)

    def get_timesteps_datetime(self) -> list:
        """
        Return timesteps as datetime-like values when possible.

        Falls back to the raw timesteps if parsing fails.
        """
        try:
            import pandas as pd
        except ImportError:
            return self.get_timesteps()

        ts = self.get_timesteps()
        parsed = pd.to_datetime(ts, errors="coerce")
        if parsed.isna().all():
            return ts
        return parsed

    def get_scenarios(self) -> list[str]:
        """
        Return all scenarios in the model.

        Returns
        -------
        list of str
            A list of scenario labels present in `model.inputs.scenarios`.
        """
        return list(self.inputs.scenarios.values)

# import pickle
#
# # Specify the path to the pickle file
# pickle_file_path = 'german_model_inputs_with_transmissions.pkl'
#
# # Open the file in read-binary mode and load the inputs
# with open(pickle_file_path, 'rb') as f:
#     loaded_inputs = pickle.load(f)
#
# helper = InputsHelper(loaded_inputs)
# # print(loaded_inputs.loc_techs_transmission)
# res = helper.get_transmission_lines()
# print(type(res))
# print(sorted(res))
# print(len(res))
