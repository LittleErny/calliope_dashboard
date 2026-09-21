from __future__ import annotations


def test_dashboard_builds_layout_and_callbacks() -> None:
    from app.app import app

    assert app.layout is not None
    assert len(app.callback_map) == 15
