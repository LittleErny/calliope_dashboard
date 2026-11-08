"""Compare every German-scale selection against independent NetCDF sums."""

import json

import numpy as np
import pytest
from plotly.utils import PlotlyJSONEncoder

from app import app_data as d
from app.app import app
from app.time_window import initial_time_window, time_marks
from helpers.results_helper import ALL_LOCATIONS

WINDOWS = [(0, 335), (0, 47), (168, 191), (335, 335)]


def _sum(array):
    return float(array.fillna(0).sum())


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
@pytest.mark.parametrize("carrier", ["electricity", "heat"])
@pytest.mark.parametrize("bounds", WINDOWS)
def test_planning_numbers_match_raw_results_for_every_selection(bounds, scenario, carrier):
    i0, i1 = bounds
    bundle = d.get_scenario(scenario, carrier)
    raw, inp, helper = bundle.LOADED_RESULTS, bundle.LOADED_INPUTS, bundle.RESULTS_HELPER
    categories = inp.base_tech
    output_techs = inp.techs.where(~categories.isin(["transmission", "demand"]), drop=True)
    all_selections = [("location", ALL_LOCATIONS, None, {})]
    all_selections += [("location", str(n), None, {"nodes": n}) for n in inp.nodes.values]
    all_selections += [
        ("technology", None, str(inp.name.sel(techs=t).item()), {"techs": t})
        for t in output_techs.values
    ]
    for mode, node, tech, selection in all_selections:
        selected_categories = categories.sel(techs=selection["techs"]) if "techs" in selection else categories
        selected = raw.sel(**selection)
        window = selected.isel(timesteps=slice(i0, i1 + 1))
        fraction = (i1 - i0 + 1) / raw.sizes["timesteps"]
        fixed = _sum(selected.cost_operation_fixed.sel(costs="monetary")) * fraction
        investment = _sum(selected.cost_investment_annualised.sel(costs="monetary")) * fraction
        variable = _sum(window.cost_operation_variable.sel(costs="monetary"))
        # Use the category mask directly, independently of dashboard tables.
        production = window.flow_out.where(~selected_categories.isin(["transmission", "demand"]), 0)
        expected = {
            "total_cost": investment + fixed + variable,
            "capex": _sum(selected.cost_investment.sel(costs="monetary")),
            "opex": fixed + variable,
            "co2_kg": _sum(window.cost_operation_variable.sel(costs="co2"))
            + _sum(selected.cost_investment_annualised.sel(costs="co2")) * fraction,
            "production": _sum(production),
            "capacity": _sum(selected.flow_cap.where(~selected_categories.isin(["transmission", "demand"]), 0)),
        }
        args = (scenario, carrier, d.TIME_INDEX[i0], d.TIME_INDEX[i1], mode, node, tech)
        actual = helper.get_plan_kpis(*args)
        assert actual == pytest.approx(expected), (bounds, mode, node, tech)
        assert helper.get_plan_production_timeseries(*args).energy_kwh.sum() == pytest.approx(expected["production"])
        assert helper.get_plan_co2_timeseries(scenario, d.TIME_INDEX[i0], d.TIME_INDEX[i1], mode, node, tech).co2_kg.sum() == pytest.approx(_sum(window.cost_operation_variable.sel(costs="co2")))
        table = helper.get_plan_detail_table(*args)
        totals = table.iloc[-1]
        for column, key in [("built_capacity_kw", "capacity"), ("capex_eur", "capex"), ("energy_kwh", "production"), ("co2_kg", "co2_kg")]:
            assert totals[column] == pytest.approx(expected[key])
        groups = helper.get_plan_cost_group(scenario, d.TIME_INDEX[i0], d.TIME_INDEX[i1], mode, node, tech)
        assert groups[["annualised_investment_eur", "fixed_opex_eur", "variable_opex_eur"]].sum().sum() == pytest.approx(expected["total_cost"])


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
@pytest.mark.parametrize("carrier", ["electricity", "heat"])
@pytest.mark.parametrize("bounds", WINDOWS)
def test_operate_numbers_and_storage_match_raw_results(bounds, scenario, carrier):
    start, end = bounds
    bundle = d.get_scenario(scenario, carrier)
    raw, inp, helper = bundle.LOADED_OPERATE_RESULTS, bundle.LOADED_OPERATE_INPUTS, bundle.OPERATE_HELPER
    for node in helper.get_locations():
        window = raw.sel(nodes=node).isel(timesteps=slice(start, end + 1))
        expected = {
            "total_demand": _sum(window.flow_in.where(inp.base_tech == "demand", 0)),
            "total_production": _sum(window.flow_out.where(~inp.base_tech.isin(["transmission", "demand"]), 0)),
            "total_unmet": _sum(window.unmet_demand),
            "total_variable_cost": _sum(window.cost_operation_variable.sel(costs="monetary")),
        }
        assert helper.get_location_operate_kpis_window(node, carrier, start, end) == pytest.approx(expected)
        if "storage" in raw.techs:
            np.testing.assert_allclose(helper.get_storage_soc_window(node, "storage", start, end), window.storage.sel(techs="storage").fillna(0))
    for line_id in helper.get_line_ids():
        line = helper._line_index[line_id]
        received = raw.flow_out.sel(nodes=line.dst, techs=line.tech, carriers=carrier).fillna(0)
        sent = raw.flow_in.sel(nodes=line.src, techs=line.tech, carriers=carrier).fillna(0)
        capacity = float(inp.flow_cap.sel(nodes=line.src, techs=line.tech))
        np.testing.assert_allclose(helper.get_line_flow_timeseries(line_id, carrier), received)
        np.testing.assert_allclose(helper.get_line_load_fraction_timeseries(line_id, carrier), sent / (capacity * inp.timestep_resolution))
        np.testing.assert_allclose(received, sent * 0.98, rtol=1e-6, atol=0.1)


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
@pytest.mark.parametrize("carrier", ["electricity", "heat"])
def test_input_supply_limits_and_demand_match_model_constraints(scenario, carrier):
    bundle = d.get_scenario(scenario, carrier)
    inp, helper = bundle.LOADED_INPUTS, bundle.INPUT_HELPER
    demand_tech = "demand" if carrier == "electricity" else "heat_demand"
    for node in helper.get_locations():
        actual = np.sum(helper.get_location_demand(node, carrier), axis=0)
        np.testing.assert_allclose(-actual, inp.sink_use_equals.sel(nodes=node, techs=demand_tech))
        for key, values in helper.get_location_total_max_supply(node, carrier).items():
            tech = key.split("::")[1]
            capacity = float(inp.flow_cap_max.sel(nodes=node, techs=tech))
            efficiency = float(inp.flow_out_parasitic_eff.sel(techs=tech))
            if not np.isfinite(efficiency):
                efficiency = 1.0
            resource = inp.source_use_max.sel(nodes=node, techs=tech).values
            if tech == "hydro":
                # Hydro is area-based and area_use == 10 * flow_cap.
                area = min(float(inp.area_use_max.sel(techs=tech)), float(inp.available_area.sel(nodes=node)))
                capacity = min(capacity, area / 10)
                expected = np.minimum(capacity, resource * min(area, capacity * 10)) * efficiency
            elif tech in {"pv", "wind", "solar_thermal"}:
                expected = np.minimum(capacity, resource * capacity) * efficiency
            else:
                expected = np.full(len(values), capacity)
            np.testing.assert_allclose(values, expected)


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
@pytest.mark.parametrize("carrier", ["electricity", "heat"])
def test_all_sections_build_for_every_city_and_line(scenario, carrier):
    callbacks = {config["callback"].__wrapped__.__name__: config["callback"].__wrapped__
                 for config in app.callback_map.values() if "callback" in config}
    bundle = d.get_scenario(scenario, carrier)
    for bounds in [(0, 335), (335, 335)]:
        for node in d.PLAN_LOCATIONS:
            json.dumps(callbacks["update_inputs_techs_list"](carrier, node, bounds, scenario), cls=PlotlyJSONEncoder)
            for norm in ("absolute", "per_kw"):
                json.dumps(callbacks["update_plan_dashboard"](scenario, carrier, bounds, "location", node, None, norm), cls=PlotlyJSONEncoder)
            json.dumps(callbacks["update_operate_info"]({"type": "location", "location": node}, carrier, bounds, scenario), cls=PlotlyJSONEncoder)
        for a, b in bundle.OPERATE_HELPER.get_physical_lines():
            json.dumps(callbacks["update_operate_info"]({"type": "line", "a": a, "b": b}, carrier, bounds, scenario), cls=PlotlyJSONEncoder)
        for tech in bundle.RESULTS_HELPER.get_technologies():
            json.dumps(callbacks["update_plan_dashboard"](scenario, carrier, bounds, "technology", None, tech, "absolute"), cls=PlotlyJSONEncoder)
        for mode in ("timestep", "critical"):
            json.dumps(callbacks["update_operate_map"](mode, 0, carrier, d.MAP_ZOOM_DEFAULT, bounds, scenario), cls=PlotlyJSONEncoder)


def test_time_control_has_sparse_dates_and_valid_initial_bounds():
    assert 1 <= len(time_marks(d.TIME_INDEX)) <= 4
    assert initial_time_window(336) == [0, 47]
    assert initial_time_window(1) == [0, 0]
    assert d.MAP_ZOOM_DEFAULT <= 6


def test_input_arrows_respect_one_way_links_and_assets_are_served():
    from app.callbacks.inputs import INPUT_ARROW_DIRECTIONS

    assert ("Hannover", "Hamburg") in INPUT_ARROW_DIRECTIONS
    assert ("Hamburg", "Hannover") not in INPUT_ARROW_DIRECTIONS
    assert ("Leipzig", "Hannover") in INPUT_ARROW_DIRECTIONS
    assert ("Hannover", "Leipzig") not in INPUT_ARROW_DIRECTIONS
    assert ("Berlin", "Hannover") in INPUT_ARROW_DIRECTIONS
    assert ("Hannover", "Berlin") in INPUT_ARROW_DIRECTIONS
    response = app.server.test_client().get("/assets/dashboard.css")
    assert response.status_code == 200
    assert "outline: none" in response.text
