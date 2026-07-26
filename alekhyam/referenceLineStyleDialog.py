from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QSpinBox,
)

from .widgets import colorPicker, sliderSpinPair

lineStyleOptions = {
    "Dashed": "--",
    "Solid": "-",
    "Dotted": ":",
    "Dash-dot": "-.",
}
lineStyleCodeToLabel = {code: label for label, code in lineStyleOptions.items()}


class ReferenceLineStyleDialog(QDialog):
    """Appearance overrides for a single reference line: color, width, alpha, style."""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced line style")
        self.setMinimumWidth(320)

        layout = QFormLayout(self)

        colorContainer, self._getColor, _ = colorPicker(entry.get("color"), defaultPreview="#888888")
        layout.addRow("Color", colorContainer)

        self.styleCombo = QComboBox()
        self.styleCombo.addItems(list(lineStyleOptions.keys()))
        self.styleCombo.setCurrentText(lineStyleCodeToLabel.get(entry.get("linestyle", "--"), "Dashed"))
        layout.addRow("Line style", self.styleCombo)

        linewidthContainer, self._getLinewidth, _ = sliderSpinPair(
            0.5, 6.0, entry.get("linewidth", 1.5), step=0.1, decimals=1,
        )
        layout.addRow("Line width", linewidthContainer)

        alphaContainer, self._getAlpha, _ = sliderSpinPair(
            0.05, 1.0, entry.get("alpha", 0.8), step=0.05, decimals=2,
        )
        layout.addRow("Opacity (alpha)", alphaContainer)

        self.zorderSpin = QSpinBox()
        self.zorderSpin.setRange(0, 20)
        self.zorderSpin.setValue(int(entry.get("zorder", 2)))
        self.zorderSpin.setToolTip("Stacking order — higher numbers draw in front")
        layout.addRow("Layer (z-order)", self.zorderSpin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def resultValues(self):
        return {
            "color": self._getColor(),
            "linestyle": lineStyleOptions[self.styleCombo.currentText()],
            "linewidth": self._getLinewidth(),
            "alpha": self._getAlpha(),
            "zorder": self.zorderSpin.value(),
        }
