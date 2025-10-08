import dash
import numpy as np
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
from Calliope_learning.visualizations.inputs_helper import InputsHelper
import pickle


class CityMapDashboard:
    def __init__(self, input_helper: InputsHelper):
        self.input_helper = input_helper
        loc_coords = input_helper.get_loc_coords()
        self.locations, self.longitudes, self.latitudes = zip(*loc_coords)

        # Initialize Dash app
        self.app = dash.Dash(__name__)

        # Tell Dash to call a function that returns the layout
        self.app.layout = self.layout

        # Register callbacks
        self.register_callbacks()

    def layout(self):
        """

        Returns
        -------

        """
        return html.Div(style={'display': 'flex', 'height': '100vh'}, children=[
            # Left: map
            html.Div(style={'flex': '2', 'padding': '10px'}, children=[
                html.H1("German Cities Map"),
                dcc.Graph(id='map-graph', style={'height': '600px'})
            ]),

            # Right: info panel (static placeholder)
            html.Div(id='info-panel', style={
                'flex': '1',
                'padding': '10px',
                'border-left': '1px solid #ccc',
                'backgroundColor': '#f9f9f9',
                'display': 'flex',
                'flexDirection': 'column',
                'height': '100%',

            }, children=[
                html.H3("Location Info"),
                html.P("Click a city to see details here."),

                # placeholder dropdown (invisible at start)
                dcc.Dropdown(
                    id="carrier-dropdown",
                    options=[],
                    value=None,
                    clearable=False,
                    style={"display": "none"}
                ),

                html.Div(id="techs-list", style={
                    "marginTop": "20px",
                    "overflowY": "auto",
                    "flex": "1"
                }, children=[
                    dcc.Graph(
                        id="timeseries-graph",
                        style={"height": "300px", "width": "100%"}  # force full width
                    )
                ]

                         ),
            ])
        ])

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
                textposition='top center'
            ))

            fig.update_layout(
                title="German Cities",
                map=dict(
                    bearing=0,
                    center=dict(  # approximately the center of Germany
                        lat=51.17,
                        lon=10.45
                    ),
                    pitch=0,
                    zoom=5.2
                ),
                mapbox_style='open-street-map',
                # mapbox_zoom=5,
                # mapbox_center={"lat": 51.1657, "lon": 10.4515},
                margin={"r": 0, "t": 50, "l": 0, "b": 0},  # small margin from above for the map title
                autosize=True
            )
            return fig

        # Info panel update
        @self.app.callback(
            Output('info-panel', 'children'),
            Input('map-graph', 'clickData')
        )
        def display_info(clickData):
            # Whenever we select some location on the map, this function is triggered

            if clickData:
                city_name = clickData['points'][0]['text']
                area = self.input_helper.get_location_area(city_name)
                carriers = self.input_helper.get_location_carriers(city_name)

                return [
                    html.H3(f"{city_name}, Germany"),
                    html.P(f"Location area: {area}"),
                    html.Label("Carrier type:"),
                    # visible dropdown when a city is selected
                    dcc.Dropdown(
                        id="carrier-dropdown",
                        options=[{"label": c, "value": c} for c in carriers],
                        value=carriers[0],
                        clearable=False
                    ),

                    # dcc.Graph(id="timeseries-graph", style={"height": "300px"}),  # new timeseries graph

                    html.Div(id="techs-list", style={
                        "marginTop": "20px",
                        "overflowY": "auto",
                        "flex": "1"
                    }, children=[
                        dcc.Graph(
                            id="timeseries-graph",
                            style={"height": "300px", "width": "100%"}  # force full width
                        )
                    ])
                ]
            else:
                # ensure the dropdown id always exists in the layout (hidden / empty)
                return [
                    html.H3("Location Info"),
                    html.P("Click a city to see details here."),
                    # placeholder dropdown — keeps the id in DOM so callbacks referencing it never fail
                    dcc.Dropdown(
                        id="carrier-dropdown",
                        options=[],  # no options when nothing is selected
                        value=None,
                        clearable=False,
                        style={"display": "none"}  # keep it invisible until a city is clicked
                    ),
                    html.Div(id="techs-list", style={
                        "marginTop": "20px",
                        "overflowY": "auto",
                        "flex": "1"
                    })
                ]

        # Tech list update
        @self.app.callback(
            Output("techs-list", "children"),
            Input("carrier-dropdown", "value"),
            Input("map-graph", "clickData")
        )
        def update_techs_list(selected_carrier, clickData):
            if not clickData or not selected_carrier:
                return []

            city_name = clickData['points'][0]['text']
            loc_techs = self.input_helper.get_location_techs(city_name,
                                                             selected_carrier)  # [(loc_name, tech_name, carrier),]

            techs_names = [x[1] for x in loc_techs]

            return [dcc.Graph(
                id="timeseries-graph",
                style={"height": "300px", "width": "100%"}  # force full width
            )] + [

                html.Div(style={
                    "border": "1px solid #ccc",
                    "borderRadius": "5px",
                    "padding": "10px",
                    "marginBottom": "10px",
                    "backgroundColor": "#fff"
                }, children=[
                    html.H4(t, style={"marginBottom": "5px"}),
                    html.Ul(children=[
                        html.Li("Type: Supply" if "PV" in t else "Storage"),
                        html.Li("Capacity: 100 MW"),
                        html.Li("Efficiency: 85%"),
                        html.Li("Lifetime: 20 years"),
                    ])
                ]) for t in techs_names
            ]

        @self.app.callback(
            Output("timeseries-graph", "figure"),
            Input("carrier-dropdown", "value"),
            Input("map-graph", "clickData")
        )
        def update_timeseries(selected_carrier, clickData):
            # print("update_timeseries", clickData, selected_carrier)
            if not clickData or not selected_carrier:
                # print("update_timeseries: no click data")
                return go.Figure()  # empty figure if nothing selected

            # print("update_timeseries: click data")
            city_name = clickData['points'][0]['text']

            # Load data
            demand_arrays = [-1 * i for i in self.input_helper.get_location_demand(city_name, selected_carrier)]
            supply_dict = self.input_helper.get_location_total_max_supply(city_name, selected_carrier)
            # print(supply_dict)
            print(demand_arrays)

            # Process demand
            if demand_arrays:
                total_demand = np.sum(np.vstack(demand_arrays), axis=0)
            else:
                # fallback in case no demand arrays
                total_demand = np.zeros_like(next(iter(supply_dict.values()))) if supply_dict else np.array([])

            # Create figure
            fig = go.Figure()
            if total_demand.size > 0:
                fig.add_trace(go.Scatter(
                    y=total_demand,
                    x=np.arange(len(total_demand)),
                    name="Demand",
                    line=dict(color='red'),
                    hovertemplate="%{y:.2f} MWh<extra>%{x}</extra>"
                ))

            # Add supply traces
            colors = ['blue', 'green', 'orange', 'purple', 'cyan']
            for i, (tech_name, supply_array) in enumerate(supply_dict.items()):
                fig.add_trace(go.Scatter(
                    y=supply_array,
                    x=np.arange(len(supply_array)),
                    name=f"Supply: {tech_name}",
                    line=dict(color=colors[i % len(colors)]),
                    hovertemplate="%{y:.2f} MWh<extra>%{x}</extra>"
                ))

            fig.update_layout(
                title=f"Energy Time Series - {city_name} ({selected_carrier})",
                xaxis_title="Time step",
                yaxis_title="Energy (MWh)",
                hovermode="x unified",
                legend=dict(
                    orientation="h",  # horizontal legend
                    yanchor="top",  # attaching to the top border of legend
                    y=-0.4,  # put it under the graph
                    xanchor="center",  # and center it
                    x=0.5
                ),
                margin=dict(b=100)  # add some space below for the legend
            )

            return fig

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
