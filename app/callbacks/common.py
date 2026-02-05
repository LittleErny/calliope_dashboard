from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from dash import Input, Output, html

import app_data
from layouts.inputs import layout_inputs
from layouts.planning import layout_results_planning
from layouts.operate import layout_results_operate


def register_common_callbacks(app):
    @app.callback(
        Output("page-content", "children"),
        Input("tabs-mode", "value"),
    )
    def render_page(tab_value: str):
        if tab_value == "inputs":
            return layout_inputs()
        if tab_value == "results_planning":
            return layout_results_planning()
        if tab_value == "results_operate":
            return layout_results_operate()
        return html.Div("Unknown mode")

    @app.callback(
        Output("time-label", "children"),
        Input("rs-time", "value"),
    )
    def update_time_label(rng: List[int]):
        i0, i1 = int(rng[0]), int(rng[1])
        n_label = len(app_data.INPUT_TIMESTEPS) if len(app_data.INPUT_TIMESTEPS) else len(app_data.TIME_INDEX)
        i0 = max(0, min(n_label - 1, i0))
        i1 = max(0, min(n_label - 1, i1))
        if i1 < i0:
            i0, i1 = i1, i0
        if len(app_data.INPUT_TIMESTEPS):
            t0 = app_data.INPUT_TIMESTEPS[i0]
            t1 = app_data.INPUT_TIMESTEPS[i1]
        else:
            t0 = app_data.TIME_INDEX[i0]
            t1 = app_data.TIME_INDEX[i1]

        def fmt_ts(ts):
            if isinstance(ts, (pd.Timestamp, np.datetime64)):
                return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M")
            return str(ts)

        return f"{fmt_ts(t0)} → {fmt_ts(t1)}  (idx {i0}-{i1})"
