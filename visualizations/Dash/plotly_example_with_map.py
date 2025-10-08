import dash
import numpy as np
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from Calliope_learning.visualizations.inputs_helper import InputsHelper
import pickle


class CityMapDashboard:
    """
    Split the single combined time series into multiple graphs:
      - One graph for Demand
      - One graph per technology (e.g., PV, WIND, etc.)
    All graphs appear stacked in the scrollable right panel, each inside its own card.
    """

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

    # -----------------------------
    # Layout
    # -----------------------------
    def layout(self):
        return html.Div(style={'display': 'flex', 'height': '100vh'}, children=[
            # Left: map
            html.Div(style={'flex': '2', 'padding': '10px'}, children=[
                html.H1("German Cities Map"),
                dcc.Graph(id='map-graph', style={'height': '600px'})
            ]),

            # Right: info panel
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

                # Keep dropdown ID always present; hidden until a city is selected
                dcc.Dropdown(
                    id="carrier-dropdown",
                    options=[],
                    value=None,
                    clearable=False,
                    style={"display": "none"}
                ),

                # Scrollable area with per-tech cards (each includes its own graph)
                html.Div(id="techs-list", style={
                    "marginTop": "20px",
                    "overflowY": "auto",
                    "flex": "1"
                })
            ])
        ])

    # -----------------------------
    # Callbacks
    # -----------------------------
    def register_callbacks(self):
        # Map update (initial render)
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
                assert len(carriers) > 0
                return [
                    html.H3(f"{city_name}, Germany"),
                    html.P(f"Location area: {area}"),
                    html.Label("Carrier type:"),
                    # visible dropdown when a city is selected
                    dcc.Dropdown(
                        id="carrier-dropdown",
                        options=[{"label": c, "value": c} for c in carriers],
                        value=carriers[0],
                        clearable=False,
                    ),
                    html.Div(id="techs-list", style={
                        "marginTop": "20px",
                        "overflowY": "auto",
                        "flex": "1"
                    })
                ]
            else:
                # ensure the dropdown id always exists in the layout (hidden / empty)
                return [
                    html.H3("Location Info"),
                    html.P("Click a city to see details here."),
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

        # Build the list of per-tech cards + a separate Demand chart in the beginning
        @self.app.callback(
            Output("techs-list", "children"),
            Input("carrier-dropdown", "value"),
            Input("map-graph", "clickData")
        )
        def update_techs_list(selected_carrier, clickData):
            if not clickData or not selected_carrier:
                return []

            city_name = clickData['points'][0]['text']

            # ---------------- Demand ----------------
            demand_arrays = [
                -1 * np.array(arr) for arr in self.input_helper.get_location_demand(city_name, selected_carrier)
            ]  # negative to show as consumption, as in your original

            total_demand = None
            if len(demand_arrays) > 0:
                total_demand = np.sum(np.vstack(demand_arrays), axis=0)

            # ---------------- Supply ----------------
            # {tech_name: np.array([...])}
            supply_dict = self.input_helper.get_location_total_max_supply(city_name, selected_carrier)

            # Discover technologies present at this location for the carrier
            loc_techs = self.input_helper.get_location_techs(city_name,
                                                             selected_carrier)  # [(loc_name, tech_name, carrier),]
            tech_names = sorted({x[1] for x in loc_techs})

            print(supply_dict, loc_techs, tech_names, sep='\n\n---\n\n')

            # Consistent card style
            card_style = {
                "border": "1px solid #ccc",
                "borderRadius": "6px",
                "padding": "10px",
                "marginBottom": "12px",
                "backgroundColor": "#fff",
                "boxShadow": "0 1px 2px rgba(0,0,0,0.06)"
            }

            # Consistent figure layout tweaks
            def apply_layout(fig: go.Figure, title: str):
                fig.update_layout(
                    title=title,
                    xaxis_title="Time step",
                    yaxis_title="Energy (MWh)",
                    hovermode="x unified",
                    showlegend=False,
                    margin=dict(t=40, r=10, b=20, l=40),
                )
                fig.update_xaxes(showgrid=True, gridwidth=1, griddash="dot")
                fig.update_yaxes(showgrid=True, gridwidth=1, griddash="dot")
                return fig

            children = []

            # Demand card (if available)
            if total_demand is not None:
                fig_d = go.Figure()
                fig_d.add_trace(go.Scatter(
                    y=total_demand,
                    x=np.arange(len(total_demand)),
                    name="Demand",
                    line=dict(width=2),
                    hovertemplate="%{y:.2f} MWh<extra>%{x}</extra>"
                ))
                fig_d = apply_layout(fig_d, f"Demand — {city_name} ({selected_carrier})")

                children.append(
                    html.Div(style=card_style, children=[
                        html.H4("Demand", style={"marginBottom": "6px"}),
                        dcc.Graph(figure=fig_d, style={"height": "240px", "width": "100%"})
                    ])
                )

            # One card per technology
            for tech in tech_names:
                arr = supply_dict.get(f"{city_name}::{tech}")
                if arr is None:
                    # Skip technologies not present in the aggregated supply
                    print("skipped", tech)
                    continue

                fig_s = go.Figure()
                fig_s.add_trace(go.Scatter(
                    y=np.array(arr),
                    x=np.arange(len(arr)),
                    name=f"{tech} Supply",
                    line=dict(width=2),
                    hovertemplate="%{y:.2f} MWh<extra>%{x}</extra>"
                ))
                fig_s = apply_layout(fig_s, f"{tech} — {city_name} ({selected_carrier})")

                # Simple static details (kept from your original UI)
                details = html.Ul(children=[
                    html.Li("Type: Supply"),
                    html.Li("Capacity: XXX MW"),
                    html.Li("Efficiency: XX%"),
                    html.Li("Lifetime: XX years"),
                ])

                children.append(
                    html.Div(style=card_style, children=[
                        html.H4(tech, style={"marginBottom": "6px"}),
                        details,
                        dcc.Graph(figure=fig_s, style={"height": "240px", "width": "100%"})
                    ])
                )

            for tech in tech_names:
                if self.input_helper.tech_is_storage(tech):
                    details = html.Ul(children=[
                        html.Li("Type: Storage"),
                        html.Li("Capacity: XXXX MW"),
                        html.Li("Efficiency: XX%"),
                        html.Li("Lifetime: XX years"),
                    ])
                    children.append(
                        html.Div(style=card_style, children=[
                            html.H4(tech, style={"marginBottom": "6px"}),
                            details
                        ])
                    )

            return children

    def run(self):
        self.app.run(debug=True)


# ---------------
# Run the dashboard
# ---------------
if __name__ == '__main__':
    # Specify the path to the pickle file
    pickle_file_path = '../german_model_inputs.pkl'

    # Open the file in read-binary mode and load the inputs
    with open(pickle_file_path, 'rb') as f:
        loaded_inputs = pickle.load(f)

    helper = InputsHelper(loaded_inputs)
    dashboard = CityMapDashboard(helper)
    dashboard.run()
