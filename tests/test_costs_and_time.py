"""Independent checks for exact cost accounting and long/mixed time axes."""

import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from app import app_data as d
from app.app import app
from app.figures import compute_resample_rule, downsample_series
from helpers.carriers import select_carrier
from helpers.costs import cost_ledger
from helpers.errors import DataUnavailable
from helpers.results_helper import ResultsHelper
from helpers.operate_results_helper import OperateResultsHelper


@pytest.mark.parametrize("scenario", ["default", "high_demand"])
def test_every_technology_and_cost_class_reconciles_exactly_to_netcdf(scenario):
    bundle = d.get_scenario(scenario)
    inp, raw = bundle.LOADED_INPUTS, bundle.LOADED_RESULTS
    ledger = cost_ledger(inp, raw, d.TIME_INDEX[0], d.TIME_INDEX[-1])
    active = inp.definition_matrix.astype(bool).any("carriers").to_series()
    assert len(ledger) == int(active.sum()) * raw.sizes["costs"]
    assert set(ledger.technology) == set(inp.techs.values)
    for row in ledger.to_dict("records"):
        selection = dict(nodes=row["location"], techs=row["technology"], costs=row["cost_class"])
        assert row["model_total"] == pytest.approx(float(raw.cost.sel(**selection).fillna(0).sum()))
        assert row["investment"] == pytest.approx(float(raw.cost_investment_annualised.sel(**selection).fillna(0).sum()))
        assert row["variable"] == pytest.approx(float(raw.cost_operation_variable.sel(**selection).fillna(0).sum()))
        assert row["window_total"] == pytest.approx(row["model_total"])
    for cls in raw.costs.values:
        assert ledger.loc[ledger.cost_class == cls, "model_total"].sum() == pytest.approx(float(raw.cost.sel(costs=cls).fillna(0).sum()))


def test_shared_costs_appear_once_and_exclusive_costs_plus_shared_equal_model():
    inp, raw = d.LOADED_INPUTS.copy(deep=True), d.LOADED_RESULTS.copy(deep=True)
    # A conversion-like technology connected to electricity and heat. Different
    # nodes deliberately have different scopes for the same technology ID.
    inp.definition_matrix.loc[dict(nodes="Berlin", techs="coal", carriers="heat")] = 1
    selected_costs = []
    for carrier in raw.carriers.values:
        _, scoped = select_carrier(inp, raw, str(carrier))
        assert float(scoped.cost.sel(nodes="Berlin", techs="coal").sum()) == 0
        selected_costs.append(scoped.cost.sum(["nodes", "techs"]))
    ledger = cost_ledger(inp, raw, d.TIME_INDEX[0], d.TIME_INDEX[-1])
    for cls in raw.costs.values:
        shared = ledger.loc[(ledger.scope == "Shared") & (ledger.cost_class == cls), "model_total"].sum()
        assert shared == pytest.approx(float(raw.cost.sel(nodes="Berlin", techs="coal", costs=cls)))
        assert sum(float(cost.sel(costs=cls)) for cost in selected_costs) + shared == pytest.approx(float(raw.cost.sel(costs=cls).sum()))


def test_negative_costs_custom_objectives_and_missing_components_are_not_relabelled_or_lost():
    inp, raw = d.LOADED_INPUTS.copy(deep=True), d.LOADED_RESULTS.copy(deep=True)
    raw = raw.assign_coords(costs=["monetary", "land_use"])
    inp = inp.assign_coords(costs=["monetary", "land_use"])
    raw.cost.loc[dict(nodes="Berlin", techs="coal", costs="monetary")] = -1234.567890123
    raw = raw.drop_vars("cost_operation_fixed")
    ledger = cost_ledger(inp, raw, d.TIME_INDEX[0], d.TIME_INDEX[23])
    row = ledger.query("location == 'Berlin' and technology == 'coal' and cost_class == 'monetary'").iloc[0]
    assert row.model_total == -1234.567890123
    assert row.fixed is None
    assert row.window_total is not None
    assert row.residual == pytest.approx(row.model_total-row.investment-row.variable)
    assert set(ledger.cost_class) == {"monetary", "land_use"}
    with pytest.raises(DataUnavailable, match="Monetary costs"):
        ResultsHelper(raw.sel(costs=["land_use"]), inp.sel(costs=["land_use"])).get_plan_assets()


def test_cost_window_uses_duration_and_weights_and_never_prorates_capex():
    inp, raw = d.LOADED_INPUTS.copy(deep=True), d.LOADED_RESULTS.copy(deep=True)
    inp.timestep_resolution[:] = 2
    inp.timestep_resolution[0] = .5
    inp.timestep_weights[:] = 1
    inp.timestep_weights[0] = 3
    ledger = cost_ledger(inp, raw, d.TIME_INDEX[0], d.TIME_INDEX[0])
    hours = inp.timestep_resolution * inp.timestep_weights
    fraction = float(hours[0]/hours.sum())
    row = ledger.query("location == 'Berlin' and technology == 'coal' and cost_class == 'monetary'").iloc[0]
    expected = (row.investment + row.fixed + row.residual) * fraction + float(raw.cost_operation_variable.sel(nodes="Berlin", techs="coal", costs="monetary").isel(timesteps=0))
    assert row.window_total == pytest.approx(expected)
    assert row.window_capex == row.capex
    helper = ResultsHelper(raw, inp)
    assert helper._window_fraction(d.TIME_INDEX[0], d.TIME_INDEX[0]) == pytest.approx(fraction)
    assert helper._hours_in_window(d.TIME_INDEX[0], d.TIME_INDEX[0]) == .5


def test_cost_chart_keeps_transmission_names_and_tables_keep_raw_numbers():
    callbacks = {cfg["callback"].__wrapped__.__name__: cfg["callback"].__wrapped__
                 for cfg in app.callback_map.values() if "callback" in cfg}
    output = callbacks["update_plan_dashboard"]("default", "electricity", [0,335], "location", "__all_locations__", None, "absolute")
    assert all(pd.notna(label) for trace in output[2].data for label in trace.x)
    assert any("Transmission" in str(label) or "transmission" in str(label) for trace in output[2].data for label in trace.x)
    assert all(isinstance(row["capex_eur"], (int,float)) for row in output[-1])
    cols, rows, note = callbacks["update_cost_ledger"]("default", [0,335], "monetary")
    assert sum(row["model_total"] for row in rows) == pytest.approx(float(d.LOADED_RESULTS.cost.sel(costs="monetary").sum()))
    assert any(row["model_total"] == 0 for row in rows)


def test_storage_energy_totals_and_soc_extrema_survive_yearly_downsampling():
    from app.callbacks.operate import _build_storage_figure
    from types import SimpleNamespace
    index = pd.date_range("2025-01-01", periods=8760, freq="h")
    soc = pd.Series(np.arange(len(index)) % 101, index=index, dtype=float)
    charge, discharge = soc / 10, soc / 20
    helper = SimpleNamespace(
        get_storage_soc_window=lambda *a: soc,
        get_storage_capacity=lambda *a: 100,
        get_location_tech_consumption_window=lambda *a: charge,
        get_location_tech_production_window=lambda *a: discharge,
        timestep_hours=lambda: pd.Series(1., index=index),
    )
    data = SimpleNamespace(OPERATE_HELPER=helper)
    flow = _build_storage_figure("City", "battery", "electricity", 0, 8759, "flow", data=data)
    assert len(flow.data[0].x) <= 60
    assert sum(flow.data[0].y) == pytest.approx(charge.sum())
    assert -sum(flow.data[1].y) == pytest.approx(discharge.sum())
    state = _build_storage_figure("City", "battery", "electricity", 0, 8759, "soc", data=data)
    assert len(state.data[0].x) <= 1200
    assert max(next(t for t in state.data if t.name == "SOC · max").y) == soc.max()
    assert min(next(t for t in state.data if t.name == "SOC · min").y) == soc.min()


@pytest.mark.parametrize("frequency", ["30min", "2h"])
def test_long_energy_series_conserve_totals_even_with_irregular_samples(frequency):
    index = pd.date_range("2024-01-01", periods=9000, freq=frequency).delete([3,5,9])
    energy = pd.Series(np.arange(len(index)), index=index, dtype=float)
    rule = compute_resample_rule(index, 1200)
    grouped = downsample_series(energy, 1200, "sum", rule)
    assert len(grouped) <= 1200
    assert grouped.sum() == pytest.approx(energy.sum())
    assert downsample_series(energy, 1200, "max", rule).max() == energy.max()


def test_half_hour_line_uses_kw_and_sending_end_loading():
    from app.callbacks.operate import _build_line_timeseries_figure
    from types import SimpleNamespace
    inp, raw = d.LOADED_OPERATE_INPUTS.copy(deep=True), d.LOADED_OPERATE_RESULTS
    inp.timestep_resolution[:] = .5
    helper = OperateResultsHelper(raw, inp)
    line = next(line for line in helper.get_line_ids() if helper.get_line_total_flow(line, "electricity") > 0)
    ref = helper.get_line_ref(line)
    fig = _build_line_timeseries_figure(ref.src, ref.dst, "electricity", 0, 335, data=SimpleNamespace(OPERATE_HELPER=helper, OPERATE_TIMESTEPS=d.TIME_INDEX))
    trace = next(t for t in fig.data if t.name.startswith(f"{ref.src} → {ref.dst}"))
    np.testing.assert_allclose(trace.y, helper.get_line_flow_window(line, "electricity", 0,335)/.5)
    np.testing.assert_allclose(np.asarray(trace.customdata)[:,0], helper.get_line_load_fraction_window(line,"electricity",0,335)*100)
    assert fig.layout.yaxis.title.text == "kW"
    changed = raw.copy(deep=True)
    changed["flow_cap"] = inp.flow_cap.copy(deep=True) * .5
    optimized = OperateResultsHelper(changed, inp)
    assert optimized.get_line_capacity(line) == pytest.approx(helper.get_line_capacity(line)*.5)


def test_data_failures_raise_log_and_clear_callback_outputs(monkeypatch, caplog):
    helper = OperateResultsHelper(d.LOADED_OPERATE_RESULTS, d.LOADED_OPERATE_INPUTS)
    with pytest.raises(DataUnavailable, match="Cannot read operate"):
        helper._series("flow_out", nodes="nonexistent")
    assert "nonexistent" in caplog.text
    broken = ResultsHelper(d.LOADED_RESULTS.drop_vars("cost"), d.LOADED_INPUTS)
    with pytest.raises(DataUnavailable, match="missing cost"):
        broken.get_plan_assets()
    monkeypatch.setattr(d.get_scenario("default").RESULTS_HELPER, "get_plan_assets", lambda *a, **kw: (_ for _ in ()).throw(DataUnavailable("Broken cost fixture")))
    # Exercise the actual Dash HTTP error handler, not only a helper exception.
    output = next(key for key in app.callback_map if "cost-ledger-table.columns" in key)
    monkeypatch.setattr(__import__('app.costs_view', fromlist=['cost_ledger']), 'cost_ledger', lambda *a: (_ for _ in ()).throw(DataUnavailable("Broken cost fixture")))
    config = app.callback_map[output]
    outputs = [{"id": o.component_id, "property": o.component_property} for o in config["output"]]
    response = app.server.test_client().post('/_dash-update-component', json={"output": output, "outputs": outputs,
        "inputs": [{"id":"dd-scenario","property":"value","value":"default"}, {"id":"applied-time","property":"data","value":[0,335]},
                   {"id":"cost-ledger-class","property":"value","value":"monetary"}],
        "state":[], "changedPropIds":["dd-scenario.value"]})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['response']['cost-ledger-table']['data'] == []
    assert 'Broken cost fixture' in payload['sideUpdate']['data-error-message']['children']


def test_operate_failure_explains_missing_run_and_tab_switch_clears_banner(monkeypatch):
    import app.callbacks.operate as operate_callbacks

    def missing_results(*args, **kwargs):
        raise DataUnavailable("Missing dispatch results")

    monkeypatch.setattr(operate_callbacks, "_build_line_components", missing_results)
    response = app.server.test_client().post('/_dash-update-component', json={
        "output": "operate-map-layer.children",
        "outputs": {"id": "operate-map-layer", "property": "children"},
        "inputs": [
            {"id": "operate-map-mode", "property": "value", "value": "critical"},
            {"id": "operate-timestep", "property": "value", "value": 0},
            {"id": "dd-carrier", "property": "value", "value": "electricity"},
            {"id": "operate-map", "property": "zoom", "value": 6},
            {"id": "applied-time", "property": "data", "value": [0, 23]},
            {"id": "dd-scenario", "property": "value", "value": "default"},
        ], "state": [], "changedPropIds": ["dd-scenario.value"],
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['response']['operate-map-layer']['children'] == []
    message = payload['sideUpdate']['data-error-message']['children']
    assert 'Missing dispatch results' in message
    assert 'Operate results may not have been calculated' in message
    # Verify the browser clears both the banner and its text on a mode change.
    dependency = next(c for c in app._callback_list
                      if 'data-error-banner.style' in c['output'])
    assert {'id': 'tabs-mode', 'property': 'value'} in dependency['inputs']
    if shutil.which('node'):
        source = next(s for s in app._inline_scripts
                      if dependency['clientside_function']['function_name'] in s)
        script = "global.window={dash_clientside:{}};\n" + source
        script += "\nconst f=window.dash_clientside[" + json.dumps(dependency['clientside_function']['namespace']) + "][" + json.dumps(dependency['clientside_function']['function_name']) + "];"
        script += "require('assert/strict').deepEqual(f(0,'results_planning'),[{display:'none'},'']);"
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


def test_exact_date_inputs_validate_snap_and_do_not_apply():
    if not shutil.which("node"):
        pytest.skip("Node unavailable")
    asset = Path(__file__).resolve().parents[1]/'app/assets/time_window.js'
    script = r"""
const fs=require('fs'), assert=require('assert/strict');
global.window={dash_clientside:{no_update:'NO',callback_context:{triggered:[{prop_id:'time-end-input.value'}]}}};
eval(fs.readFileSync(process.argv[1],'utf8'));
const f=window.dash_clientside.timeWindow.edit;
const iso=['2024-01-01T00:00','2024-01-01T02:00','2024-01-01T04:00'];
const applied=[0,0], limits={max_end:[2,2,2]};
let result=f([0,0],applied,'2024-01-01 00:00','2024-01-01 03:00',iso,limits,[0,0],iso);
assert.deepEqual(result[0],[0,1]);
assert.match(result[8],/Snapped/);
assert.deepEqual(applied,[0,0]);
assert.equal(result[5],false);
result=f([0,0],applied,'2024-01-01 00:00','2024-02-30 03:00',iso,limits,[0,0],iso);
assert.equal(result[5],true);
assert.match(result[8],/valid model date/);
"""
    subprocess.run(['node','-e',script,str(asset)],check=True,capture_output=True,text=True)
