import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from Calliope_learning.visualizations.inputs_helper import InputsHelper
import pickle


class CityMapDashboard:
    def __init__(self, input_helper: InputsHelper):
        # Germany city data
        # self.cities = input_helper.get_locations()
        self.input_helper = input_helper
        loc_coords = input_helper.get_loc_coords()
        self.locations, self.longitudes, self.latitudes = zip(*loc_coords)

        # Initialize Dash app
        self.app = dash.Dash(__name__)

        # Set layout
        self.app.layout = html.Div(style={'display': 'flex'}, children=[
            html.Div(style={'flex': '2', 'padding': '10px'}, children=[
                html.H1("German Cities Map"),
                dcc.Graph(id='map-graph', style={'height': '600px'})
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

        # Register callbacks
        self.register_callbacks()

    def register_callbacks(self):
        # Map update
        @self.app.callback(
            Output('map-graph', 'figure'),
            Input('map-graph', 'id')  # dummy input to trigger initial render
        )
        def update_map(_):
            fig = go.Figure(go.Scattermap(
                mode='markers+text',
                lon=self.longitudes,
                lat=self.latitudes,
                text=self.locations,
                marker=dict(size=20, color='blue'),
                textposition='top center',
                # customdata=[{'population': 2, 'state': 1} for _ in self.locations]
            ))

            fig.update_layout(
                title="German Cities",
                map=dict(
                    bearing=0,
                    center=dict(
                        lat=51.17,
                        lon=10.45
                    ),
                    pitch=0,
                    zoom=5.2
                ),
                mapbox_style='open-street-map',
                mapbox_zoom=5,
                mapbox_center={"lat": 51.1657, "lon": 10.4515},
                margin={"r": 0, "t": 50, "l": 0, "b": 0},
                autosize=True
            )
            return fig

        # Info panel update
        @self.app.callback(
            Output('info-panel', 'children'),
            Input('map-graph', 'clickData')
        )
        def display_info(clickData):
            if clickData:
                print(clickData)
                point_data = clickData['points'][0]
                city_name = point_data['text']

                # Get location area
                area = self.input_helper.get_location_area(city_name)

                # Get city techs
                techs = self.input_helper.get_location_techs(city_name)
                # print(techs)

                # Here I want to render a dropdown men

                # Return the elements to display
                return [
                    html.H3(f"{city_name}, Germany"),
                    html.P(f"Location area: {area}"),
                ]
            else:
                return [
                    html.H3("Location Info"),
                    html.P("Click a city to see details here.")
                ]

    def run(self):
        self.app.run(debug=True)


# Run the dashboard
if __name__ == '__main__':
    # Specify the path to the pickle file
    pickle_file_path = '../german_model_inputs.pkl'

    # Open the file in read-binary mode and load the inputs
    with open(pickle_file_path, 'rb') as f:
        loaded_inputs = pickle.load(f)

    helper = InputsHelper(loaded_inputs)
    dashboard = CityMapDashboard(helper)
    dashboard.run()
