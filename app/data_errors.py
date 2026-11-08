"""Dash error handling that clears affected values and exposes a useful status."""

import logging

from dash import ctx, html, no_update, set_props

from app.figures import empty_figure
from helpers.errors import DataUnavailable


def handle_data_error(error):
    logging.getLogger("calliope_dashboard.data").exception("Dashboard callback failed")
    outputs = ctx.outputs_list
    output_list = outputs if isinstance(outputs, list) else [outputs]
    is_operate = any(
        any(part in str(output["id"]) for part in ("operate-", "coverage-"))
        for output in output_list
    )
    detail = str(error) if isinstance(error, DataUnavailable) else "Could not read or calculate the selected data. See the server log."
    message = f"Data unavailable. {detail} Affected results have been cleared."
    if is_operate:
        message += " Operate results may not have been calculated or included in this export. Run an Operate optimisation and load its results."
    set_props("data-error-message", {"children": message})
    set_props("data-error-banner", {"style": {"display": "flex"}})

    def replacement(output):
        prop = output["property"]
        if prop == "figure":
            return empty_figure("Data unavailable — see the error message above")
        if prop in {"data", "columns"} and "table" in str(output["id"]):
            return []
        if prop == "children":
            if "map-layer" in str(output["id"]):
                return []
            return html.Div(message, role="alert", className="data-unavailable")
        return no_update

    return [replacement(o) for o in outputs] if isinstance(outputs, list) else replacement(outputs)
