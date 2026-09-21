from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import xarray as xr

from calliope_dashboard import CalliopeDashboard


class FakeModel:
    def __init__(self) -> None:
        self.results = xr.Dataset()

    def to_netcdf(self, path) -> None:
        path.write_bytes(b"dashboard fixture")


class FakeParetoResult:
    method = "weighted_sum"
    points = pd.DataFrame(
        [{"point_id": 7, "objective_1": 10.0, "objective_2": 20.0}]
    )

    def solution(self, point_id: int) -> xr.Dataset:
        if point_id != 7:
            raise KeyError(point_id)
        return xr.Dataset({"answer": xr.DataArray(42.0)})


def test_prepare_pareto_solution(tmp_path) -> None:
    created = SimpleNamespace(model=None)

    def model_factory():
        created.model = FakeModel()
        return created.model

    dashboard = CalliopeDashboard.from_pareto(
        result=FakeParetoResult(),
        point_id=7,
        model_factory=model_factory,
        data_dir=tmp_path,
    )

    assert dashboard.prepare() == tmp_path
    assert float(created.model.results.answer) == 42.0
    assert (tmp_path / "planning.nc").is_file()
    assert (tmp_path / "operate.nc").is_file()
    metadata = json.loads((tmp_path / "selection.json").read_text())
    assert metadata["pareto_method"] == "weighted_sum"
    assert metadata["pareto_point_id"] == 7
