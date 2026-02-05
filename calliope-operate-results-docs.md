## Model.results (operate mode)

This document describes the structure of `Model.results` **for Calliope operate mode** as produced in this project.
The results are stored as an **xarray.Dataset** with named dimensions, coordinates, data variables, and attributes.
The exact contents below match the current `german_model_results_operate.pkl` output.


### Dimensions

The dataset uses label-based coordinates. In operate mode there is **no separate `locs` dimension**; locations are encoded in labels like `loc::tech` and `loc::tech::carrier`.

- `carriers` — list of energy carriers in the model (in this dataset: only `electricity`).
- `costs` — cost classes (e.g., `monetary`, `co2`).
- `loc_carriers` — all `location::carrier` pairs present in the system.
- `loc_carriers_system_balance_constraint` — subset of `loc_carriers` where the system balance constraint is enforced.
- `loc_tech_carriers_con` — all `location::tech::carrier` combinations that **consume** carrier.
- `loc_tech_carriers_export` — all `location::tech::carrier` combinations that can **export** carrier outside the system.
- `loc_tech_carriers_prod` — all `location::tech::carrier` combinations that **produce** carrier (including transmission output).
- `loc_techs` — all `location::tech` combinations in the model (all techs at all locations).
- `loc_techs_area` — subset of `loc_techs` whose output depends on area constraints.
- `loc_techs_balance_demand_constraint` — subset of `loc_techs` that represent **demand** technologies; used for demand balance constraints.
- `loc_techs_cost` — subset of `loc_techs` that participate in total cost accounting.
- `loc_techs_om_cost` — subset of `loc_techs` that incur variable O&M costs per timestep.
- `loc_techs_store` — subset of `loc_techs` that are **storage** technologies.
- `loc_techs_supply_plus` — subset of `loc_techs` that are **supply_plus** technologies.
- `techs` — unique technology IDs (base tech names without location).
- `timesteps` — the operate-mode time window (here: 336 hourly timesteps for 2 weeks).


### Data Variables

Exactly the arrays with described dimensions from above. All variables below are from the operate results output.

**Current Mode: Operate**

- `carrier_prod` (`loc_tech_carriers_prod`, `timesteps`) — actual carrier production per tech and timestep.
- `carrier_con` (`loc_tech_carriers_con`, `timesteps`) — actual carrier consumption per tech and timestep.
- `carrier_export` (`loc_tech_carriers_export`, `timesteps`) — exported carrier outside the system per tech and timestep.
- `required_resource` (`loc_techs_balance_demand_constraint`, `timesteps`) — **demand** requirement per demand tech and timestep. In this dataset, values are negative (consumption); use absolute value for total demand.
- `unmet_demand` (`loc_carriers`, `timesteps`) — unmet demand per location and carrier per timestep.
- `system_balance` (`loc_carriers_system_balance_constraint`, `timesteps`) — system balance residual per location and carrier per timestep.

- `storage` (`loc_techs_store`, `timesteps`) — storage state (energy stored) per storage tech and timestep.
- `storage_cap` (`loc_techs_store`) — storage capacity (kWh) for each storage tech.
- `energy_cap_per_storage_cap` (`loc_techs_store`) — fixed ratio of energy cap per storage cap (hour-based).

- `resource_con` (`loc_techs_supply_plus`, `timesteps`) — resource consumption of supply_plus techs per timestep.
- `resource_cap` (`loc_techs_supply_plus`) — installed resource consumption capacity for supply_plus techs.
- `resource_area` (`loc_techs_area`) — resource area required for area-constrained techs.

- `energy_cap` (`loc_techs`) — installed energy capacity of each loc::tech. In operate mode this is typically fixed via `energy_cap_equals` in config.

- `capacity_factor` (`timesteps`, `loc_tech_carriers_prod`) — operating load per producing tech per timestep (0–1).
- `systemwide_capacity_factor` (`carriers`, `techs`) — capacity factor aggregated systemwide by tech and carrier.

- `cost` (`timesteps`, `costs`, `loc_techs_cost`) — total cost per tech per timestep and cost class (operate mode includes time dimension).
- `cost_var` (`costs`, `loc_techs_om_cost`, `timesteps`) — variable O&M costs per tech per timestep.
- `cost_var_rhs` (`costs`, `loc_techs_om_cost`, `timesteps`) — RHS form of variable costs (often similar to `cost_var`).
- `systemwide_levelised_cost` (`carriers`, `costs`, `techs`, `timesteps`) — levelised cost per tech/carrier and timestep.
- `total_levelised_cost` (`carriers`, `costs`, `timesteps`) — total system levelised cost per carrier per timestep.


### Attributes

Mostly additional information without dimensions.

- `termination_condition` — solver termination status.
- `solution_time` — total solve time in seconds.
- `time_finished` — timestamp when solve finished.
- `calliope_version` — Calliope version string.
- `applied_overrides` — applied scenario overrides (if any).
- `scenario` — scenario name (if any).
- `defaults` — flattened defaults snapshot (config).
- `allow_operate_mode` — flag indicating operate mode was allowed.
- `model_config` — serialized model configuration used for the run.
- `run_config` — serialized run configuration (includes operate window/horizon).


---

## What might be interesting to visualize (operate)

- Total production vs total demand vs unmet demand over time.
- Stacked production by technology for the operating window.
- Storage state-of-charge (absolute and normalized by `storage_cap`).
- Capacity factor distributions by tech.
- Net system balance per location (sum of `system_balance`).
- Variable cost time series and cumulative cost per tech.
- Export flows (if any) per tech and time.

