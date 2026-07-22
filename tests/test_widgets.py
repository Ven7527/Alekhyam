"""Tests for reusable widget helpers: sliderSpinPair, colorPicker, iconButton."""
import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor

from alekhyam.icons import plusIcon
from alekhyam.widgets import colorPicker, iconButton, sliderSpinPair


# ---------------------------------------------------------------------------
# sliderSpinPair
# ---------------------------------------------------------------------------

@pytest.fixture
def slider_pair(qapp):
    container, get, set_ = sliderSpinPair(0.0, 10.0, 5.0, step=0.5, decimals=1)
    return container, get, set_


def test_slider_initial_value(slider_pair):
    _, get, _ = slider_pair
    assert get() == pytest.approx(5.0)


def test_slider_set_value(slider_pair):
    _, get, set_ = slider_pair
    set_(3.5)
    assert get() == pytest.approx(3.5)


def test_slider_set_value_clamped_to_max(slider_pair):
    _, get, set_ = slider_pair
    set_(999.0)
    assert get() == pytest.approx(10.0)


def test_slider_set_value_clamped_to_min(slider_pair):
    _, get, set_ = slider_pair
    set_(-999.0)
    assert get() == pytest.approx(0.0)


def test_slider_onChange_fires(qapp):
    # onChange is wired after the initial setValue, so it fires on subsequent changes only.
    fired = []
    _, get, set_ = sliderSpinPair(0, 10, 5, step=1, decimals=0, onChange=lambda v: fired.append(v))
    set_(8)
    assert len(fired) == 1
    assert fired[0] == 8


def test_slider_integer_mode(qapp):
    _, get, set_ = sliderSpinPair(0, 100, 42, step=1, decimals=0)
    assert get() == 42
    set_(77)
    assert get() == 77


def test_slider_container_is_widget(slider_pair):
    from PySide6.QtWidgets import QWidget
    container, _, _ = slider_pair
    assert isinstance(container, QWidget)


# ---------------------------------------------------------------------------
# colorPicker
# ---------------------------------------------------------------------------

def test_color_picker_initial_auto(qapp):
    _, get, _ = colorPicker()
    assert get() is None


def test_color_picker_initial_color(qapp):
    _, get, _ = colorPicker(initialColor="#ff0000")
    assert get() == "#ff0000"


def test_color_picker_set_color(qapp):
    _, get, set_ = colorPicker()
    set_("#00ff00")
    assert get() == "#00ff00"


def test_color_picker_set_to_none_is_auto(qapp):
    _, get, set_ = colorPicker(initialColor="#ff0000")
    set_(None)
    assert get() is None


# ---------------------------------------------------------------------------
# iconButton
# ---------------------------------------------------------------------------

def test_icon_button_size(qapp):
    color = QColor(30, 30, 30)
    btn = iconButton(plusIcon(color), "tip", diameter=32)
    assert btn.width() == 32
    assert btn.height() == 32


def test_icon_button_tooltip(qapp):
    color = QColor(30, 30, 30)
    btn = iconButton(plusIcon(color), "my tooltip")
    assert btn.toolTip() == "my tooltip"


def test_icon_button_cursor_is_pointing_hand(qapp):
    color = QColor(30, 30, 30)
    btn = iconButton(plusIcon(color))
    assert btn.cursor().shape() == Qt.PointingHandCursor
