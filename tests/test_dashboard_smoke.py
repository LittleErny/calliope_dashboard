from __future__ import annotations


def test_dashboard_builds_layout_and_callbacks() -> None:
    from app.app import app

    assert app.layout is not None
    assert "applied-time.data" in app.callback_map
    # No Python chart/map callback should receive the unconfirmed slider.
    for config in app.callback_map.values():
        if "callback" in config:
            assert all(item["id"] != "rs-time" for item in config["inputs"])
