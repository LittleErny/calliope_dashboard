"""Semantic hues must survive model naming conventions and scenario changes."""
import pytest

from helpers.technology_colors import technology_color


@pytest.mark.parametrize("tech,name,reference", [
    ("roof_pv_100", "Rooftop generation", "solar"),
    ("roof_pv100", "", "solar"),
    ("PVRooftop", "", "solar"),
    ("PV100", "", "solar"),
    ("rooftopPV", "", "solar"),
    ("supply_1", "Photovoltaik Süd", "solar"),
    ("supply_2", "Солнечная станция", "solar"),
    ("collector", "Solar Thermal", "solar_thermal"),
    ("csp_plant", "", "solar_thermal"),
    ("phs", "", "pumped_storage"),
    ("flywheel", "", "caes"),
    ("ev_charging", "", "electric_vehicle"),
    ("onshore_wind", "", "wind"),
    ("wind_offshore", "", "offshore"),
    ("river_plant", "Run-of-river", "hydro"),
    ("plant", "Wasserkraft", "hydro"),
    ("plant", "Гидроэлектростанция", "hydro"),
    ("pumped_hydro_storage", "", "pumped_storage"),
    ("bess_1", "", "battery"),
    ("store", "Lithium-ion battery", "battery"),
    ("hot_water_tank", "", "thermal_storage"),
    ("supply", "Wärmespeicher", "thermal_storage"),
    ("hp", "", "heat_pump"),
    ("pump", "Wärmepumpe", "heat_pump"),
    ("hp_air", "Тепловой насос", "heat_pump"),
    ("h2_storage", "", "hydrogen"),
    ("electrolyser", "", "hydrogen"),
    ("fuel_cell", "", "hydrogen"),
    ("biogas_boiler", "", "biogas"),
    ("wood_pellets", "", "biomass"),
    ("ground", "Geothermie", "geothermal"),
    ("ccgt", "", "gas"),
    ("gas_boiler", "", "gas"),
    ("coal_chp", "", "coal"),
    ("braunkohle", "", "lignite"),
    ("uranium_plant", "", "nuclear"),
    ("diesel_generator", "", "oil"),
    ("waste_incinerator", "", "waste"),
    ("bhkw", "", "chp"),
    ("electric_boiler", "", "boiler"),
    ("district_heating", "", "heat"),
    ("electricity_import", "", "grid"),
    ("thermal_demand", "", "demand"),
])
def test_recognizes_ids_labels_and_specific_technologies(tech, name, reference):
    assert technology_color(tech, name) == technology_color(reference)


@pytest.mark.parametrize("tech", ["Las Vegas", "window", "preview", "gastronomy", "coalescence"])
def test_no_accidental_substring_matches(tech):
    assert technology_color(tech, model_color="#123456") == "#123456"


def test_model_colors_take_priority_over_keywords():
    assert technology_color("pv_roof", model_color="#FF0000") == "#FF0000"
    assert technology_color("water_turbine", model_color="#FF0000") == "#FF0000"
    assert technology_color("solar", model_color=" goldenrod ") == "goldenrod"
    for missing in (None, "nan", "None", "", "   "):
        assert technology_color("pv_roof", model_color=missing) == "#F9D956"
        assert technology_color("water_turbine", model_color=missing) == "#2E54D1"
    assert technology_color("solar_thermal") != technology_color("pv")
    assert technology_color("biogas") != technology_color("gas")
    assert technology_color("pumped_storage") != technology_color("battery")


def test_unknown_fallback_is_stable_and_keeps_explicit_colors():
    techs = ["unknown_a", "unknown_b", "unknown_c"]
    forward = {tech: technology_color(tech) for tech in techs}
    assert forward == {tech: technology_color(tech) for tech in reversed(techs)}
    for missing in (None, "nan", "None", ""):
        assert technology_color("unknown_a", model_color=missing) == forward["unknown_a"]
    assert technology_color("unknown_a", model_color="#ABCDEF") == "#ABCDEF"


@pytest.mark.parametrize("model_colors", [True, False])
def test_planning_and_operate_share_colors(monkeypatch, model_colors):
    from app import app_data

    for scenario in app_data.SCENARIOS:
        bundle = app_data.get_scenario(scenario, "electricity")
        planning = bundle.RESULTS_HELPER
        operate = bundle.OPERATE_HELPER
        if not model_colors:
            monkeypatch.setattr(planning, "_tech_color_map", {})
            monkeypatch.setattr(operate, "_tech_color_map", {})
        plan_colors = planning.get_technology_color_map()
        operate_colors = operate.get_technology_color_map()
        for tech, color in operate_colors.items():
            assert plan_colors[planning._humanize_tech(tech)] == color
        if not model_colors:
            assert planning.get_technology_color_map(include_fallback=False) == {}
            assert plan_colors["Solar Photovoltaic Power"] == "#F9D956"
            assert plan_colors["Wind Energy"] == "#6FB8E6"
