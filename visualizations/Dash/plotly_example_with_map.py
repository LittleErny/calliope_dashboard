import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# Germany city data
cities = ['Berlin', 'Hamburg', 'Munich', 'Cologne', 'Frankfurt']
latitudes = [52.5200, 53.5511, 48.1351, 50.9375, 50.1109]
longitudes = [13.4050, 9.9937, 11.5820, 6.9603, 8.6821]
populations = [3769000, 1841000, 1472000, 1086000, 763000]
states = ['Berlin', 'Hamburg', 'Bavaria', 'North Rhine-Westphalia', 'Hesse']

# Initialize Dash app
app = dash.Dash(__name__)

# App layout: map on left, info panel on right
app.layout = html.Div(style={'display': 'flex'}, children=[
    html.Div(style={'flex': '2', 'padding': '10px'}, children=[
        html.H1("German Cities Map"),
        dcc.Graph(
            id='map-graph',
            style={'height': '600px'}  # fixed height to prevent jumping
        )

    ]),
    html.Div(id='info-panel', style={
        'flex': '1',
        'padding': '10px',
        'border-left': '1px solid #ccc',
        'minHeight': '500px',
        'backgroundColor': '#f9f9f9'
    }, children=[
        html.H3("Location Info"),
        html.P("Click a city to see details here.")
    ])
])

# Callback to generate the map (no dropdown input needed)
@app.callback(
    Output('map-graph', 'figure'),
    Input('map-graph', 'id')  # dummy input to trigger initial render
)
def update_map(_):
    # Always show all cities
    fig = go.Figure(go.Scattermapbox(
        mode='markers+text',
        lon=longitudes,
        lat=latitudes,
        text=cities,
        marker=dict(size=12, color='blue'),
        textposition='top center',
        customdata=[{'population': pop, 'state': st} for pop, st in zip(populations, states)]
    ))

    fig.update_layout(
        title="German Cities",
        mapbox_style='open-street-map',
        mapbox_zoom=5,
        mapbox_center={"lat": 51.1657, "lon": 10.4515},  # center Germany
        margin={"r":0,"t":50,"l":0,"b":0},
        autosize=True
    )

    return fig


# Callback to update the info panel based on click
@app.callback(
    Output('info-panel', 'children'),
    Input('map-graph', 'clickData')
)
def display_info(clickData):
    if clickData:
        point_data = clickData['points'][0]
        city_name = point_data['text']
        population = point_data['customdata']['population']
        state = point_data['customdata']['state']
        return [
            html.H3(f"{city_name}, {state}"),
            html.P(f"Population: {population:,}")  # formatted with commas
        ]
    else:
        return [
            html.H3("Location Info"),
            html.P("Click a city to see details here.")
        ]

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
