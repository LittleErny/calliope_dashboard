"""Initial selection and sparse date labels for the shared time control."""

import numpy as np
import pandas as pd


def annual_window_limits(index: pd.DatetimeIndex, durations=None) -> dict:
    """Last allowed timestep for each start, including timestep duration.

    A year is a calendar year, so leap years retain their extra day.
    """
    if not len(index):
        return {"max_end": []}
    if durations is None:
        step = index.to_series().diff().median() if len(index) > 1 else pd.Timedelta(hours=1)
        durations = np.full(len(index), step / pd.Timedelta(hours=1))
    ends = index + pd.to_timedelta(np.asarray(durations), unit="h")
    anniversaries = index + pd.DateOffset(years=1)
    max_end = ends.searchsorted(anniversaries, side="right") - 1
    return {"max_end": np.maximum(np.arange(len(index)), max_end).tolist()}


def initial_time_window(count: int) -> list[int]:
    last = max(0, count - 1)
    return [0, last if count <= 168 else min(last, 47)]


def time_marks(index: pd.DatetimeIndex) -> dict:
    if not len(index):
        return {}
    date_format = "%b %Y" if index[0].year != index[-1].year else "%d %b"
    positions = np.unique(np.linspace(0, len(index) - 1, min(4, len(index))).astype(int))
    return {
        int(i): {
            "label": index[i].strftime(date_format),
            "style": {"whiteSpace": "nowrap", "fontSize": "11px"},
        }
        for i in positions
    }
