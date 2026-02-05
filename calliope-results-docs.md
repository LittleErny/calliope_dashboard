## Model.results




### Dimensions

The data in inputs is represented in the form of **xarray.Dataset** - some kind of dict with a lot of multi-dimensional arrays inside. The arrays must follow some coordinate system, described when creating the Dataset using `coords` parameter.

So, for `Model.results`, the names of Dimensions and their Coordinates are:

- `carriers` - list of possible energy carriers. For example, it can be *electricity*, *gas*, *heat*.
- `costs` - each technology has some costs, most often those are *monetary*(how much $ it costs) or *environmental*(can be represented in the amount of emissions of co2). Generally means something bad, something, that our model will try to minimize.
- `loc_carriers` - list of combinations of all possible "`location_name`::`carrier`" such that the exact `carrier` is present in exactly this `location_name`.
- `loc_carriers_system_balance_constraint` - list of `location_name`::`carrier`, representing all location-carrier combinations where the energy balance(supply + import - demand - export) has to be <= 0.
- `loc_tech_carriers_con` - list of all combinations of `location_name`::`tech_name`::`carrier` such that consume some energy.
- `loc_tech_carriers_export` - list of all combinations of `location_name`::`tech_name`::`carrier` such that are able to export energy out of the system
- `loc_tech_carriers_prod` - list of all combinations of `location_name`::`tech_name`::`carrier` such that have some energy production or transmit energy from other locations.
- `loc_techs` - a list of combinations of "`location_name`::`tech`" such that this exact `tech` is present in that exact `location_name`.
- `loc_techs_area` - a subset of `loc_techs` such that technologies in this list are somehow affected or restricted by area (for example, PV tech is usually restricted by available area for them).
- `loc_techs_balance_demand_constraint` - a subset of `loc_techs` such that all the techs are demand techs. 
- `loc_techs_cost` - a subset of `loc_techs` such that all techs in it require some capital or O&M costs.
- `loc_techs_cost_investment_constraint` - ToDo
- `loc_techs_investment_cost` - ToDo
- `loc_techs_om_cost` - a subset of `loc_techs` such that all the techs require some Operation & Maintenance costs.
- `loc_techs_store` - a subset of `loc_techs` such that all the techs' parent is **storage**.
- `loc_techs_supply_plus` - a subset of `loc_techs` such that all the techs' parent is **supply_plus**.
- `techs` - an array of all technologies.
- `timesteps` - an array of all timesteps.


### Data Variables:

Exactly the arrays with described dimensions from above. So, for example, data variable `available_area ('locs',)` means that there is an array `available_area` with one just dimension `'locs'`, and basically represents the amount of available area in every location. So, if one wants to find out the amount of available area in location "X2", one must first check the index of this location at `model.inputs.locs`, and then extract the value from the `available_area` array using this index.

 **Current Mode: Planning**

- `capacity_factor` ('loc_tech_carriers_prod', 'timesteps') - to each tech somehow supplying energy to some location for each timestep a number $\in [0, 1]$ representing the tech load is assigned. $0$ means minimal load, while $1$ represents maximal. **Definitely something to visualize!**
- `carrier_con` ('loc_tech_carriers_con', 'timesteps') - to each tech somehow demanding energy tech at some location for each timestep the amount of consumed energy is assigned. 
- `carrier_export` ('loc_tech_carriers_export', 'timesteps') - to each tech that are allowed to export energy outside the system the amount of exported energy for each timestep is assigned. 
- `carrier_prod` ('loc_tech_carriers_prod', 'timesteps') - to each tech that can produce energy the amount of actual produced energy is assigned for each timestep.
- `cost` ('costs', 'loc_techs_cost') - total costs for each loc_tech (including initial investment costs + O&M costs). Exactly this metric is minimized in the backend when running the model. 
- `cost_investment` ('costs', 'loc_techs_investment_cost') - investment costs for each loc_tech.
- `cost_investment_rhs` ('costs', 'loc_techs_cost_investment_constraint') - investment costs for each loc_tech; somehow very similar to `cost_investment`.
- `cost_var` ('costs', 'loc_techs_om_cost', 'timesteps') - OM costs for each loc_tech.
- `cost_var_rhs` ('costs', 'loc_techs_om_cost', 'timesteps') - OM costs for each loc_tech; somehow very similar to `cost_var`.
- `energy_cap` ('loc_techs') - the list of necessary energy capacities for each loc_tech after optimization.
- `required_resource` ('loc_techs_balance_demand_constraint', 'timesteps') - shows how much energy each demand tech requires at each timestep.
- `resource_area` ('loc_techs_area') - the amount of resource area actually needed for techs requiring some area to operate.
- `resource_cap` ('loc_techs_supply_plus') - 
- `resource_con` ('loc_techs_supply_plus', 'timesteps') -
- `storage` ('loc_techs_store', 'timesteps') - the amount of energy stored at each storage tech at each timestep.
- `storage_cap` ('loc_techs_store') - optimized minimal amount of storage per each storage tech needed for the model.
- `system_balance` ('loc_carriers_system_balance_constraint', 'timesteps') -
- `systemwide_capacity_factor` ('techs', 'carriers') -
- `systemwide_levelised_cost` ('techs', 'costs', 'carriers') -
- `total_levelised_cost` ('costs', 'carriers') -
- `unmet_demand` ('loc_carriers', 'timesteps') - after the model is optimized, all the unmet demand at each location can be found there. 



### Attributes:

Mostly those describe some additional information about Dataset, without any dimensions. Mostly not important for visualisations.

- allow_operate_mode - (?)
- applied_overrides - 
- calliope_version
- defaults
- scenario



--- 

## What might be interesting to visualize:


