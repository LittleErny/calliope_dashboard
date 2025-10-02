# inputs_helper.py
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
        # print(inputs.dims)
        # assert len(dict(inputs.dims).keys()) == 20  # the data should have exactly 20 dimensions
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

    def get_loc_coords(self) -> list[tuple[str, int, int]]:
        """
        Return all locations in the model with their names and 2D coordinates.

        The function assumes that only 2D space is used (x and y coordinates).

        Returns:
            list[tuple[str, int, int]]: A list of tuples, each containing
            the location name (str), the x-coordinate (int), and the y-coordinate (int).

        Example:
        helper.get_loc_coords()
        [('N1', 5, 7), ('X3', 5, 3), ('X1', 2, 7), ('X2', 8, 7)]
        """

        assert len(self.inputs.coordinates) == 2  # The function works correctly iff only 2D space is used

        loc_names = self.get_locations()

        coords = self.inputs.loc_coordinates.data

        coords_x = coords[0]
        coords_y = coords[1]

        return list(zip(loc_names, coords_x, coords_y))

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
        area = self.inputs.available_area.data[idx]

        return area

    def get_location_coordinates(self, location: str) -> tuple[int, int]:
        """
        Return the (x, y) coordinates of the specified location.

        Parameters
        ----------
        location : str
            The name or identifier of the location to look up.

        Returns
        -------
        tuple[int, int]
            A tuple containing the (x, y) coordinates of the location.

        Raises
        ------
        AssertionError
            If the provided location does not exist.
        """

        # Locate the indices where the location matches
        matches = np.where(self.inputs.locs.data == location)[0]

        # Assert that the location exists
        assert matches.size > 0, f"Location '{location}' not found in locs.data"

        x, y = self.inputs.loc_coordinates.data[0][matches[0]], self.inputs.loc_coordinates.data[1][matches[0]]

        return x, y

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

        n_timesteps = len(loaded_inputs.timesteps)

        # find out which of supply techs do not depend on timeseries
        infinite_resource_ltc = list(
            filter(lambda x: f"{x[0]}::{x[1]}" not in self.inputs.loc_techs_finite_resource.data, target_loc_tech))

        infinite_resource_timeseries = {f"{x[0]}::{x[1]}": np.full(n_timesteps, self.inputs.energy_cap_max.data[
            list(self.inputs.loc_techs.data).index(f"{x[0]}::{x[1]}")]) for x in infinite_resource_ltc}

        return finite_resource_timeseries | infinite_resource_timeseries


# import pickle
#
# # Specify the path to the pickle file
# pickle_file_path = 'model_inputs.pkl'
#
# # Open the file in read-binary mode and load the inputs
# with open(pickle_file_path, 'rb') as f:
#     loaded_inputs = pickle.load(f)
#
# helper = InputsHelper(loaded_inputs)
#
# res = helper.get_location_total_max_supply(location='X1', carrier='electricity')
# print(type(res))
# print(res)
