"""Shared, name-based technology colors for Planning and Operate charts.

Model colors have priority. Missing colors use name-based rules, then a stable
fallback for unrecognized technologies.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata


# Specific technologies precede broader fuel/resource keywords. Match whole
# words, not substrings: e.g. "gas" must not classify "Las Vegas".
COLOR_RULES = (
    (r"solar thermal|concentrated solar|csp|solartherm\w*|solar warm\w*|солнеч\w* теп\w*", "#E89B23"),
    (r"heat pump|heatpump|waermepumpe\w*|warmepumpe\w*|теплов\w* насос\w*|hp|ashp|gshp", "#E76F51"),
    (r"pumped hydro|pumped storage|phs|psh|phes|pumpspeicher\w*|гаэс", "#2455A4"),
    (r"thermal storage|heat storage|hot water|warmwass\w*|waermespeicher\w*|warmespeicher\w*|теплоаккум\w*", "#B85C38"),
    (r"hydrogen|wasserstoff|водород\w*|h2|electrolys\w*|elektrolys\w*|электролиз\w*|fuel cell|brennstoffzelle\w*|топливн\w* элемент\w*", "#8C6BB1"),
    (r"biogas|biomethane|биогаз\w*", "#6A994E"),
    (r"biomass|biomasse|bioenergy|biofuel|wood|pellet\w*|holz|биомасс\w*|дров\w*|пеллет\w*", "#608C3C"),
    (r"geothermal|geotherm\w*|erdwaerme|erdwarme|геотерм\w*", "#A65E3B"),
    (r"offshore wind|offshore", "#388FB5"),
    (r"wind|windturbine\w*|windkraft\w*|windenergie|ветр\w*", "#6FB8E6"),
    (r"solar|pv|photovoltaic\w*|photovoltaik\w*|photovoltaics|sonnen\w*|солнеч\w*|фотовольт\w*|сэс", "#F9D956"),
    (r"hydro\w*|water|wasser\w*|run of river|ror|tidal|wave|гидро\w*|прилив\w*|волнов\w*|гэс", "#2E54D1"),
    (r"battery|batteries|batterie\w*|bess|lithium|li ion|аккумулятор\w*|батаре\w*", "#2A9D8F"),
    (r"compressed air|caes|flywheel|schwungrad\w*|маховик\w*", "#438D87"),
    (r"electric vehicle|ev|v2g|charging|lade\w*|электромобил\w*", "#AD6A9F"),
    (r"nuclear|uranium|atomkraft\w*|kernkraft\w*|ядер\w*|атом\w*|аэс", "#B39BCE"),
    (r"lignite|braunkohle|бур\w* уголь", "#7A6253"),
    (r"coal|kohle|steinkohle|уголь\w*|угле\w*", "#4E4E4E"),
    (r"diesel|oil|petrol\w*|heizoel|heizol|нефт\w*|дизел\w*|мазут\w*", "#8B5E3C"),
    (r"gas|methane|erdgas|ccgt|ocgt|газ\w*|метан\w*", "#D9A15C"),
    (r"waste|incinerat\w*|muell\w*|mull\w*|отход\w*|мусор\w*", "#8A8170"),
    (r"chp|cogeneration|kwk|bhkw|когенерац\w*|тэц", "#CC7855"),
    (r"boiler|furnace|kessel|котел\w*|котёл\w*", "#C76A40"),
    (r"district heat|heat|heating|waerme\w*|warme\w*|тепл\w*", "#D66B52"),
    (r"transmission|grid|import|export|netz\w*|stromnetz|сеть|сетев\w*|импорт\w*|экспорт\w*", "#687B91"),
    (r"storage|speicher\w*|накопител\w*|хранилищ\w*", "#4F9C91"),
    (r"demand|load|consumption|bedarf|verbrauch\w*|спрос\w*|потреблен\w*|нагруз\w*", "#84919E"),
)
_RULES = [(re.compile(r"\b(?:" + pattern + r")\b"), color) for pattern, color in COLOR_RULES]
_FALLBACK = ("#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2")


def _words(value: str) -> str:
    value = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", str(value))
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    value = re.sub(r"[^\w]+|_", " ", value)
    # Split model IDs such as pv100 and pv_roof, but preserve H2.
    value = re.sub(r"(?i)\bpv(?=\d)", "pv ", value)
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^\w]+|_", " ", value).strip()


def technology_color(tech_id: str, name: str = "", model_color: str | None = None) -> str:
    """Choose a resource/fuel hue from both ID and label, independently of order."""
    if model_color and str(model_color).strip().casefold() not in {"nan", "none", ""}:
        return str(model_color).strip()
    text = f"{_words(tech_id)} {_words(name)}"
    for pattern, color in _RULES:
        if pattern.search(text):
            return color
    digest = hashlib.sha256(str(tech_id).encode("utf-8")).digest()
    return _FALLBACK[int.from_bytes(digest[:4], "big") % len(_FALLBACK)]
