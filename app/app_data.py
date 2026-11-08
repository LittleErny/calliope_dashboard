from __future__ import annotations

import math
import os
import json
from types import SimpleNamespace
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import xarray as xr
from dash.exceptions import PreventUpdate

from helpers.inputs_helper import InputsHelper
from helpers.operate_results_helper import OperateResultsHelper
from helpers.results_helper import ALL_LOCATIONS, ResultsHelper
from helpers.carriers import select_carrier

# -----------------------------
# Paths & loaders
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "models" / "1_german_scale"
MODEL_DIR = Path(os.environ.get("CALLIOPE_DASHBOARD_MODEL_DIR", DEFAULT_MODEL_DIR)).expanduser().resolve()

PLANNING_PATH = MODEL_DIR / "planning.nc"
OPERATE_PATH = MODEL_DIR / "operate.nc"

_VALID_DEFAULT_TABS = {"inputs", "results_planning", "results_operate"}
DEFAULT_TAB = os.environ.get("CALLIOPE_DASHBOARD_DEFAULT_TAB", "inputs")
if DEFAULT_TAB not in _VALID_DEFAULT_TABS:
    DEFAULT_TAB = "inputs"


def _load_netcdf_group(path: Path, group: str) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Calliope NetCDF file not found: {path}")
    with xr.open_dataset(path, group=group, engine="h5netcdf") as dataset:
        return dataset.load()


def _read_metadata_value(metadata: xr.Dataset, section: str, key: str) -> Optional[str]:
    """Read one scalar from a YAML string stored in Calliope's attrs group."""
    raw_value = metadata.attrs.get(section)
    if not isinstance(raw_value, str):
        return None
    for raw_line in raw_value.splitlines():
        line = raw_line.strip()
        if line.startswith(f"{key}:"):
            value = line.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


# -----------------------------
# Real Inputs data (Calliope)
# -----------------------------

LOADED_INPUTS = _load_netcdf_group(PLANNING_PATH, "inputs")
LOADED_METADATA = _load_netcdf_group(PLANNING_PATH, "attrs")
CALLIOPE_VERSION = _read_metadata_value(
    LOADED_METADATA, "runtime", "calliope_version_initialised"
)
LOADED_INPUTS.attrs["calliope_version"] = CALLIOPE_VERSION

INPUT_HELPER = InputsHelper(LOADED_INPUTS)

INPUT_RAW_COORDS = INPUT_HELPER.get_loc_coords()  # [(name, lon, lat), ...]
if INPUT_RAW_COORDS:
    INPUT_LOCATIONS, INPUT_LONGITUDES, INPUT_LATITUDES = [
        list(values) for values in zip(*INPUT_RAW_COORDS)
    ]
else:
    # Coordinates are optional in Calliope. Keep non-map dashboard views usable
    # for models such as the THD case study, which defines no node coordinates.
    INPUT_LOCATIONS = INPUT_HELPER.get_locations()
    INPUT_LONGITUDES = []
    INPUT_LATITUDES = []

INPUT_CITIES = {name: [lat, lon] for name, lon, lat in INPUT_RAW_COORDS}

def _compute_map_center() -> List[float]:
    if not INPUT_LATITUDES or not INPUT_LONGITUDES:
        return [51.17, 10.45]
    avg_lat = float(sum(INPUT_LATITUDES)) / float(len(INPUT_LATITUDES))
    avg_lon = float(sum(INPUT_LONGITUDES)) / float(len(INPUT_LONGITUDES))
    return [avg_lat, avg_lon]


MAP_CENTER = _compute_map_center()
# Fit country-scale and campus-scale models without opening inside one city.
_coordinate_span = max(
    max(INPUT_LATITUDES) - min(INPUT_LATITUDES),
    max(INPUT_LONGITUDES) - min(INPUT_LONGITUDES),
) if INPUT_RAW_COORDS else 0
MAP_ZOOM_DEFAULT = max(2, min(15, int(math.log2(360 / max(_coordinate_span, 0.005))) + 1)) if INPUT_RAW_COORDS else 6

INPUT_CONNECTIONS = []
for line in INPUT_HELPER.get_transmission_lines():
    loc1, loc2 = line
    a_name, a_lon, a_lat = loc1
    b_name, b_lon, b_lat = loc2
    if a_name not in INPUT_CITIES:
        INPUT_CITIES[a_name] = [a_lat, a_lon]
    if b_name not in INPUT_CITIES:
        INPUT_CITIES[b_name] = [b_lat, b_lon]
    INPUT_CONNECTIONS.append((a_name, b_name))

INPUT_CARRIERS = sorted({c for loc in INPUT_LOCATIONS for c in INPUT_HELPER.get_location_carriers(loc)})
INPUT_TIMESTEPS = INPUT_HELPER.get_timesteps_datetime()
INPUT_T = len(INPUT_TIMESTEPS)

# -----------------------------
# Real Results data (Calliope)
# -----------------------------

LOADED_RESULTS = _load_netcdf_group(PLANNING_PATH, "results")
LOADED_RESULTS.attrs["calliope_version"] = CALLIOPE_VERSION

RESULTS_HELPER = ResultsHelper(LOADED_RESULTS, LOADED_INPUTS)

RESULTS_SCENARIOS = RESULTS_HELPER.get_scenarios()
SCENARIOS = RESULTS_SCENARIOS if RESULTS_SCENARIOS else []

RESULTS_TIMESTEPS = RESULTS_HELPER.get_timesteps_datetime()
if len(RESULTS_TIMESTEPS):
    TIME_INDEX = pd.DatetimeIndex(RESULTS_TIMESTEPS)
elif len(INPUT_TIMESTEPS):
    TIME_INDEX = pd.DatetimeIndex(INPUT_TIMESTEPS)
else:
    TIME_INDEX = pd.DatetimeIndex([])
T = len(TIME_INDEX)

PLAN_LOCATIONS = RESULTS_HELPER.get_locations()
PLAN_LOCATION_OPTIONS = [
    {"label": "All locations", "value": ALL_LOCATIONS},
    *({"label": location, "value": location} for location in PLAN_LOCATIONS),
]
PLAN_TECHS = RESULTS_HELPER.get_technologies()
PLAN_CARRIERS = RESULTS_HELPER.get_carriers()

CARRIER_OPTIONS = PLAN_CARRIERS or INPUT_CARRIERS
DEFAULT_CARRIER = CARRIER_OPTIONS[0] if CARRIER_OPTIONS else None

# -----------------------------
# Real Results data (Operate mode)
# -----------------------------

LOADED_OPERATE_RESULTS = _load_netcdf_group(OPERATE_PATH, "results")
LOADED_OPERATE_RESULTS.attrs["calliope_version"] = CALLIOPE_VERSION
LOADED_OPERATE_INPUTS = _load_netcdf_group(OPERATE_PATH, "inputs")
LOADED_OPERATE_INPUTS.attrs["calliope_version"] = CALLIOPE_VERSION

OPERATE_HELPER = OperateResultsHelper(LOADED_OPERATE_RESULTS, LOADED_OPERATE_INPUTS)
OPERATE_TIMESTEPS = OPERATE_HELPER.get_timesteps_datetime()
OPERATE_T = len(OPERATE_TIMESTEPS)
OPERATE_CARRIERS = OPERATE_HELPER.get_carriers()
OPERATE_CONNECTIONS = OPERATE_HELPER.get_physical_lines()

# Each callback selects a bundle explicitly; changing a dropdown never mutates
# process-wide model data used by another browser session.
_BUNDLE_NAMES = [
    "INPUT_HELPER", "RESULTS_HELPER", "OPERATE_HELPER", "INPUT_TIMESTEPS",
    "INPUT_T", "TIME_INDEX", "T", "OPERATE_TIMESTEPS", "OPERATE_T",
    "LOADED_INPUTS", "LOADED_RESULTS", "LOADED_OPERATE_INPUTS", "LOADED_OPERATE_RESULTS",
]
SCENARIO_DATA = {"default": SimpleNamespace(**{name: globals()[name] for name in _BUNDLE_NAMES})}
SCENARIO_OPTIONS = [{"label": "Default", "value": "default"}]
DEFAULT_SCENARIO = "default"
_manifest_path = MODEL_DIR / "dashboard_scenarios.json"
if _manifest_path.is_file():
    _manifest = json.loads(_manifest_path.read_text())
    SCENARIO_OPTIONS = []
    for entry in _manifest["scenarios"]:
        scenario_id = entry["id"]
        SCENARIO_OPTIONS.append({"label": entry["label"], "value": scenario_id})
        if scenario_id == "default":
            continue
        planning_path = MODEL_DIR / entry["planning"]
        operate_path = MODEL_DIR / entry["operate"]
        inputs = _load_netcdf_group(planning_path, "inputs")
        results = _load_netcdf_group(planning_path, "results")
        operate_inputs = _load_netcdf_group(operate_path, "inputs")
        operate_results = _load_netcdf_group(operate_path, "results")
        for dataset in (inputs, results, operate_inputs, operate_results):
            dataset.attrs["calliope_version"] = CALLIOPE_VERSION
        # Shared controls/map IDs require the same nodes, geography and time
        # axis. Investment scenarios may enable different techs and carriers.
        for reference, candidate in [(LOADED_INPUTS, inputs), (LOADED_OPERATE_INPUTS, operate_inputs)]:
            for coordinate in ("nodes", "timesteps"):
                if not reference[coordinate].equals(candidate[coordinate]):
                    raise ValueError(f"Scenario {scenario_id} has incompatible {coordinate}")
            for coordinate in ("latitude", "longitude"):
                if (coordinate in reference) != (coordinate in candidate) or (
                    coordinate in reference and not reference[coordinate].equals(candidate[coordinate])
                ):
                    raise ValueError(f"Scenario {scenario_id} has incompatible {coordinate}")
        if InputsHelper(inputs).get_transmission_lines() != INPUT_HELPER.get_transmission_lines():
            raise ValueError(f"Scenario {scenario_id} has incompatible map connections")
        values = {name: globals()[name] for name in _BUNDLE_NAMES}
        values.update(
            INPUT_HELPER=InputsHelper(inputs), RESULTS_HELPER=ResultsHelper(results, inputs),
            OPERATE_HELPER=OperateResultsHelper(operate_results, operate_inputs),
            LOADED_INPUTS=inputs, LOADED_RESULTS=results,
            LOADED_OPERATE_INPUTS=operate_inputs, LOADED_OPERATE_RESULTS=operate_results,
        )
        SCENARIO_DATA[scenario_id] = SimpleNamespace(**values)
    DEFAULT_SCENARIO = _manifest.get("default", "default")
SCENARIOS = list(SCENARIO_DATA)


_CARRIER_BUNDLES = {}


def get_scenario(scenario_id: str | None = None, carrier: str | None = None):
    """Return one immutable selection of inputs/results and its cached helpers."""
    scenario_id = scenario_id or DEFAULT_SCENARIO
    bundle = SCENARIO_DATA[scenario_id]
    if carrier is None:
        return bundle
    if carrier not in bundle.LOADED_INPUTS.carriers.values:
        # A scenario switch can arrive before the carrier selector updates.
        # Wait for its valid new value instead of selecting unavailable data
        # or briefly showing another carrier under the stale label.
        raise PreventUpdate
    key = (scenario_id, carrier)
    if key not in _CARRIER_BUNDLES:
        inputs, results = select_carrier(bundle.LOADED_INPUTS, bundle.LOADED_RESULTS, carrier)
        operate_inputs, operate_results = select_carrier(bundle.LOADED_OPERATE_INPUTS, bundle.LOADED_OPERATE_RESULTS, carrier)
        values = vars(bundle).copy()
        values.update(
            INPUT_HELPER=InputsHelper(inputs), RESULTS_HELPER=bundle.RESULTS_HELPER.for_carrier(carrier),
            OPERATE_HELPER=bundle.OPERATE_HELPER.for_carrier(carrier),
            LOADED_INPUTS=inputs, LOADED_RESULTS=results,
            LOADED_OPERATE_INPUTS=operate_inputs, LOADED_OPERATE_RESULTS=operate_results,
        )
        _CARRIER_BUNDLES[key] = SimpleNamespace(**values)
    return _CARRIER_BUNDLES[key]

# -----------------------------
# Model metadata
# -----------------------------

MODEL_NAME = _read_metadata_value(LOADED_METADATA, "config", "name")


def get_model_name() -> Optional[str]:
    return MODEL_NAME

# -----------------------------
# Map geometry helpers shared across tabs
# -----------------------------

R_EARTH = 6371000.0
ZOOM_REF = 6
L_REF_M = 30000
W_REF_M = 22000
L_MAX_M = 80000
W_MAX_M = 60000


def _deg2rad(x: float) -> float:
    return math.radians(x)


def _rad2deg(x: float) -> float:
    return math.degrees(x)


def destination_point(lat_deg: float, lon_deg: float, distance_m: float, bearing_deg: float) -> List[float]:
    """Return [lat, lon] from (lat_deg, lon_deg) by distance_m at bearing_deg."""
    lat1 = _deg2rad(lat_deg)
    lon1 = _deg2rad(lon_deg)
    brng = _deg2rad(bearing_deg)
    dr = distance_m / R_EARTH

    lat2 = math.asin(math.sin(lat1) * math.cos(dr) +
                     math.cos(lat1) * math.sin(dr) * math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(dr) * math.cos(lat1),
                             math.cos(dr) - math.sin(lat1) * math.sin(lat2))
    return [_rad2deg(lat2), (_rad2deg(lon2) + 540) % 360 - 180]


def initial_bearing_deg(a: List[float], b: List[float]) -> float:
    """Return initial bearing in degrees from point A to point B."""
    lat1, lon1 = map(_deg2rad, a)
    lat2, lon2 = map(_deg2rad, b)
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    brng = _rad2deg(math.atan2(y, x))
    return (brng + 360) % 360


def head_sizes_for_zoom(zoom: float | None) -> Tuple[float, float]:
    """Choose arrowhead length/width so the screen size stays roughly constant."""
    z = zoom if zoom is not None else ZOOM_REF
    factor = 2 ** (ZOOM_REF - z)
    l_val = min(L_MAX_M, L_REF_M * factor)
    w_val = min(W_MAX_M, W_REF_M * factor)
    return l_val, w_val


def arrowhead_triangle_at_b(a: List[float], b: List[float], length_m: float, width_m: float,
                            zoom: float | None = None, marker: str = "circle") -> List[List[float]]:
    """Place the head at the receiving end, just outside its marker.

    Work in Leaflet's Mercator plane so the head stays on the straight line.
    Screen-pixel clearance keeps it beside the marker when zoom changes.
    """
    world = 256 * 2 ** (ZOOM_REF if zoom is None else zoom)

    def project(point):
        lat = math.radians(max(-85.0511, min(85.0511, point[0])))
        return ((point[1] + 180) / 360 * world,
                (1 - math.asinh(math.tan(lat)) / math.pi) / 2 * world)

    def unproject(x, y):
        return [math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / world)))),
                x / world * 360 - 180]

    ax, ay = project(a)
    bx, by = project(b)
    distance = math.hypot(bx - ax, by - ay)
    if distance < 1:
        return []
    ux, uy = (bx - ax) / distance, (by - ay) / distance
    if marker == "pin":
        # A Leaflet pin is anchored at its bottom, with its body above it.
        across = 16 / abs(ux) if abs(ux) > 1e-9 else math.inf
        vertical = (44 if uy > 0 else 4) / abs(uy) if abs(uy) > 1e-9 else math.inf
        gap = min(across, vertical) + 5
    else:
        gap = 17  # Operate circle radius 12 px plus a visible gap.
    available = distance - gap - 5
    if available < 3:
        return []
    meters_per_pixel = 2 * math.pi * R_EARTH * math.cos(math.radians((a[0] + b[0]) / 2)) / world
    length = min(length_m / meters_per_pixel, available * .6)
    half_width = min(width_m / meters_per_pixel / 2, length * .6)
    tx, ty = bx - ux * gap, by - uy * gap
    cx, cy = tx - ux * length, ty - uy * length
    return [unproject(tx, ty), unproject(cx - uy * half_width, cy + ux * half_width),
            unproject(cx + uy * half_width, cy - ux * half_width)]
