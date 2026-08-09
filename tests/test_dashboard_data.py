from __future__ import annotations

import pickle
from pathlib import Path

from helpers.inputs_helper import InputsHelper
from helpers.operate_results_helper import OperateResultsHelper
from helpers.results_helper import ResultsHelper


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "models" / "mainkofen_case_study"


def _load_pickle(name: str):
    with open(MODEL_DIR / name, "rb") as file:
        return pickle.load(file)


def test_mainkofen_inputs() -> None:
    inputs = _load_pickle("mainkofen_model_inputs.pkl")
    helper = InputsHelper(inputs)

    assert helper.get_locations() == ["Mainkofen"]
    assert helper.get_timesteps_datetime().size == 8760
    assert inputs.attrs["termination_condition"] == "optimal"


def test_mainkofen_planning_results() -> None:
    inputs = _load_pickle("mainkofen_model_inputs.pkl")
    results = _load_pickle("mainkofen_model_results_planning.pkl")
    helper = ResultsHelper(results, inputs)

    assert helper.get_locations() == ["Mainkofen"]
    assert helper.get_carriers() == ["biomass", "electricity", "heat"]
    assert len(helper.get_plan_assets()) == 9
    assert results.attrs["termination_condition"] == "optimal"


def test_mainkofen_operate_results() -> None:
    inputs = _load_pickle("mainkofen_model_inputs.pkl")
    results = _load_pickle("mainkofen_model_results_operate.pkl")
    helper = OperateResultsHelper(results, inputs)

    assert helper.get_locations() == ["Mainkofen"]
    assert helper.get_carriers() == ["biomass", "electricity", "heat"]
    assert helper.get_timesteps_datetime().size == 8760
    assert results.attrs["termination_condition"] == "optimal"
