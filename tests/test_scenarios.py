"""Scenario switching must select different solved data, including carrier scope."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest
import xarray as xr

from app import app_data as d
from app.app import app
from helpers.results_helper import ALL_LOCATIONS


@pytest.mark.parametrize("carrier", ["electricity", "heat"])
def test_high_demand_changes_only_demand_inputs_by_twenty_percent(carrier):
    baseline = d.get_scenario("default", carrier)
    stress = d.get_scenario("high_demand", carrier)
    np.testing.assert_allclose(stress.LOADED_INPUTS.sink_use_equals,
                               baseline.LOADED_INPUTS.sink_use_equals * 1.2)
    xr.testing.assert_equal(stress.LOADED_INPUTS.source_use_max,
                            baseline.LOADED_INPUTS.source_use_max)
    assert stress.LOADED_RESULTS.attrs["scenario_id"] == "high_demand"
    assert stress.LOADED_OPERATE_RESULTS.attrs["scenario_id"] == "high_demand"
    for bundle in (baseline, stress):
        np.testing.assert_allclose(
            bundle.LOADED_OPERATE_RESULTS.flow_in.where(bundle.LOADED_OPERATE_INPUTS.base_tech == "demand", 0).sum(["techs", "carriers"]).transpose("nodes", "timesteps"),
            bundle.LOADED_OPERATE_INPUTS.sink_use_equals.fillna(0).sum("techs").transpose("nodes", "timesteps"),
            rtol=1e-6, atol=0.2,
        )


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
def test_financial_carrier_slices_reconcile_to_complete_model(scenario):
    costs = []
    emissions = []
    for carrier in ("electricity", "heat"):
        bundle = d.get_scenario(scenario, carrier)
        kpis = bundle.RESULTS_HELPER.get_plan_kpis(
            scenario, carrier, d.TIME_INDEX[0], d.TIME_INDEX[-1], "location", ALL_LOCATIONS, None
        )
        costs.append(kpis["total_cost"])
        emissions.append(kpis["co2_kg"])
    raw = d.get_scenario(scenario).LOADED_RESULTS
    assert sum(costs) == pytest.approx(float(raw.cost.sel(costs="monetary").sum()))
    assert sum(emissions) == pytest.approx(float(raw.cost.sel(costs="co2").sum()))
    heat = d.get_scenario(scenario, "heat")
    assert heat.RESULTS_HELPER.get_technologies() == ["Gas Boiler", "Solar Thermal"]
    assert heat.OPERATE_HELPER.get_physical_lines() == []
    assert "storage" not in heat.LOADED_RESULTS.techs
    assert "gas_boiler" not in d.get_scenario(scenario, "electricity").LOADED_RESULTS.techs


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
def test_map_layers_hide_electricity_connections_when_heat_selected(scenario):
    callbacks = {v["callback"].__wrapped__.__name__: v["callback"].__wrapped__
                 for v in app.callback_map.values() if "callback" in v}
    for mode in ("timestep", "critical"):
        layers = callbacks["update_operate_map"](mode, 0, "heat", 6, [0, 335], scenario)
        paths = [x for x in layers if x.__class__.__name__ in {"Polyline", "Polygon"}]
        assert paths and all(x.positions == [] for x in paths)
    layers = callbacks["update_inputs_map"]("inputs-map", "heat", scenario, 6)
    paths = [x for x in layers if x.__class__.__name__ in {"Polyline", "Polygon"}]
    assert paths and all(x.positions == [] for x in paths)
    assert all(x == [] for x in callbacks["scale_inputs_arrowheads"](6, "heat", scenario))


def test_each_data_callback_listens_to_scenario_changes():
    names = {"update_inputs_map", "scale_inputs_arrowheads", "display_inputs_info",
             "update_inputs_techs_list", "update_plan_selector", "update_plan_dashboard",
             "update_operate_map", "update_storage_graph", "update_operate_info"}
    for config in app.callback_map.values():
        if "callback" in config and config["callback"].__wrapped__.__name__ in names:
            assert {"id": "dd-scenario", "property": "value"} in config["inputs"]


def test_single_export_without_scenario_manifest_still_loads(tmp_path):
    for name in ("planning.nc", "operate.nc"):
        shutil.copy2(d.MODEL_DIR / name, tmp_path / name)
    result = subprocess.run(
        [sys.executable, "-c", "import json; from app import app_data as d; print(json.dumps(d.SCENARIOS))"],
        env={**os.environ, "CALLIOPE_DASHBOARD_MODEL_DIR": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
        cwd=Path(__file__).parents[1], capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == ["default"]


def test_scenario_can_change_before_input_map_markers_mount():
    key, config = next((key, config) for key, config in app.callback_map.items()
                       if "callback" in config and config["callback"].__wrapped__.__name__ == "display_inputs_info")
    for dependency in config["inputs"]:
        if dependency["id"].startswith("inputs-"):
            assert dependency["allow_optional"] is True
    payload = {
        "output": key,
        "outputs": [{"id": x.component_id, "property": x.component_property} for x in config["output"]],
        "inputs": [{"id": x["id"], "property": x["property"],
                    "value": "high_demand" if x["id"] == "dd-scenario" else "heat" if x["id"] == "dd-carrier" else None}
                   for x in config["inputs"]],
        "state": [{"id": "inputs-selected-city", "property": "data", "value": "Berlin"}],
        "changedPropIds": ["dd-scenario.value"],
    }
    response = app.server.test_client().post("/_dash-update-component", json=payload)
    assert response.status_code == 200
    assert response.json["response"]["inputs-selected-city"]["data"] == "Berlin"


def test_investment_scenarios_support_different_technologies_and_carriers(tmp_path):
    """A scenario must not invent heat or disabled equipment to fit the root."""
    for filename in ("planning.nc", "operate.nc"):
        shutil.copy2(d.MODEL_DIR / filename, tmp_path / filename)
        destination = tmp_path / "electric_only" / filename
        destination.parent.mkdir(exist_ok=True)
        for group in ("inputs", "results", "attrs"):
            with xr.open_dataset(d.MODEL_DIR / filename, group=group, engine="h5netcdf") as raw:
                data = raw.load()
            if "carriers" in data.coords:
                data = data.sel(carriers=["electricity"])
            if "techs" in data.coords:
                data = data.drop_sel(techs=["coal"])
            data.to_netcdf(destination, group=group, engine="h5netcdf",
                           mode="w" if group == "inputs" else "a")
    (tmp_path / "dashboard_scenarios.json").write_text(json.dumps({
        "default": "default", "scenarios": [
            {"id": "default", "label": "Both carriers", "planning": "planning.nc", "operate": "operate.nc"},
            {"id": "electric_only", "label": "Electric only", "planning": "electric_only/planning.nc", "operate": "electric_only/operate.nc"},
        ],
    }))
    script = '''
from dash.exceptions import PreventUpdate
from app import app_data as d
from app.app import app
from helpers.results_helper import ALL_LOCATIONS
bundle = d.get_scenario('electric_only', 'electricity')
assert bundle.LOADED_INPUTS.carriers.values.tolist() == ['electricity']
assert 'coal' not in bundle.LOADED_INPUTS.techs.values
callbacks = {c['callback'].__wrapped__.__name__: c['callback'].__wrapped__
             for c in app.callback_map.values() if 'callback' in c}
options, selected = callbacks['update_scenario_carriers']('electric_only', 'heat')
assert options == [{'label': 'electricity', 'value': 'electricity'}]
assert selected == 'electricity'
try:
    d.get_scenario('electric_only', 'heat')
except PreventUpdate:
    pass
else:
    raise AssertionError('Stale carrier must wait for the selector update')
response = app.server.test_client().post('/_dash-update-component', json={
    'output': 'operate-map-layer.children',
    'outputs': {'id': 'operate-map-layer', 'property': 'children'},
    'inputs': [
        {'id': 'operate-map-mode', 'property': 'value', 'value': 'timestep'},
        {'id': 'operate-timestep', 'property': 'value', 'value': 0},
        {'id': 'dd-carrier', 'property': 'value', 'value': 'heat'},
        {'id': 'operate-map', 'property': 'zoom', 'value': 6},
        {'id': 'applied-time', 'property': 'data', 'value': [0, 23]},
        {'id': 'dd-scenario', 'property': 'value', 'value': 'electric_only'},
    ], 'state': [], 'changedPropIds': ['dd-scenario.value'],
})
assert response.status_code == 204, response.get_data(as_text=True)
options, selected = callbacks['update_scenario_carriers']('default', 'electricity')
assert {o['value'] for o in options} == {'electricity', 'heat'}
assert selected == 'electricity'
for name, args in [
    ('update_plan_dashboard', ('electric_only','electricity',[0,23],'location',ALL_LOCATIONS,None,'absolute')),
    ('update_operate_map', ('timestep',0,'electricity',6,[0,23],'electric_only')),
    ('update_inputs_map', ('inputs-map','electricity','electric_only',6)),
]:
    assert callbacks[name](*args) is not None, name
print('heterogeneous scenarios OK')
'''
    result = subprocess.run([sys.executable, "-c", script],
        env={**os.environ, "CALLIOPE_DASHBOARD_MODEL_DIR": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
        cwd=Path(__file__).parents[1], capture_output=True, text=True, check=True)
    assert "heterogeneous scenarios OK" in result.stdout
