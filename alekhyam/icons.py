"""
Icon helpers — thin wrappers around qtawesome (Font Awesome 5 Solid).

All functions accept a color (QColor or hex string) and return a QIcon.
Extra kwargs are accepted and ignored so callers don't break if old
size= arguments are passed during a transition.
"""
import qtawesome as qta
from PySide6.QtGui import QColor


def _c(color):
    """Normalise QColor → hex string for qtawesome."""
    if isinstance(color, QColor):
        return color.name()
    return color or "#000000"


def plusIcon(color, **_):
    return qta.icon("fa5s.plus", color=_c(color))

def minusIcon(color, **_):
    return qta.icon("fa5s.minus", color=_c(color))

def gearIcon(color, **_):
    return qta.icon("fa5s.cog", color=_c(color))

def trashIcon(color, **_):
    return qta.icon("fa5s.trash-alt", color=_c(color))

def resetViewIcon(color, **_):
    return qta.icon("fa5s.sync-alt", color=_c(color))

def folderIcon(color, **_):
    return qta.icon("fa5s.folder", color=_c(color))

def paletteIcon(color, **_):
    return qta.icon("fa5s.palette", color=_c(color))

def slidersIcon(color, **_):
    return qta.icon("fa5s.sliders-h", color=_c(color))

def exportIcon(color, **_):
    return qta.icon("fa5s.file-image", color=_c(color))

def saveIcon(color, **_):
    return qta.icon("fa5s.save", color=_c(color))

def openFileIcon(color, **_):
    return qta.icon("fa5s.folder-open", color=_c(color))

def hLineIcon(color, **_):
    return qta.icon("fa5s.grip-lines", color=_c(color))

def vLineIcon(color, **_):
    return qta.icon("fa5s.grip-lines-vertical", color=_c(color))

def copyIcon(color, **_):
    return qta.icon("fa5s.copy", color=_c(color))

def analysisIcon(color, **_):
    return qta.icon("fa5s.chart-line", color=_c(color))

def statsIcon(color, **_):
    return qta.icon("fa5s.table", color=_c(color))

def clipboardIcon(color, **_):
    return qta.icon("fa5s.clipboard", color=_c(color))

def templateIcon(color, **_):
    return qta.icon("fa5s.file-code", color=_c(color))

def fitIcon(color, **_):
    return qta.icon("fa5s.bezier-curve", color=_c(color))

def gridIcon(color, **_):
    return qta.icon("fa5s.border-all", color=_c(color))

def flipHIcon(color, **_):
    return qta.icon("fa5s.exchange-alt", color=_c(color))

def flipVIcon(color, **_):
    return qta.icon("fa5s.exchange-alt", color=_c(color), rotated=90)

def aspectIcon(color, **_):
    return qta.icon("fa5s.vector-square", color=_c(color))

def ratioIcon(color, **_):
    return qta.icon("fa5s.ruler-combined", color=_c(color))

def rectIcon(color, **_):
    return qta.icon("fa5.square", color=_c(color))

def ellipseIcon(color, **_):
    return qta.icon("fa5.circle", color=_c(color))

def imageIcon(color, **_):
    return qta.icon("fa5s.image", color=_c(color))
