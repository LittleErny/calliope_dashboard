import math
import dash
import numpy as np
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import dash_leaflet as dl

from Calliope_learning.visualizations.inputs_helper import InputsHelper
import pickle


class CityMapDashboard:
    # -----------------------------
    # Arrowhead scaling parameters
    # -----------------------------
    R_EARTH = 6371000.0  # meters
    ZOOM_REF = 6         # reference zoom level for arrowhead size
    L_REF_M = 25000      # length at ZOOM_REF (meters)
    W_REF_M = 18000      # width  at ZOOM_REF (meters)
    L_MIN_M, L_MAX_M = 4000, 80000
    W_MIN_M, W_MAX_M = 3000, 60000

    def __init__(self, input_helper: InputsHelper):
        self.input_helper = input_helper

        raw_coords = self.input_helper.get_loc_coords()  # [(name, lon, lat), ...]
        self.locations, self.longitudes, self.latitudes = [list(x) for x in zip(*raw_coords)]

        self.cities = {name: [lat, lon] for name, lon, lat in raw_coords}


        lines = self.input_helper.get_transmission_lines()  # [((name1, lon1, lat1), (name2, lon2, lat2)), ..]
        self.connections = []
        for line in lines:
            loc1, loc2 = line
            a_name, a_lon, a_lat = loc1
            b_name, b_lon, b_lat = loc2
            # Enforce existence in cities; InputsHelper is assumed consistent
            if a_name not in self.cities:
                self.cities[a_name] = [a_lat, a_lon]
            if b_name not in self.cities:
                self.cities[b_name] = [b_lat, b_lon]
            self.connections.append((a_name, b_name))

        # ---- Prebuild Leaflet components (markers, polylines, empty arrowheads) ----
        self.marker_components = [
            dl.Marker(
                id=f"marker-{city}",
                position=coords,
                children=[dl.Tooltip(city), dl.Popup([html.B(city)])]
            )
            for city, coords in self.cities.items()
        ]

        self.route_lines = [
            dl.Polyline(
                id=f"route-{a}-{b}",
                positions=[self.cities[a], self.cities[b]],
                color="red",
                weight=4,
                opacity=0.7,
                children=[dl.Tooltip(f"{a} → {b}")]
            )
            for a, b in self.connections
        ]

        self.arrowheads = [
            dl.Polygon(
                id=f"head-{a}-{b}",
                positions=[],  # will be filled by zoom callback
                color="red",
                fill=True,
                fillColor="red",
                fillOpacity=0.7,
                weight=2,
            )
            for a, b in self.connections
        ]

        # ---- Dash app ----
        self.app = dash.Dash(__name__, suppress_callback_exceptions=True)
        self.app.layout = self.layout

        # ---- Register callbacks ----
        self.register_callbacks()

    # -----------------------------
    # Geo helpers for arrowheads
    # -----------------------------
    @staticmethod
    def _deg2rad(x):
        return math.radians(x)

    @staticmethod
    def _rad2deg(x):
        return math.degrees(x)

    def destination_point(self, lat_deg, lon_deg, distance_m, bearing_deg):
        """Return [lat, lon] from (lat_deg, lon_deg) by distance_m at bearing_deg."""
        lat1 = self._deg2rad(lat_deg)
        lon1 = self._deg2rad(lon_deg)
        brng = self._deg2rad(bearing_deg)
        dr = distance_m / self.R_EARTH

        lat2 = math.asin(math.sin(lat1) * math.cos(dr) +
                         math.cos(lat1) * math.sin(dr) * math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(dr) * math.cos(lat1),
                                 math.cos(dr) - math.sin(lat1) * math.sin(lat2))
        # Normalize longitude to [-180, 180)
        return [self._rad2deg(lat2), (self._rad2deg(lon2) + 540) % 360 - 180]

    def initial_bearing_deg(self, a_name, b_name):
        """Initial bearing (deg) from city A to B in [0..360)."""
        lat1, lon1 = map(self._deg2rad, self.cities[a_name])
        lat2, lon2 = map(self._deg2rad, self.cities[b_name])
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        brng = self._rad2deg(math.atan2(y, x))
        return (brng + 360) % 360

    def arrowhead_triangle_at_b(self, a_name, b_name, length_m, width_m):
        """
        Build a small triangular arrowhead at destination B, pointing A -> B.
        Returns [tip(B), base_left, base_right] as [lat, lon] lists.
        """
        tip = self.cities[b_name]
        dir_ab = self.initial_bearing_deg(a_name, b_name)
        base_center = self.destination_point(tip[0], tip[1], length_m, (dir_ab + 180) % 360)
        left_bearing = (dir_ab + 90) % 360
        right_bearing = (dir_ab + 270) % 360
        base_left = self.destination_point(base_center[0], base_center[1], width_m / 2.0, left_bearing)
        base_right = self.destination_point(base_center[0], base_center[1], width_m / 2.0, right_bearing)
        return [tip, base_left, base_right]

    def head_sizes_for_zoom(self, zoom):
        """
        Choose length/width in meters so screen size stays roughly constant.
        Leaflet zoom steps ~factor 2; zoom up => fewer meters for same on-screen size.
        """
        z = zoom if zoom is not None else self.ZOOM_REF
        factor = 2 ** (self.ZOOM_REF - z)  # zoom up => factor down
        L = max(self.L_MIN_M, min(self.L_MAX_M, self.L_REF_M * factor))
        W = max(self.W_MIN_M, min(self.W_MAX_M, self.W_REF_M * factor))
        return L, W

    # -----------------------------
    # Layout
    # -----------------------------
    def layout(self):
        return html.Div(style={'display': 'flex', 'height': '100vh'}, children=[
            # Left: Leaflet map
            html.Div(style={'flex': '2', 'padding': '10px'}, children=[
                html.H1("German Cities Map"),
                # Selected city store to share across callbacks
                dcc.Store(id="selected-city", data=None),
                dl.Map(
                    id="map",
                    center=[51.17, 10.45],  # approx center of Germany; ToDo: calculate it automatically
                    zoom=6,
                    style={"width": "100%", "height": "600px"},
                    children=[
                        dl.TileLayer(),
                        dl.LayerGroup(id="map-layer")  # will be populated by initial callback
                    ]
                ),
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
        app = self.app  # alias

        # --- Initial map population: add markers, lines, and empty arrowheads ---
        @app.callback(
            Output('map-layer', 'children'),
            Input('map', 'id')  # dummy input to trigger initial render
        )
        def update_map(_):
            return self.marker_components + self.route_lines + self.arrowheads

        # --- Recompute arrowheads on zoom ---
        head_outputs = [Output(f"head-{a}-{b}", "positions") for a, b in self.connections]

        @app.callback(head_outputs, Input("map", "zoom"))
        def scale_arrowheads(zoom):
            L, W = self.head_sizes_for_zoom(zoom)
            positions_list = []
            for a, b in self.connections:
                tri = self.arrowhead_triangle_at_b(a, b, length_m=L, width_m=W)
                positions_list.append(tri)
            return positions_list

        # Build Inputs for clicks on markers, routes, and arrowheads
        marker_inputs = [Input(f"marker-{c}", "n_clicks") for c in self.cities.keys()]
        route_inputs = [Input(f"route-{a}-{b}", "n_clicks") for a, b in self.connections]
        head_inputs = [Input(f"head-{a}-{b}", "n_clicks") for a, b in self.connections]

        # --- Info panel update + remember selected city in Store ---
        @app.callback(
            [Output('info-panel', 'children'), Output('selected-city', 'data')],
            marker_inputs + route_inputs + head_inputs
        )
        def display_info(*_):
            ctx = dash.callback_context
            # Default (nothing clicked yet)
            default_panel = [
                html.H3("Location Info"),
                html.P("Click a city to see details here."),
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
                })
            ]

            print(ctx.triggered)
            if not ctx.triggered or ctx.triggered[0]['value'] is None:
                return default_panel, None

            trig_id = ctx.triggered[0]["prop_id"].split(".")[0]

            # We only open the detailed info when a city marker is clicked.
            if trig_id.startswith("marker-"):
                city_name = trig_id.replace("marker-", "")
                area = self.input_helper.get_location_area(city_name)
                carriers = self.input_helper.get_location_carriers(city_name)
                assert len(carriers) > 0

                return (
                    [
                        html.H3(f"{city_name}, Germany"),
                        html.P(f"Location area: {area}"),
                        html.Label("Carrier type:"),
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
                    ],
                    city_name  # store selected city for the charts callback
                )

            # If a route/arrow is clicked, keep default panel (no city context)
            return default_panel, None

        # --- Build the list of per-tech cards + separate Demand chart ---
        @app.callback(
            Output("techs-list", "children"),
            Input("carrier-dropdown", "value"),
            Input("selected-city", "data")
        )
        def update_techs_list(selected_carrier, selected_city):
            # print("Callback: ", selected_carrier, selected_city)
            if not selected_city or not selected_carrier:
                return []

            city_name = selected_city

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
            loc_techs = self.input_helper.get_location_techs(city_name, selected_carrier)  # [(loc_name, tech_name, carrier),]
            tech_names = sorted({x[1] for x in loc_techs})

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
                    yaxis_title="Energy (kWh)",
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
                    hovertemplate="%{y:.2f} kWh<extra>%{x}</extra>"
                ))
                fig_d = apply_layout(fig_d, f"Demand — {city_name} ({selected_carrier})")

                children.append(
                    html.Div(style=card_style, children=[
                        html.H4("Demand", style={"marginBottom": "6px"}),
                        dcc.Graph(figure=fig_d, style={"height": "240px", "width": "100%"})
                    ])
                )

            # Supply techs (one card per technology)
            for tech in tech_names:
                arr = supply_dict.get(f"{city_name}::{tech}")
                if arr is None:
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

                # Static details
                details_map = self.input_helper.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
                tech_children = []

                for key, value in details_map.items():
                    if key == "lifetime" and not math.isnan(value):
                        tech_children.append(html.Li(f"Lifetime: {value} years"))
                    if key == "energy_cap_max" and not math.isnan(value):
                        tech_children.append(html.Li(f"Maximum Energy Capacity: {value} kW"))
                    if key == "energy_con" and not math.isnan(value):
                        tech_children.append(html.Li(f"Energy Consumption: {value} kW"))
                    if key == "energy_eff" and not math.isnan(value):
                        tech_children.append(html.Li(f"Energy Efficiency: {value * 100}%"))
                    if key == "parasitic_eff" and not math.isnan(value):
                        tech_children.append(html.Li(f"Parasitic Efficiency: {value * 100}%"))
                    if key == "resource_area_max" and not math.isnan(value):
                        tech_children.append(html.Li(f"Maximum Resource Area: {value} m²"))
                    if key == "resource_eff" and not math.isnan(value):
                        tech_children.append(html.Li(f"Resource Efficiency: {value * 100}%"))

                details = html.Ul(children=tech_children)

                children.append(
                    html.Div(style=card_style, children=[
                        html.H4(tech, style={"marginBottom": "6px"}),
                        details,
                        dcc.Graph(figure=fig_s, style={"height": "240px", "width": "100%"})
                    ])
                )

            # Storage techs (details only)
            for tech in tech_names:
                if self.input_helper.tech_is_storage(tech):
                    details_map = self.input_helper.get_loc_tech_carrier_stats(city_name, tech, selected_carrier)
                    tech_children = []

                    for key, value in details_map.items():
                        if key == "lifetime" and not math.isnan(value):
                            tech_children.append(html.Li(f"Lifetime: {value} years"))
                        if key == "energy_cap_max" and not math.isnan(value):
                            tech_children.append(html.Li(f"Maximum Discharge Power: {value} kW"))
                        if key == "energy_con" and not math.isnan(value):
                            tech_children.append(html.Li(f"Energy Consumption: {value} kW"))
                        if key == "energy_eff" and not math.isnan(value):
                            tech_children.append(html.Li(f"Energy Efficiency: {value * 100}%"))
                        if key == "parasitic_eff" and not math.isnan(value):
                            tech_children.append(html.Li(f"Parasitic Efficiency: {value * 100}%"))
                        if key == "resource_area_max" and not math.isnan(value):
                            tech_children.append(html.Li(f"Maximum Resource Area: {value} m²"))
                        if key == "resource_eff" and not math.isnan(value):
                            tech_children.append(html.Li(f"Resource Efficiency: {value * 100}%"))
                        if key == "storage_cap_max" and not math.isnan(value):
                            tech_children.append(html.Li(f"Max Storage Capacity: {value} kWh"))

                    details = html.Ul(children=tech_children)
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
    pickle_file_path = '../german_model_inputs_with_transmissions.pkl'

    # Open the file in read-binary mode and load the inputs
    with open(pickle_file_path, 'rb') as f:
        loaded_inputs = pickle.load(f)

    helper = InputsHelper(loaded_inputs)
    dashboard = CityMapDashboard(helper)
    dashboard.run()
