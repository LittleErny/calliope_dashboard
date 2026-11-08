"""Calendar-aligned energy totals for the demand coverage chart."""

import pandas as pd


COVERAGE_MAX_BARS = 60
INTERVALS = [
    ("1h", "1 hour"), ("2h", "2 hours"), ("3h", "3 hours"),
    ("4h", "4 hours"), ("6h", "6 hours"), ("12h", "12 hours"),
    ("1D", "1 day"), ("W-MON", "1 week (Mon–Sun)"),
    ("MS", "1 month"), ("QS", "1 quarter"), ("YS", "1 year"),
]


def aggregate_coverage(energy: pd.DataFrame, durations: pd.Series, mode="auto"):
    """Sum energy, retaining actual covered bounds (end exclusive) per bar.

    The components must already be allocated at the original resolution.
    Empty calendar bins are omitted; partial edge bins include selected data only.
    """
    ends = energy.index + pd.to_timedelta(durations.reindex(energy.index), unit="h")
    bounds = pd.DataFrame({"start": energy.index, "end": ends}, index=energy.index)
    if mode == "hourly":
        label = "1 hour" if durations.reindex(energy.index).eq(1).all() else "original timestep"
        return energy.copy(), bounds, label
    for rule, label in INTERVALS:
        if rule not in {"W-MON", "MS", "QS", "YS"}:
            if pd.Timedelta(rule) < pd.Timedelta(hours=float(durations.reindex(energy.index).max())):
                continue
        grouper = pd.Grouper(freq=rule, closed="left", label="left")
        groups = energy.groupby(grouper)
        present = groups.size().gt(0)
        if present.sum() <= COVERAGE_MAX_BARS:
            totals = groups.sum().loc[present]
            periods = bounds.groupby(grouper).agg({"start": "min", "end": "max"}).loc[present]
            return totals, periods, label
    raise ValueError("Demand coverage window is too long")
