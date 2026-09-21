from __future__ import annotations

from pathlib import Path

import pytest
import xarray as xr

from helpers.inputs_helper import InputsHelper
from helpers.operate_results_helper import OperateResultsHelper
from helpers.results_helper import ALL_LOCATIONS, ResultsHelper


MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "1_german_scale"
CALLIOPE_VERSION = "0.7.0.dev7"


def _load(path: Path, group: str) -> xr.Dataset:
    with xr.open_dataset(path, group=group, engine="h5netcdf") as dataset:
        loaded = dataset.load()
    loaded.attrs["calliope_version"] = CALLIOPE_VERSION
    return loaded


def test_german_scale_inputs() -> None:
    inputs = _load(MODEL_DIR / "planning.nc", "inputs")
    helper = InputsHelper(inputs)

    assert helper.get_locations() == [
        "Berlin", "Cologne", "Frankfurt", "Hamburg",
        "Hannover", "Leipzig", "Munich", "Nuremberg",
    ]
    assert helper.get_timesteps_datetime().size == 336
    assert len(helper.get_transmission_lines()) == 8
    assert helper.get_location_demand("Berlin", "electricity")


def test_german_scale_planning_results() -> None:
    inputs = _load(MODEL_DIR / "planning.nc", "inputs")
    results = _load(MODEL_DIR / "planning.nc", "results")
    helper = ResultsHelper(results, inputs)

    assert helper.get_carriers() == ["electricity"]
    assert helper.get_technologies() == [
        "Battery Storage", "Coal Power Plant", "Gas Power Plant",
        "Hydropower (Dams)", "Solar Photovoltaic Power", "Wind Energy",
    ]
    assert helper.get_plan_assets().built_capacity_kw.sum() > 0
    assert helper.get_plan_energy().energy_kwh.sum() > 0


def test_german_scale_operate_results() -> None:
    inputs = _load(MODEL_DIR / "operate.nc", "inputs")
    results = _load(MODEL_DIR / "operate.nc", "results")
    helper = OperateResultsHelper(results, inputs)

    assert helper.get_timesteps_datetime().size == 336
    assert helper.get_carriers() == ["electricity"]
    assert len(helper.get_physical_lines()) == 8
    for line_id in helper.get_line_ids():
        assert helper.get_line_capacity(line_id) > 0
        assert helper.get_line_total_flow(line_id, "electricity") >= 0
    assert helper.get_storage_capacity("Berlin", "storage") > 0


def test_netcdf_metadata_records_optimal_solutions() -> None:
    for name in ("planning.nc", "operate.nc"):
        metadata = _load(MODEL_DIR / name, "attrs")
        assert "calliope_version_initialised: 0.7.0.dev7" in metadata.attrs["runtime"]
        assert "termination_condition: optimal" in metadata.attrs["runtime"]


def test_dashboard_queries_cover_each_view() -> None:
    from app import app_data

    start_ts = app_data.TIME_INDEX[0]
    end_ts = app_data.TIME_INDEX[-1]
    helper = app_data.RESULTS_HELPER

    for location in app_data.PLAN_LOCATIONS:
        kwargs = {
            "scenario_id": "default",
            "carrier": "electricity",
            "start_ts": start_ts,
            "end_ts": end_ts,
            "view_mode": "location",
            "selected_location": location,
            "selected_tech": None,
        }
        assert set(helper.get_plan_kpis(**kwargs)) == {
            "capacity", "capex", "opex", "production", "co2_kg"
        }
        assert "Name" in helper.get_plan_detail_table(**kwargs).columns

    all_locations = {
        "scenario_id": "default",
        "carrier": "electricity",
        "start_ts": start_ts,
        "end_ts": end_ts,
        "view_mode": "location",
        "selected_location": ALL_LOCATIONS,
        "selected_tech": None,
    }
    all_kpis = helper.get_plan_kpis(**all_locations)
    location_capacity = sum(
        helper.get_plan_kpis(
            **{**all_locations, "selected_location": location}
        )["capacity"]
        for location in app_data.PLAN_LOCATIONS
    )
    assert all_kpis["capacity"] == pytest.approx(location_capacity)
    assert helper.get_plan_production_timeseries(**all_locations).group_label.nunique() > 1
    assert helper.get_plan_demand_timeseries(**all_locations).demand_kwh.sum() > 0

    operate = app_data.OPERATE_HELPER
    for location in operate.get_locations():
        kpis = operate.get_location_operate_kpis_window(
            location, "electricity", 0, app_data.OPERATE_T - 1
        )
        assert set(kpis) == {
            "total_demand", "total_unmet", "total_production", "total_variable_cost"
        }

    for a, b in operate.get_physical_lines():
        a_to_b, b_to_a = operate.get_line_ids_for_pair(a, b)
        assert a_to_b is not None
        assert b_to_a is not None
