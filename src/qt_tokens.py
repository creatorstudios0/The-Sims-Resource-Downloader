"""Shared desktop design tokens and packaged visual assets."""
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFontDatabase

ASSETS = Path(__file__).resolve().parent / "assets"
SUCCESS = "#78D7AB"
WARNING = "#F4C879"
ERROR = "#F995A0"
ACCENT = "#B7A6F5"
INK = "#121017"
DENSITIES = {"Comfortable": (34, "7px 10px"), "Compact": (27, "4px 8px")}


@dataclass(frozen=True)
class Palette:
    background: str
    sidebar: str
    surface: str
    input: str
    control: str
    hover: str
    border: str
    selection: str
    text: str = "#F1F0F4"
    muted: str = "#A8A5B2"
    subdued: str = "#858291"


THEMES = {
    "Midnight": Palette("#101015", "#141419", "#18181F", "#121218",
                        "#222229", "#2C2B34", "#30303A", "#353044"),
    "Graphite": Palette("#151619", "#191B1F", "#202227", "#181A1E",
                        "#282B31", "#32353D", "#3C3F48", "#393643"),
    "Deep navy": Palette("#10141D", "#131824", "#191F2D", "#121722",
                         "#222B3A", "#2C3548", "#323C50", "#353349"),
}


def palette(name):
    return THEMES.get(name, THEMES["Midnight"])


def load_typeface():
    if "Inter" not in QFontDatabase.families():
        QFontDatabase.addApplicationFont(str(ASSETS / "Inter.ttf"))
    return "Inter" if "Inter" in QFontDatabase.families() else "Segoe UI"
