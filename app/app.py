from __future__ import annotations

from dash import Dash, html

from app import app_data
from app.callbacks.common import layout_for_tab, register_common_callbacks
from app.callbacks.inputs import register_inputs_callbacks
from app.callbacks.operate import register_operate_callbacks
from app.callbacks.planning import register_planning_callbacks
from app.layouts.common import layout_header, layout_root, layout_tabs
from app.data_errors import handle_data_error
from app.costs_view import register_cost_callbacks

app = Dash(__name__, suppress_callback_exceptions=True, on_error=handle_data_error)
server = app.server

app.layout = layout_root(
    [
        html.Div([layout_header(), layout_tabs()], className="dashboard-shell"),
        html.Div([
            html.Span(id="data-error-message", role="alert"),
            html.Button("Dismiss", id="dismiss-data-error", n_clicks=0),
        ], id="data-error-banner", className="data-error-banner", style={"display": "none"}),
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
register_cost_callbacks(app)
register_operate_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
