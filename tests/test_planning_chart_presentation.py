"""Chart layout must retain the model values behind each category."""
import numpy as np
import pytest

from app import app_data
from app.app import app
from helpers.results_helper import ALL_LOCATIONS


@pytest.mark.parametrize("scenario,carrier,view,location,tech,norm", [
    ("default", "electricity", "location", ALL_LOCATIONS, None, "absolute"),
    ("high_demand", "heat", "location", "Berlin", None, "per_kw"),
    ("default", "electricity", "technology", None, "Wind Energy", "absolute"),
])
def test_vertical_breakdowns_preserve_category_values(scenario, carrier, view, location, tech, norm):
    callback = next(v["callback"].__wrapped__ for v in app.callback_map.values()
                    if "callback" in v and v["callback"].__wrapped__.__name__ == "update_plan_dashboard")
    _, capacity, costs, co2, *_ = callback(scenario, carrier, [0, 47], view, location, tech, norm)
    bundle = app_data.get_scenario(scenario, carrier)
    helper = bundle.RESULTS_HELPER
    group = helper.resolve_plan_selection(view, location, tech)["group_key"]
    args = dict(scenario_id=scenario, carrier=carrier, view_mode=view,
                selected_location=location, selected_tech=tech)
    expected_capacity = helper.get_plan_capacity_group(**args)
    if not expected_capacity.empty:
        trace = capacity.data[0]
        assert trace.orientation == "v"
        actual = dict(zip(trace.x, trace.y))
        for _, row in expected_capacity.iterrows():
            assert actual[row[group]] == pytest.approx(row["carrier_capacity_kw"])
    start, end = bundle.TIME_INDEX[0], bundle.TIME_INDEX[47]
    expected_cost = helper.get_plan_cost_group(scenario_id=scenario, start_ts=start, end_ts=end,
                                               view_mode=view, selected_location=location, selected_tech=tech)
    if norm == "per_kw":
        expected_cost = expected_cost[expected_cost.built_capacity_kw > 0]
    components = {"Annualised investment": "annualised_investment_eur",
                  "Fixed OPEX": "fixed_opex_eur", "Variable OPEX": "variable_opex_eur",
                  "Other / residual": "other_costs_eur"}
    for trace in costs.data:
        assert trace.orientation == "v"
        actual = dict(zip(trace.x, trace.y))
        for _, row in expected_cost.iterrows():
            expected = row[components[trace.name]]
            if norm == "per_kw":
                expected /= row["built_capacity_kw"]
            if not np.isnan(expected):
                assert actual[row[group]] == pytest.approx(expected)
    expected_co2 = helper.get_plan_co2_group(scenario_id=scenario, start_ts=start, end_ts=end,
                                              view_mode=view, selected_location=location, selected_tech=tech)
    if not expected_co2.empty:
        trace = co2.data[0]
        assert trace.orientation == "v"
        actual = dict(zip(trace.x, trace.y))
        for _, row in expected_co2.iterrows():
            assert actual[row[group]] == pytest.approx(row["co2_kg"])
