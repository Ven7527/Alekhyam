from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLineEdit, QSpinBox,
)

from .widgets import colorPicker


class MetricAnnotationDialog(QDialog):
    """Display settings for a single metric annotation (RMSD / MAE / MSE)."""

    def __init__(self, settings, metric_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{metric_name} — annotation settings")
        self.setMinimumWidth(330)

        layout = QFormLayout(self)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self.unitEdit = QLineEdit(settings.get("unit", ""))
        self.unitEdit.setPlaceholderText("e.g. m/s  (blank = none)")
        layout.addRow("Unit", self.unitEdit)

        self.decimalsSpin = QSpinBox()
        self.decimalsSpin.setRange(1, 8)
        self.decimalsSpin.setValue(settings.get("decimals", 4))
        layout.addRow("Decimal places", self.decimalsSpin)

        self.xSpin = QDoubleSpinBox()
        self.xSpin.setRange(0.0, 1.0)
        self.xSpin.setDecimals(3)
        self.xSpin.setSingleStep(0.05)
        self.xSpin.setValue(settings.get("x", 0.05))
        layout.addRow("Position X (axes 0–1)", self.xSpin)

        self.ySpin = QDoubleSpinBox()
        self.ySpin.setRange(0.0, 1.0)
        self.ySpin.setDecimals(3)
        self.ySpin.setSingleStep(0.05)
        self.ySpin.setValue(settings.get("y", 0.95))
        layout.addRow("Position Y (axes 0–1)", self.ySpin)

        self.fontSizeSpin = QSpinBox()
        self.fontSizeSpin.setRange(6, 36)
        self.fontSizeSpin.setValue(settings.get("fontSize", 11))
        self.fontSizeSpin.setSuffix(" pt")
        layout.addRow("Font size", self.fontSizeSpin)

        self.fontWeightCombo = QComboBox()
        self.fontWeightCombo.addItems(["normal", "bold"])
        self.fontWeightCombo.setCurrentText(settings.get("fontWeight", "normal"))
        layout.addRow("Font weight", self.fontWeightCombo)

        colorContainer, self._getColor, _ = colorPicker(settings.get("color", "#000000"))
        layout.addRow("Color", colorContainer)

        self.haCombo = QComboBox()
        self.haCombo.addItems(["left", "center", "right"])
        self.haCombo.setCurrentText(settings.get("ha", "left"))
        layout.addRow("H align", self.haCombo)

        self.vaCombo = QComboBox()
        self.vaCombo.addItems(["top", "center", "bottom"])
        self.vaCombo.setCurrentText(settings.get("va", "top"))
        layout.addRow("V align", self.vaCombo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def resultValues(self):
        return {
            "unit":       self.unitEdit.text().strip(),
            "decimals":   self.decimalsSpin.value(),
            "x":          self.xSpin.value(),
            "y":          self.ySpin.value(),
            "fontSize":   self.fontSizeSpin.value(),
            "fontWeight": self.fontWeightCombo.currentText(),
            "color":      self._getColor() or "#000000",
            "ha":         self.haCombo.currentText(),
            "va":         self.vaCombo.currentText(),
        }
