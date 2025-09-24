## Model.inputs

There are generally 2 ways of parsing the input data. One way is obviously parsing of initial `.yaml` files and writing all the logic ourselves. While it seems easy at first, it requires full understanding of inner-mechanisms of Calliope, cause a lot of variables in the `.yaml` files often overwrite each other. This is why I decided to have a look into the 2nd approach - looking directly into `Model.inputs`. This is the data retrieved from the same `.yaml` files, but already preprocessed and ready to be used in the simulation.

While one can easily find the documentation for different fields of `.yaml` files, there is almost no easy-readable information on the fields in `Model.inputs`. This is why I will write a small documentation for the most crucial variables, so that one could directly use those, without need to parse `.yaml` files.


### Dimensions

The data in inputs is represented in the form of **xarray.Dataset** - some kind of dict with a lot of multi-dimensional arrays inside. The arrays must follow some coordinate system, described when creating the Dataset using `coords` parameter.

So, for `Model.inputs`, the names of Dimensions and their Coordinates are:

- carrier_tiers - convertion techs can have multiple inputs and outputs, which names are specified in the `carrier_tiers` coordinates.
- `carriers` - list of possible energy carriers. For example, it can be *electricity*, *gas*, *heat*.
- `costs` - each technology has some costs, most often those are *monetary*(how much $ it costs) or *environmental*(can be represented in the amount of emissions of co2). Generally means something bad, something, that our model will try to minimize.
- `coordinates` - list of names of dimensions on the map (when specifying locations). TBC
- `loc_carriers` - list of combinations of all possible "`location_name`::`carrier`" such that the exact `carrier` is present in exactly this `location_name`.
- `loc_tech_carriers_conversion_plus` - list of combinations of "`location_name`::`conv_plus_tech_name`::`carrier`" such that there is a `conv_plus_tech_name` located at `location_name` and somehow processes `carrier`.
- `loc_techs` - a list of combinations of "`location_name`::`tech`" such that this exact `tech` is present in that exact `location_name`.
- `loc_techs_area` - a subset of `loc_techs` such that technologies in this list are somehow affected or restricted by area (for example, PV tech is usually restricted by available area for them).
- `loc_techs_conversion` - a subset of `loc_techs` such that technologies in this list are of `conversion` type (excluding `conversion_plus`).
- `loc_techs_conversion_plus` - a subset of `loc_techs` such that technologies in this list are of `conversion_plus` type.
- `loc_techs_export` - a subset of `loc_techs` such that technologies in this list are allowed to export some carriers outside the system. This can be defined using the `export_carrier` property of tech in `techs.yaml` If some tech is not included in this list it still means it is able to share the carrier with other locations as long as there is appropriate transmission infrastructure; the only restriction is to export carrier outside the system(for example, in the national grid).
- `loc_techs_finite_resource` - a subset of `loc_techs` such that the technologies there have finite resource constraints. This usually includes all the demands in the system and supply technologies that are somehow restricted in the amount of producing carrier. **ToBeChecked - something else might be also included!**
- `loc_techs_investment_cost` - a subset of `loc_techs` such that technologies in this list require some kind of investment before the tech can be used. This category includes only "buying the equipment" cost, but not operational. This cost does not depend on how much one uses this tech later.
- `loc_techs_non_conversion` - a subset of `loc_techs` such that technologies in this list do not convert one type of carrier into another.
- `loc_techs_om_cost` - a subset of `loc_techs` such that technologies in this list require some kind of investment during usage. This can be, for example, price one needs to pay per unit of carriage.
- `loc_techs_supply_plus` - a subset of `loc_techs` such that technologies in this list are of `supply_plus` type.
- `loc_techs_transmission` - a subset of `loc_techs` such that technologies in this list are of `transmission` type. The transmission is in the format "source_location_name::transmission_tech_name:destination_location_name".
- `locs` - an array of all locations.
- `techs` - an array of all technologies.
- `timesteps` - an array of all timesteps.

### Data Variables:

Exactly the arrays with described dimensions from above. So, for example, data variable `available_area ('locs',)` means that there is an array `available_area` with one just dimension `'locs'`, and basically represents the amount of available area in every location. So, if one wants to find out the amount of available area in location "X2", one must first check the index of this location at `model.inputs.locs`, and then extract the value from the `available_area` array using this index.


- `available_area` ('locs',) - array of available area in every location. It is specified in the `locations.yaml`.
- `carrier_ratios` ('carrier_tiers', 'loc_tech_carriers_conversion_plus') - **ToDo**
- `colors` ('techs',) - specifies the color for each location for each tech. It is specified in the `techs.yaml`.
- `cost_depreciation_rate` ('costs', 'loc_techs_investment_cost') - in order to compare the invest costs for each tech with varying lifetime and built costs, deprecation_rate for each tech is calculated. The idea behind is that instead of paying all built costs upfront one can borrow money from the bank with the specified interest rate for the period of tech lifetime; and when comparing the costs one can compare yearly payments to the bank that are calculated using deprecation_rate (`yearly_payment = upfront_pay * deprecation_rate`). So this 2D array contains deprecation rates for each technology for every type of costs(that can be in $, co2, etc.)
- `cost_energy_cap` ('costs', 'loc_techs_investment_cost') - the upfront investment costs for exact technology at exact location. 
- `cost_export` ('costs', 'loc_techs_om_cost', 'timesteps') - revenue that the system gets from some exact tech when exporting something outside in the certain moment of time. Not all techs in `loc_techs_om_cost` are actually allowed to export; for those, `nan` value is present. The data is imported from `export` fields in different techs or some locations. If no export specified, the tech in the current location is not allowed to export.
- `cost_om_annual` ('costs', 'loc_techs_investment_cost') - ToDo
- `cost_om_con` ('costs', 'loc_techs_om_cost') - ToDo
- `cost_om_prod` ('costs', 'loc_techs_om_cost') - ToDo
- `distance` ('loc_techs_transmission',) - the array of distances of all transmission technologies. The distances are either computed using coordinates or can be explicitly defined in the `locations.yaml`.
- `energy_cap_max` ('loc_techs',) - the array of all max capacities for each technology.
- `energy_con` ('loc_techs',) - energy consumption - boolean value of whether the technology at a specific location is allowed to consume energy. `1` means yes; `nan` - no.
- `energy_eff` ('loc_techs',) - energy efficiency - is a fraction and represent which % of energy is transferred further to carrier_out.
- `energy_prod` ('loc_techs',) - energy production - whether this technology is allowed to supply energy to carrier. `1` if yes, `nan` if no.
- `export_carrier` ('loc_techs_export',) - shows the names of carriers for each loc_tech that is allowed to export.
- `force_resource` ('loc_techs_finite_resource',) - each tech with finite resource(such as PV, which resource is limited by time-series data) has a flag representing whether this tech must consume all resource at once or not. If `False`, tech is allowed to take less resource than it's given.
- `inheritance` ('techs',) - shows from which base tech those techs are inherited. This is specified in `essentials.parent` field in `techs.yaml`.
- `lifetime` ('loc_techs',) - list of lifetimes of all techs.
- `loc_coordinates` ('coordinates', 'locs') - list of coordinates of all locations. 
- `lookup_loc_carriers` ('loc_carriers',) - for each location+carrier pair, the list of all related technologies is given. So, for example, for `X2::gas` the only 2 techs related to this carrier are `X1::supply_gas::gas,X1::chp::gas`.
- `lookup_loc_techs` ('loc_techs_non_conversion',) - for each tech that does not convert one type of carrier to another we specify the type of carrier that this tech uses. So, for example, for coordinate `X3::demand_heat` we would have value `X3::demand_heat::heat`.
- `lookup_loc_techs_area` ('locs',) - for each location we list values from `loc_techs` whose output depends on area they have.
- `lookup_loc_techs_conversion` ('carrier_tiers', 'loc_techs_conversion') - convertion techs can have multiple inputs and outputs, which names are specified in the `carrier_tiers` coordinates. And for each `loc_techs_conversion`, we specify the carrier name. For example, `X3::boiler::gas`. Some techs might have fewer inputs/outputs, so `None` is present in this case.
- `lookup_loc_techs_conversion_plus` ('carrier_tiers', 'loc_techs_conversion_plus') - similarly to `lookup_loc_techs_conversion`, for each `loc_techs_conversion`, we specify the carrier name. For example, `X3::boiler::gas`. Some techs might have fewer inputs/outputs, so `None` is present in this case.
- `lookup_loc_techs_export` ('loc_techs_export',) - for each tech that exports something outside the system, we specify which carrier exactly it exports.
- `lookup_primary_loc_tech_carriers_in` ('loc_techs_conversion_plus',) - for each `loc_techs_conversion_plus` we specify which carrier is the primary input.
- `lookup_primary_loc_tech_carriers_out` ('loc_techs_conversion_plus',) -for each `loc_techs_conversion_plus` we specify which carrier is the primary output.
- `lookup_remotes` ('loc_techs_transmission',) - for each transmission tech from loc1 -> loc2 we specify its opposite, loc2 -> loc1. So, for example, for `X2::heat_pipes:N1`, there is also `N1::heat_pipes:X2`, and vice versa.
- `max_demand_timesteps` ('carriers',) - for each carrier we specify the timestep when the carrier has max demand. (?)
- `names` ('techs',) - for each tech we specify its name.
- `parasitic_eff` ('loc_techs_supply_plus',) - for each `loc_techs_supply_plus` we specify its `parasitic_eff`.
- `resource` ('loc_techs_finite_resource', 'timesteps') - for each `loc_tech` with finite resource(such as demand or PV) we specify the exact resource values in each moment of time. 
- `resource_area_max` ('loc_techs_area',) - for each `loc_tech` the output of which depends on the area we specify max available area.
- `resource_area_per_energy_cap` ('loc_techs_area',) - for each `loc_tech` the output of which depends on the area we specify the exact amount of area that is required to get some energy_cap. Is specified either in the tech definition of can be overwritten in `locations.yaml`
- `resource_eff` ('loc_techs_finite_resource',) - for each `loc_tech` with finite resource(such as demand or PV) we specify its resource_eff - the fraction representing how much initial resource is converted to the new carrier. Usually is used for such techs as PV, wind turbines, dams, etc.
- `resource_unit` ('loc_techs_finite_resource',) - for each `loc_tech` with finite resource(such as demand or PV) we specify on what exactly its resource depends. It can be either just `energy` that is received from other techs or `energy_per_area`.
- `timestep_resolution` ('timesteps',) - amount of hours between each timestep.
- `timestep_weights` ('timesteps',) - it's common to make simulation basing not on the whole year data but just focus on some "representative" days that accumulate avg data from several days. The amount of those days is specified in this variable for each timestep.


### Attributes:

Mostly those describe some additional information about Dataset, without any dimensions. Mostly not important for visualisations.

- allow_operate_mode - (?)
- applied_overrides - 
- calliope_version
- defaults
- scenario



--- 

## What might be interesting to visualize:

Basing on the list of input fields and what might be interesting and not too complicated for user, I created a list of what visualisations I will try to create. 

- create a map with all locations
- some stats per location(when one clicks/points with cursor):
  - name of the location;
  - list of located techs there(dropdown menu?..), filter with carriers included(like show electricity or heat only) and/or their type(parent);
  - some small dashboard with key parameters about the whole location like area, total consumption/supply, .. (to think about it!);
  - demand stats - some kind of button to show the timeseries data with demand in the specified period, with possibility to see some general points about this timeseries data like avg per day/season/year;
  - PV resource timeseries data visualisation - how much sunlight and therefore how much electricity out of it it's possible to gain;
- when one select non-transition tech, one should be able to see:
  - tech name, type, color, capacity(min/max), lifetime, consumption(whether it needs energy itself), production(whether it produces energy), efficiency(fraction), parasitic_eff, whether it depends on some finite source or is potentially unlimited(and variables in `loc_techs_finite_resource` dimension)
- when **transmission** tech is selected, one should be able to see:
  - its carrier;
  - distance(+ info whether it's calculated as a straight line or was filled in manually)
  - max energy cap;
  - energy efficiency;
  - lifetime;
  - costs;
- when **supply** tech is selected, one should be able to see:
  - its carrier
  - whether it's finite or infinite
    - if finite: see the resource restriction(timeseries data/const) + other resource related variables
  - min/max capacity(how powerful it is)
  - costs(to be researched deeper)
- when **battery** tech is selected, one should be able to see:
  - energy_cap
  - storage_cap
  - energy_eff
  - energy_cap_per_storage_cap_max(?)
  - storage_loss
- ... and so on for every tech type ...



