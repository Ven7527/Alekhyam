"""Tests for icon helpers — verify each returns a valid, non-empty QIcon."""
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from alekhyam.icons import (
    exportIcon, folderIcon, gearIcon, hLineIcon, minusIcon, openFileIcon,
    paletteIcon, plusIcon, resetViewIcon, saveIcon, slidersIcon, trashIcon,
    vLineIcon,
)

_COLOR = QColor(30, 30, 30)
_ALL_ICONS = [
    plusIcon, minusIcon, gearIcon, trashIcon, resetViewIcon,
    folderIcon, paletteIcon, slidersIcon, exportIcon, saveIcon,
    hLineIcon, vLineIcon, openFileIcon,
]


@pytest.mark.parametrize("fn", _ALL_ICONS, ids=lambda f: f.__name__)
def test_icon_not_null(qapp, fn):
    assert not fn(_COLOR).isNull()


@pytest.mark.parametrize("fn", _ALL_ICONS, ids=lambda f: f.__name__)
def test_icon_renders_at_24px(qapp, fn):
    icon = fn(_COLOR)
    actual = icon.actualSize(QSize(24, 24))
    assert actual.width() > 0 and actual.height() > 0


def test_icon_accepts_hex_string(qapp):
    assert not plusIcon("#aabbcc").isNull()


def test_icon_accepts_qcolor(qapp):
    assert not plusIcon(QColor(100, 150, 200)).isNull()


def test_different_icons_are_distinct(qapp):
    # qtawesome caches by name+color — same call may return same object,
    # but different icons must differ.
    plus = plusIcon(_COLOR)
    minus = minusIcon(_COLOR)
    assert plus.cacheKey() != minus.cacheKey()
