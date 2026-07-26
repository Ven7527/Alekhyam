from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox,
)

from .widgets import colorPicker, sliderSpinPair


class FillStyleDialog(QDialog):
    """Appearance options for a horizontal / vertical fill band."""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fill band style")
        self.setMinimumWidth(310)

        layout = QFormLayout(self)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self.legendEdit = QLineEdit(entry.get("legendLabel", ""))
        self.legendEdit.setPlaceholderText("(no legend entry)")
        layout.addRow("Legend label", self.legendEdit)

        colorContainer, self._getFaceColor, _ = colorPicker(entry.get("color") or "#1f77b4")
        layout.addRow("Fill color", colorContainer)

        alphaContainer, self._getAlpha, _ = sliderSpinPair(
            0.01, 1.0, entry.get("alpha", 0.2), step=0.05, decimals=2,
        )
        layout.addRow("Opacity", alphaContainer)

        self.zorderSpin = QSpinBox()
        self.zorderSpin.setRange(0, 20)
        self.zorderSpin.setValue(int(entry.get("zorder", 1)))
        self.zorderSpin.setToolTip("Stacking order — higher numbers draw in front")
        layout.addRow("Layer (z-order)", self.zorderSpin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def resultValues(self):
        return {
            "legendLabel": self.legendEdit.text().strip(),
            "color":       self._getFaceColor(),
            "alpha":       self._getAlpha(),
            "zorder":      self.zorderSpin.value(),
        }
