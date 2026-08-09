from __future__ import annotations

import sys
from pathlib import Path

from dash import Dash, html

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from layouts.common import layout_header, layout_root, layout_tabs
from callbacks.common import register_common_callbacks
from callbacks.inputs import register_inputs_callbacks
from callbacks.planning import register_planning_callbacks
from callbacks.operate import register_operate_callbacks

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

app.layout = layout_root(
    [
        layout_header(),
        layout_tabs(),
        html.Div(id="page-content", style={"padding": "14px 16px", "flex": "1 1 auto"}),
    ]
)

register_common_callbacks(app)
register_inputs_callbacks(app)
register_planning_callbacks(app)
register_operate_callbacks(app)

if __name__ == "__main__":
    MIN_VERSION = (3, 10)
    print(sys.version_info)

    app.run(debug=True)
