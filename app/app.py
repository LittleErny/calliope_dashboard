from __future__ import annotations

from dash import Dash, html

from app import app_data
from app.callbacks.common import layout_for_tab, register_common_callbacks
from app.callbacks.inputs import register_inputs_callbacks
from app.callbacks.operate import register_operate_callbacks
from app.callbacks.planning import register_planning_callbacks
from app.layouts.common import layout_header, layout_root, layout_tabs

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

app.layout = layout_root(
    [
        layout_header(),
        layout_tabs(),
        html.Div(
            layout_for_tab(app_data.DEFAULT_TAB),
            id="page-content",
            style={"padding": "14px 16px", "flex": "1 1 auto"},
        ),
    ]
)

register_common_callbacks(app)
register_inputs_callbacks(app)
register_planning_callbacks(app)
register_operate_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
