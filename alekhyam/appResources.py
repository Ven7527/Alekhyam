import sys
from pathlib import Path


def resourceDir():
    return Path(__file__).resolve().parent / "resources"


def iconPath():
    resources = resourceDir()
    # PNG is universally reliable; SVG needs the Qt SVG plugin.
    # On Windows prefer ICO so the taskbar/ALT-TAB show the right icon.
    if sys.platform == "win32":
        ico = resources / "alekhyam.ico"
        if ico.exists():
            return ico
    png = resources / "alekhyam.png"
    return png if png.exists() else resources / "alekhyam.svg"
