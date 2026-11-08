"""Energy conservation, readable intervals, and the calendar-year slider cap."""

import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from app.coverage import aggregate_coverage
from app.time_window import annual_window_limits, time_marks


@pytest.mark.parametrize("start,days,interval", [
    ("2025-01-01", 1, "1 hour"),
    ("2025-01-01 03:00", 7, "3 hours"),
    ("2025-01-01", 14, "6 hours"),
    ("2025-01-01 05:00", 31, "1 day"),
    ("2025-01-01", 365, "1 week (Mon–Sun)"),
    ("2024-01-01", 366, "1 week (Mon–Sun)"),
])
def test_calendar_bins_conserve_energy_and_show_exact_bounds(start, days, interval):
    index = pd.date_range(start, periods=days * 24, freq="h")
    energy = pd.DataFrame({"local": np.arange(len(index)), "imports": 2.0}, index=index)
    totals, bounds, label = aggregate_coverage(energy, pd.Series(1, index=index))
    assert label == interval
    assert len(totals) <= 60
    np.testing.assert_allclose(totals.sum(), energy.sum())
    assert bounds.start.iloc[0] == index[0]
    assert bounds.end.iloc[-1] == index[-1] + pd.Timedelta(hours=1)
    if "week" in label:
        assert (totals.index.dayofweek == 0).all()
    # Nothing outside the selected range contributes to partial edge bins.
    for bin_id, period in bounds.iterrows():
        expected = energy.loc[(index >= period.start) & (index < period.end)].sum()
        np.testing.assert_allclose(totals.loc[bin_id], expected)


def test_coverage_allocates_before_grouping_and_hourly_preserves_all_steps():
    from app.callbacks.operate import _build_demand_coverage_figure

    index = pd.date_range("2025-01-01", periods=365 * 24, freq="h")
    demand = pd.Series(np.tile([10., 100.], len(index) // 2), index=index)
    local = pd.Series(np.tile([100., 1.], len(index) // 2), index=index)
    imports = pd.Series(20., index=index)
    unmet = demand * .1
    helper = SimpleNamespace(
        inputs=xr.Dataset({"timestep_resolution": ("timesteps", np.ones(len(index)))}, coords={"timesteps": index}),
        get_location_effective_demand_window=lambda *a: demand,
        get_location_unmet_window=lambda *a: unmet,
        get_location_techs=lambda *a, **kw: ["local"],
        get_location_tech_production_window=lambda *a: local,
        get_incoming_line_ids=lambda *a: ["line"],
        get_line_ref=lambda *a: SimpleNamespace(src="Other", tech="line"),
        get_line_flow_window=lambda *a: imports,
        get_technology_color_map=lambda: {},
    )
    bundle = SimpleNamespace(OPERATE_HELPER=helper)
    auto = _build_demand_coverage_figure("City", "heat", 0, len(index)-1, data=bundle)
    hourly = _build_demand_coverage_figure("City", "heat", 0, len(index)-1, data=bundle, mode="hourly")
    expected_local = (demand * .9 * local / (local + imports)).sum()
    for fig, count in [(auto, 53), (hourly, len(index))]:
        assert len(fig.data[0].x) == count
        assert sum(fig.data[0].y) == pytest.approx(expected_local)
        assert sum(sum(trace.y) for trace in fig.data) == pytest.approx(demand.sum())
        np.testing.assert_allclose(np.array([trace.customdata for trace in fig.data], dtype=object)[:, :, 0].astype(float).sum(axis=0), 100)
    assert "1 week" in auto.layout.xaxis.title.text
    assert "1 hour" in hourly.layout.xaxis.title.text


@pytest.mark.parametrize("start,expected_end", [
    ("2023-01-01", "2023-12-31 23:00"),
    ("2024-01-01", "2024-12-31 23:00"),
    ("2024-02-29", "2025-02-27 23:00"),
])
def test_year_limit_counts_calendar_year_and_last_step_duration(start, expected_end):
    index = pd.date_range(start, periods=2 * 366 * 24, freq="h")
    limits = annual_window_limits(index)
    assert index[limits["max_end"][0]] == pd.Timestamp(expected_end)
    ends = index + pd.Timedelta(hours=1)
    assert (ends.take(limits["max_end"]) <= index + pd.DateOffset(years=1)).all()
    # The window can slide through all years, including the simulation's end.
    assert limits["max_end"][-1] == len(index)-1


def test_browser_range_normalization_moves_opposite_handle_and_waits_for_apply():
    if not shutil.which("node"):
        pytest.skip("Node is required for the client-side range check")
    index = pd.date_range("2023-01-01", "2025-12-31 23:00", freq="h")
    limits = annual_window_limits(index)
    assert "2023" in time_marks(index)[0]["label"]
    assert "2025" in time_marks(index)[len(index)-1]["label"]
    asset = Path(__file__).resolve().parents[1] / "app/assets/time_window.js"
    script = """
const fs = require('fs');
const assert = require('assert/strict');
global.window = {dash_clientside: {no_update: 'NO_UPDATE'}};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const limits = JSON.parse(fs.readFileSync(0, 'utf8'));
const control = window.dash_clientside.timeWindow;
let range = control.normalize([0, 17543], [0, 47], limits);
assert.equal(range[1], 17543); // End handle remains where the user put it.
assert.ok(range[1] <= limits.max_end[range[0]]);
assert.ok(limits.max_end[range[0] - 1] < range[1]);
let backwards = control.normalize([0, 17543], range, limits);
assert.deepEqual(backwards, [0, limits.max_end[0]]);
const applied = [0, 47];
let output = control.update([0, 17543], applied, Array(limits.max_end.length).fill('date'), limits, [0, 47]);
assert.deepEqual(applied, [0, 47]);
assert.deepEqual(output[0], range);
assert.equal(output[5], false);
assert.match(output[4], /Not applied/);
assert.equal(control.update(range, range, Array(limits.max_end.length).fill('date'), limits, range)[5], true);
"""
    subprocess.run(["node", "-e", script, str(asset)], input=json.dumps(limits), text=True, check=True, capture_output=True)
