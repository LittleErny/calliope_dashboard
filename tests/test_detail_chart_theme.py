"""Applying the shared chart theme must not change plotted measurements."""
import plotly.graph_objects as go

from app.figures import style_detail_chart


def test_chart_theme_preserves_values_and_hover_details():
    fig = go.Figure(go.Bar(x=["a", "b"], y=[1.25, -2.5], customdata=[10, 20],
                           hovertemplate="%{y} (%{customdata})<extra></extra>"))
    before = fig.to_plotly_json()["data"]
    style_detail_chart(fig)
    assert fig.to_plotly_json()["data"] == before
    assert fig.layout.paper_bgcolor == "white"
