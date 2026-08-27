from __future__ import annotations

import math
import os
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import xarray as xr

from helpers.inputs_helper import InputsHelper
from helpers.operate_results_helper import OperateResultsHelper
from helpers.results_helper import ResultsHelper

# -----------------------------
# Paths & loaders
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "models" / "1_german_scale"
MODEL_DIR = Path(os.environ.get("CALLIOPE_DASHBOARD_MODEL_DIR", DEFAULT_MODEL_DIR)).expanduser().resolve()

PLANNING_PATH = MODEL_DIR / "planning.nc"
OPERATE_PATH = MODEL_DIR / "operate.nc"


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
INPUT_LOCATIONS, INPUT_LONGITUDES, INPUT_LATITUDES = [list(x) for x in zip(*INPUT_RAW_COORDS)]

INPUT_CITIES = {name: [lat, lon] for name, lon, lat in INPUT_RAW_COORDS}

def _compute_map_center() -> List[float]:
    if not INPUT_LATITUDES or not INPUT_LONGITUDES:
        return [51.17, 10.45]
    avg_lat = float(sum(INPUT_LATITUDES)) / float(len(INPUT_LATITUDES))
    avg_lon = float(sum(INPUT_LONGITUDES)) / float(len(INPUT_LONGITUDES))
    return [avg_lat, avg_lon]


MAP_CENTER = _compute_map_center()
MAP_ZOOM_DEFAULT = 6

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
L_REF_M = 25000
W_REF_M = 18000
L_MIN_M, L_MAX_M = 4000, 80000
W_MIN_M, W_MAX_M = 3000, 60000


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
    l_val = max(L_MIN_M, min(L_MAX_M, L_REF_M * factor))
    w_val = max(W_MIN_M, min(W_MAX_M, W_REF_M * factor))
    return l_val, w_val


def arrowhead_triangle_at_b(a: List[float], b: List[float], length_m: float, width_m: float) -> List[List[float]]:
    """Build a triangular arrowhead at destination B, pointing A -> B."""
    tip = b
    dir_ab = initial_bearing_deg(a, b)
    base_center = destination_point(tip[0], tip[1], length_m, (dir_ab + 180) % 360)
    left_bearing = (dir_ab + 90) % 360
    right_bearing = (dir_ab + 270) % 360
    base_left = destination_point(base_center[0], base_center[1], width_m / 2.0, left_bearing)
    base_right = destination_point(base_center[0], base_center[1], width_m / 2.0, right_bearing)
    return [tip, base_left, base_right]
