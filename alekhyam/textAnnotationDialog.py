from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QLineEdit, QSpinBox,
)

from .widgets import colorPicker


class TextAnnotationDialog(QDialog):
    """Add / edit a text label anywhere on the figure."""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Text annotation")
        self.setMinimumWidth(340)

        layout = QFormLayout(self)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self.textEdit = QLineEdit(entry.get("text", ""))
        self.textEdit.setPlaceholderText("Annotation text")
        layout.addRow("Text", self.textEdit)

        # Coordinate type
        self.coordCombo = QComboBox()
        self.coordCombo.addItems(["Axes (0 – 1)", "Data coordinates"])
        self.coordCombo.setCurrentIndex(0 if entry.get("coordType", "axes") == "axes" else 1)
        layout.addRow("Coords", self.coordCombo)

        hint = QLabel("Axes: 0 = left/bottom, 1 = right/top  |  Data: actual plot units")
        hint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        layout.addRow("", hint)

        self.xSpin = QDoubleSpinBox()
        self.xSpin.setRange(-1e9, 1e9)
        self.xSpin.setDecimals(4)
        self.xSpin.setValue(entry.get("x", 0.5))
        layout.addRow("X", self.xSpin)

        self.ySpin = QDoubleSpinBox()
        self.ySpin.setRange(-1e9, 1e9)
        self.ySpin.setDecimals(4)
        self.ySpin.setValue(entry.get("y", 0.5))
        layout.addRow("Y", self.ySpin)

        self.fontSizeSpin = QSpinBox()
        self.fontSizeSpin.setRange(6, 96)
        self.fontSizeSpin.setValue(entry.get("fontSize", 12))
        self.fontSizeSpin.setSuffix(" pt")
        layout.addRow("Font size", self.fontSizeSpin)

        self.fontWeightCombo = QComboBox()
        self.fontWeightCombo.addItems(["normal", "bold", "light"])
        self.fontWeightCombo.setCurrentText(entry.get("fontWeight", "normal"))
        layout.addRow("Font weight", self.fontWeightCombo)

        colorContainer, self._getColor, _ = colorPicker(entry.get("color", "#000000"))
        layout.addRow("Color", colorContainer)

        self.rotationSpin = QSpinBox()
        self.rotationSpin.setRange(0, 359)
        self.rotationSpin.setValue(int(entry.get("rotation", 0)))
        self.rotationSpin.setSuffix("°")
        layout.addRow("Rotation", self.rotationSpin)

        self.haCombo = QComboBox()
        self.haCombo.addItems(["left", "center", "right"])
        self.haCombo.setCurrentText(entry.get("ha", "center"))
        layout.addRow("H align", self.haCombo)

        self.vaCombo = QComboBox()
        self.vaCombo.addItems(["top", "center", "bottom"])
        self.vaCombo.setCurrentText(entry.get("va", "center"))
        layout.addRow("V align", self.vaCombo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def resultValues(self):
        return {
            "text":       self.textEdit.text(),
            "coordType":  "axes" if self.coordCombo.currentIndex() == 0 else "data",
            "x":          self.xSpin.value(),
            "y":          self.ySpin.value(),
            "fontSize":   self.fontSizeSpin.value(),
            "fontWeight": self.fontWeightCombo.currentText(),
            "color":      self._getColor() or "#000000",
            "rotation":   self.rotationSpin.value(),
            "ha":         self.haCombo.currentText(),
            "va":         self.vaCombo.currentText(),
        }
