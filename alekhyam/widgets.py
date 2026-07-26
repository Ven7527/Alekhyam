from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)


def iconButton(icon, tooltip="", diameter=28):
    """A small round flat button showing a custom-drawn icon.

    Uses palette()-relative colors (not hardcoded hex) so it reads correctly
    against both light and dark application themes.
    """
    button = QPushButton()
    button.setIcon(icon)
    button.setIconSize(QSize(round(diameter * 0.62), round(diameter * 0.62)))
    button.setToolTip(tooltip)
    button.setFixedSize(diameter, diameter)
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet(
        f"QPushButton {{"
        f"  border-radius: {diameter // 2}px;"
        f"  border: 1px solid palette(mid);"
        f"  background-color: palette(base);"
        f"  padding: 0px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background-color: palette(alternate-base);"
        f"  border-color: #2e73b8;"
        f"}}"
        f"QPushButton:pressed {{"
        f"  background-color: palette(mid);"
        f"}}"
    )
    return button


def sliderSpinPair(minValue, maxValue, initialValue, step=1, decimals=0, suffix="", onChange=None):
    """A slider synced to a spinbox, sharing one row. Returns (container, getValue, setValue).

    onChange, if given, fires with the current value whenever it changes (from either
    control). It's wired to the spinbox only, since slider drags always cascade into a
    spinbox update — wiring both would fire onChange twice per interaction.
    """
    scale = 10 ** decimals

    slider = QSlider(Qt.Horizontal)
    slider.setRange(round(minValue * scale), round(maxValue * scale))
    slider.setSingleStep(max(1, round(step * scale)))

    spin = QDoubleSpinBox() if decimals > 0 else QSpinBox()
    if decimals > 0:
        spin.setDecimals(decimals)
    spin.setRange(minValue, maxValue)
    spin.setSingleStep(step)
    if suffix:
        spin.setSuffix(suffix)

    guard = {"active": False}

    def onSliderChanged(value):
        if guard["active"]:
            return
        guard["active"] = True
        spin.setValue(value / scale)
        guard["active"] = False

    def onSpinChanged(value):
        if guard["active"]:
            return
        guard["active"] = True
        slider.setValue(round(value * scale))
        guard["active"] = False

    slider.valueChanged.connect(onSliderChanged)
    spin.valueChanged.connect(onSpinChanged)
    slider.setValue(round(initialValue * scale))
    spin.setValue(initialValue)

    if onChange is not None:
        spin.valueChanged.connect(onChange)

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(slider, 1)
    layout.addWidget(spin)

    def getValue():
        return spin.value()

    def setValue(value):
        spin.setValue(value)

    return container, getValue, setValue


def colorPicker(initialColor=None, autoLabel="Auto", defaultPreview="#1f77b4"):
    """A button opening a color dialog, plus a reset-to-auto button.

    Returns (container, getColor, setColor). getColor() returns None when set to auto.
    """
    state = {"color": initialColor}

    colorButton = QPushButton()
    colorButton.setCursor(Qt.PointingHandCursor)
    autoButton = QPushButton(autoLabel)
    autoButton.setCursor(Qt.PointingHandCursor)

    def updateButton():
        if state["color"]:
            qc = QColor(state["color"])
            fg = "#101010" if qc.lightness() > 140 else "#f5f5f5"
            colorButton.setStyleSheet(
                f"QPushButton {{ background-color: {state['color']}; color: {fg};"
                f" border: 1px solid palette(mid); border-radius: 7px; padding: 5px 12px; }}"
            )
            colorButton.setText(state["color"])
        else:
            colorButton.setStyleSheet("")   # inherit the app button style
            colorButton.setText("Pick colour…")

    def pickColor():
        initial = QColor(state["color"]) if state["color"] else QColor(defaultPreview)
        color = QColorDialog.getColor(initial, colorButton, "Choose color")
        if color.isValid():
            state["color"] = color.name()
            updateButton()

    def useAuto():
        state["color"] = None
        updateButton()

    colorButton.clicked.connect(pickColor)
    autoButton.clicked.connect(useAuto)
    updateButton()

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(colorButton)
    layout.addWidget(autoButton)

    def getColor():
        return state["color"]

    def setColor(color):
        state["color"] = color
        updateButton()

    return container, getColor, setColor
