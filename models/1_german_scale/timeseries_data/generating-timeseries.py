import numpy as np
import pandas as pd

"""
For the German-Scale toy scenario I decided to generate all timeseries data on my own so that I avoid
problems with licensing.
For each desired city, I generate 4 timeseries:
- PV profile
- Wind profile
- Hydro profile
- Demand

Each of these is generated using some kind of trigonometric function + noise. The exact implementation of those
was done by ChatGPT(with minor adjustments from my side); but as far as I could verify it 
in the `exploring-timeseries.ipynb`, the data looks similar to real.

When calculating Demand for each city, its population is taken into the account - the bigger population, 
the bigger demand.

Similarly, when calculating green energy supply timeseries, additional coefficients are used. For example,
Hamburg has much bigger wind energy potential than Munich due to limitations of the nature. This allows estimate the
real conditions of green energy supply.

All the timeseries are saved in the `timeseries_data` folder.
"""

# Parameters
hours_per_year = 365 * 24
time_index = pd.date_range("2025-01-01", periods=hours_per_year, freq="H")

# Populations (fictional realistic)
populations = {
    "Berlin": 3_600_000,
    "Hamburg": 1_800_000,
    "Munich": 1_500_000,
    "Cologne": 1_100_000,
    "Frankfurt": 750_000,
    "Leipzig": 600_000,
    "Hannover": 500_000,
    "Nuremberg": 500_000
}

# Tech coefficients per city
coefficients = {
    "Berlin": {"pv": 0.8, "wind": 0.6, "hydro": 0.3},
    "Hamburg": {"pv": 0.7, "wind": 1.0, "hydro": 0.2},
    "Munich": {"pv": 1.0, "wind": 0.4, "hydro": 0.8},
    "Cologne": {"pv": 0.75, "wind": 0.5, "hydro": 0.3},
    "Frankfurt": {"pv": 0.85, "wind": 0.5, "hydro": 0.3},
    "Leipzig": {"pv": 0.8, "wind": 0.7, "hydro": 0.3},
    "Hannover": {"pv": 0.8, "wind": 0.8, "hydro": 0.2},
    "Nuremberg": {"pv": 0.9, "wind": 0.4, "hydro": 0.7}
}


# Base profiles
def generate_pv_profile():
    hours = np.arange(hours_per_year)
    day_of_year = hours // 24
    pv = np.maximum(0, np.sin((hours % 24 - 6) / 12 * np.pi)) \
         * (0.5 + 0.5 * np.sin((day_of_year - 80) / 365 * 2 * np.pi))
    return pv


def generate_wind_profile():
    base = 0.5 + 0.3 * np.random.rand(hours_per_year)
    seasonal = 0.5 + 0.5 * np.sin(np.arange(hours_per_year) / 8760 * 2 * np.pi)
    return base * seasonal


def generate_hydro_profile():
    seasonal = 0.7 + 0.3 * np.sin((np.arange(hours_per_year) / 8760 * 2 * np.pi) - 1)
    return seasonal


def generate_demand_profile(base=1000):
    hours_per_year = 8760
    hours = np.arange(hours_per_year)

    # --- Seasonal pattern ---
    # main winter-summer cycle
    seasonal = 0.12 * np.cos(2 * np.pi * hours / hours_per_year)
    # add second harmonic to create smaller summer peak
    seasonal += 0.05 * np.cos(4 * np.pi * hours / hours_per_year)

    # --- Daily pattern ---
    hour_of_day = hours % 24
    # two daily peaks: morning (7–9) and evening (18–21)
    daily = 0.15 * np.sin((hour_of_day - 7) / 24 * 2 * np.pi) + 0.25 * np.sin((hour_of_day - 19) / 24 * 2 * np.pi)

    # --- Random noise ---
    noise = 0.05 * np.random.randn(hours_per_year)

    # --- Final demand ---
    demand = -base * (1.3 + seasonal + daily + noise)

    return np.minimum(demand, 0)


# Generate CSVs
for city, pop in populations.items():
    coeff = coefficients[city]

    pv_profile = generate_pv_profile() * coeff["pv"]
    wind_profile = generate_wind_profile() * coeff["wind"]
    hydro_profile = generate_hydro_profile() * coeff["hydro"]
    demand_profile = generate_demand_profile(pop)

    df = pd.DataFrame({
        "pv": pv_profile,  # kWh/m²
        "wind": wind_profile,  # kWh/m²
        "hydro": hydro_profile,  # kWh/m²
        "demand": demand_profile  # kWh
    }, index=time_index)

    df.to_csv(f"{city}_timeseries.csv", index_label="time")
