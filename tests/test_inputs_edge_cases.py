"""Inputs must distinguish absent technologies, zero profiles and missing data."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
import xarray as xr
from plotly.utils import PlotlyJSONEncoder

from app import app_data as d
from app.app import app
from helpers.inputs_helper import InputsHelper


def callbacks():
    return {c['callback'].__wrapped__.__name__: c['callback'].__wrapped__
            for c in app.callback_map.values() if 'callback' in c}


def install_inputs(monkeypatch, inputs):
    bundle = SimpleNamespace(**vars(d.get_scenario('default')))
    bundle.INPUT_HELPER = InputsHelper(inputs)
    monkeypatch.setattr(d, 'get_scenario', lambda *args: bundle)
    return bundle.INPUT_HELPER


def text(value):
    return json.dumps(value, cls=PlotlyJSONEncoder)


def set_input(inputs, variable, value, **selection):
    selected = {k: v for k, v in selection.items() if k in inputs[variable].dims}
    inputs[variable].loc[selected] = value


def test_node_without_selected_carrier_shows_explicit_zero_demand(monkeypatch):
    inputs = d.LOADED_INPUTS.copy(deep=True)
    inputs.definition_matrix.loc[dict(nodes='Berlin', carriers='heat')] = False
    install_inputs(monkeypatch, inputs)
    result = callbacks()['update_inputs_techs_list']('heat', 'Berlin', [0, 23], 'default')
    body = text(result)
    assert '0 kWh' in body
    assert 'No heat technologies are defined at Berlin' in body
    assert 'No fixed heat demand technology' in body
    # Exercise a real marker/filter event: absence of local techs must not
    # reset the selected city back to the initial click-a-city placeholder.
    key, cfg = next((key, c) for key, c in app.callback_map.items()
                    if 'callback' in c and c['callback'].__wrapped__.__name__ == 'display_inputs_info')
    response = app.server.test_client().post('/_dash-update-component', json={
        'output': key,
        'outputs': [{'id': o.component_id, 'property': o.component_property} for o in cfg['output']],
        'inputs': [{'id': dep['id'], 'property': dep['property'],
                    'value': 'default' if dep['id'] == 'dd-scenario' else 'heat' if dep['id'] == 'dd-carrier' else None}
                   for dep in cfg['inputs']],
        'state': [{'id': 'inputs-selected-city', 'property': 'data', 'value': 'Berlin'}],
        'changedPropIds': ['dd-carrier.value'],
    })
    assert response.status_code == 200
    assert response.json['response']['inputs-selected-city']['data'] == 'Berlin'


def test_defined_zero_demand_is_labeled_zero_not_missing(monkeypatch):
    inputs = d.LOADED_INPUTS.copy(deep=True)
    set_input(inputs, 'sink_use_equals', 0, nodes='Berlin', techs='heat_demand')
    install_inputs(monkeypatch, inputs)
    body = text(callbacks()['update_inputs_techs_list']('heat', 'Berlin', [0, 23], 'default'))
    assert '0.00 kWh' in body
    assert 'defined demand profile is zero' in body
    assert 'Not specified' not in body


def test_demand_without_fixed_profile_is_not_reported_as_zero(monkeypatch):
    inputs = d.LOADED_INPUTS.copy(deep=True).drop_vars('sink_use_equals')
    install_inputs(monkeypatch, inputs)
    body = text(callbacks()['update_inputs_techs_list']('heat', 'Berlin', [0, 23], 'default'))
    assert 'Not specified' in body
    assert 'without a fixed demand profile' in body
    assert '0 kWh' not in body


@pytest.mark.parametrize('variable,tech,carrier,notice', [
    ('source_use_max', 'pv', 'electricity', 'Resource data is missing for 1'),
    ('sink_use_equals', 'heat_demand', 'heat', 'Demand data is missing for 1'),
])
def test_one_gap_does_not_break_valid_dates_or_turn_into_zero(monkeypatch, variable, tech, carrier, notice):
    inputs = d.LOADED_INPUTS.copy(deep=True)
    set_input(inputs, variable, np.nan, nodes='Berlin', techs=tech, timesteps=d.TIME_INDEX[-1])
    helper = install_inputs(monkeypatch, inputs)
    cb = callbacks()['update_inputs_techs_list']
    assert notice not in text(cb(carrier, 'Berlin', [0, 23], 'default'))
    assert notice in text(cb(carrier, 'Berlin', [0, d.T-1], 'default'))
    if variable == 'sink_use_equals':
        values = helper.get_location_demand('Berlin', carrier)[0]
    else:
        values = helper.get_location_total_max_supply('Berlin', carrier)['Berlin::pv']
    assert np.isnan(values[-1])


def test_unbounded_solar_capacity_still_has_zero_availability_at_night(monkeypatch):
    inputs = d.LOADED_INPUTS.copy(deep=True)
    set_input(inputs, 'flow_cap_max', np.nan, nodes='Berlin', techs='pv')
    set_input(inputs, 'source_use_max', 0, nodes='Berlin', techs='pv', timesteps=d.TIME_INDEX[0])
    helper = install_inputs(monkeypatch, inputs)
    values = helper.get_location_total_max_supply('Berlin', 'electricity')['Berlin::pv']
    assert values[0] == 0
    assert not np.isnan(values).any()
    body = text(callbacks()['update_inputs_techs_list']('electricity', 'Berlin', [0, 23], 'default'))
    assert 'no finite upper bound' in body


def test_storage_energy_capacity_cost_is_explicit(monkeypatch):
    inputs = d.LOADED_INPUTS.copy(deep=True)
    inputs['cost_storage_cap'] = xr.full_like(inputs.cost_flow_cap, np.nan)
    set_input(inputs, 'cost_storage_cap', 225, nodes='Berlin', techs='storage', costs='monetary')
    helper = install_inputs(monkeypatch, inputs)
    assert helper.get_loc_tech_costs('Berlin', 'storage')['cost_storage_cap'] == 225
    body = text(callbacks()['update_inputs_techs_list']('electricity', 'Berlin', [0, 23], 'default'))
    assert 'Storage capacity cost' in body
    assert '225 per kWh' in body
