from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGroupBox, QLabel, QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from .plotCanvas import markerOptions
from .widgets import colorPicker, sliderSpinPair

lineStyleOptions = {
    "Solid":    "-",
    "Dashed":   "--",
    "Dotted":   ":",
    "Dash-dot": "-.",
}
_codeToLabel = {v: k for k, v in lineStyleOptions.items()}

_scatterMarkers = {k: v for k, v in markerOptions.items() if k != "None"}
_scatterCodeToLabel = {v: k for k, v in _scatterMarkers.items()}

_KIND_TITLES = {
    "line":      "Line style",
    "scatter":   "Scatter style",
    "histogram": "Histogram style",
}


class SeriesStyleDialog(QDialog):
    """Per-series appearance — layout adapts for Line, Scatter, or Histogram."""

    def __init__(self, entry, parent=None, dataFrames=None):
        super().__init__(parent)
        self._kind = entry.get("kind", "line")
        self._dataFrames = dataFrames or {}
        self.setWindowTitle(_KIND_TITLES.get(self._kind, "Series style"))
        self.setMinimumWidth(340)

        outerLayout = QVBoxLayout(self)
        outerLayout.setContentsMargins(0, 0, 0, 12)
        outerLayout.setSpacing(0)

        inner = QWidget()
        innerLayout = QVBoxLayout(inner)
        innerLayout.setContentsMargins(12, 12, 12, 4)
        innerLayout.setSpacing(10)

        # ── Appearance ────────────────────────────────────────────────
        appGroup = QGroupBox("Appearance")
        appLayout = QFormLayout(appGroup)
        appLayout.setVerticalSpacing(8)

        self.legendEdit = QLineEdit(entry.get("legendLabel") or "")
        self.legendEdit.setPlaceholderText("auto")
        appLayout.addRow("Legend label", self.legendEdit)

        colorContainer, self._getColor, _ = colorPicker(entry.get("color"))
        appLayout.addRow("Color", colorContainer)

        if self._kind == "histogram":
            self.binsSpin = QSpinBox()
            self.binsSpin.setRange(2, 500)
            self.binsSpin.setValue(entry.get("bins", 20))
            self.binsSpin.setSuffix(" bins")
            appLayout.addRow("Bins", self.binsSpin)

        elif self._kind == "line":
            self.lineStyleCombo = QComboBox()
            self.lineStyleCombo.addItems(list(lineStyleOptions.keys()))
            self.lineStyleCombo.setCurrentText(
                _codeToLabel.get(entry.get("linestyle", "-"), "Solid")
            )
            appLayout.addRow("Line style", self.lineStyleCombo)

            lwContainer, self._getLinewidth, _ = sliderSpinPair(
                0.5, 6.0, entry.get("linewidth", 2.5), step=0.5, decimals=1,
            )
            appLayout.addRow("Line width", lwContainer)

            self.markerCombo = QComboBox()
            self.markerCombo.addItems(list(markerOptions.keys()))
            markerCodeToLabel = {v: k for k, v in markerOptions.items() if v is not None}
            self.markerCombo.setCurrentText(
                markerCodeToLabel.get(entry.get("marker"), "None")
            )
            appLayout.addRow("Marker (opt.)", self.markerCombo)

        else:  # scatter
            self._scatterSizeSpin = QSpinBox()
            self._scatterSizeSpin.setRange(10, 500)
            self._scatterSizeSpin.setSingleStep(10)
            self._scatterSizeSpin.setValue(entry.get("scatterSize", 60))
            self._scatterSizeSpin.setSuffix(" pt²")
            appLayout.addRow("Point size", self._scatterSizeSpin)

            self.markerCombo = QComboBox()
            self.markerCombo.addItems(list(_scatterMarkers.keys()))
            self.markerCombo.setCurrentText(
                _scatterCodeToLabel.get(entry.get("marker"), "Circle")
            )
            appLayout.addRow("Marker", self.markerCombo)

        alphaContainer, self._getAlpha, _ = sliderSpinPair(
            0.05, 1.0, entry.get("alpha", 0.9), step=0.05, decimals=2,
        )
        appLayout.addRow("Opacity", alphaContainer)

        if self._kind != "histogram":
            self.markerEdgeCheck = QCheckBox("Draw marker edge / outline")
            self.markerEdgeCheck.setChecked(entry.get("markerEdge", True))
            appLayout.addRow("", self.markerEdgeCheck)

            self.rightAxisCheck = QCheckBox("Use right Y axis")
            self.rightAxisCheck.setChecked(entry.get("useRightAxis", False))
            appLayout.addRow("", self.rightAxisCheck)

        innerLayout.addWidget(appGroup)

        # ── Error bars (line + scatter) ───────────────────────────────
        if self._kind in ("line", "scatter") and self._dataFrames:
            errGroup = QGroupBox("Error bars")
            errLayout = QFormLayout(errGroup)
            errLayout.setVerticalSpacing(6)
            self._errCheck = QCheckBox("Show error bars")
            self._errCheck.setChecked(entry.get("errData") is not None)
            errLayout.addRow(self._errCheck)
            self._errCombo = self._buildColumnCombo(entry.get("errData"))
            self._errCombo.setEnabled(self._errCheck.isChecked())
            self._errCheck.toggled.connect(self._errCombo.setEnabled)
            errLayout.addRow("Error column", self._errCombo)
            innerLayout.addWidget(errGroup)

        # ── Rolling average (line only) ───────────────────────────────
        if self._kind == "line":
            smoothGroup = QGroupBox("Rolling average overlay")
            smoothLayout = QFormLayout(smoothGroup)
            smoothLayout.setVerticalSpacing(6)
            self._smoothCheck = QCheckBox("Show rolling average")
            self._smoothCheck.setChecked(entry.get("smoothing", False))
            smoothLayout.addRow(self._smoothCheck)
            self._smoothSpin = QSpinBox()
            self._smoothSpin.setRange(2, 500)
            self._smoothSpin.setValue(entry.get("smoothWindow", 10))
            self._smoothSpin.setSuffix(" pts")
            self._smoothSpin.setEnabled(self._smoothCheck.isChecked())
            self._smoothCheck.toggled.connect(self._smoothSpin.setEnabled)
            smoothLayout.addRow("Window", self._smoothSpin)
            innerLayout.addWidget(smoothGroup)

        # ── Color encoding (scatter only) ─────────────────────────────
        if self._kind == "scatter" and self._dataFrames:
            colorByGroup = QGroupBox("Color by column")
            colorByLayout = QFormLayout(colorByGroup)
            colorByLayout.setVerticalSpacing(6)
            self._colorByCheck = QCheckBox("Map color to a column (viridis)")
            self._colorByCheck.setChecked(entry.get("colorByCol") is not None)
            colorByLayout.addRow(self._colorByCheck)
            self._colorByCombo = self._buildColumnCombo(entry.get("colorByCol"))
            self._colorByCombo.setEnabled(self._colorByCheck.isChecked())
            self._colorByCheck.toggled.connect(self._colorByCombo.setEnabled)
            colorByLayout.addRow("Column", self._colorByCombo)
            innerLayout.addWidget(colorByGroup)

        # ── Row filter (all types) ─────────────────────────────────────
        filterGroup = QGroupBox("Row filter")
        filterLayout = QFormLayout(filterGroup)
        filterLayout.setVerticalSpacing(6)
        self._filterEdit = QLineEdit(entry.get("filterExpr", ""))
        self._filterEdit.setPlaceholderText("e.g.  y > 0  or  x >= 1.5  (blank = no filter)")
        filterLayout.addRow("Query", self._filterEdit)
        fhint = QLabel("Pandas query — use 'x' and 'y' to refer to the plotted columns.")
        fhint.setWordWrap(True)
        fhint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        filterLayout.addRow("", fhint)
        innerLayout.addWidget(filterGroup)

        innerLayout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(620)
        outerLayout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setContentsMargins(12, 4, 12, 0)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outerLayout.addWidget(buttons)

    def _buildColumnCombo(self, current=None):
        combo = QComboBox()
        combo.addItem("(none)", None)
        for label, df in self._dataFrames.items():
            for col in df.select_dtypes(include="number").columns:
                combo.addItem(f"{col}  [{label}]", (label, col))
        if current is not None:
            for i in range(combo.count()):
                if combo.itemData(i) == current:
                    combo.setCurrentIndex(i)
                    break
        return combo

    def resultValues(self):
        result = {
            "legendLabel": self.legendEdit.text().strip(),
            "color":       self._getColor(),
            "alpha":       self._getAlpha(),
            "filterExpr":  self._filterEdit.text().strip(),
        }

        if self._kind == "histogram":
            result["bins"] = self.binsSpin.value()
            return result

        result["marker"]       = markerOptions.get(self.markerCombo.currentText())
        result["markerEdge"]   = self.markerEdgeCheck.isChecked()
        result["useRightAxis"] = self.rightAxisCheck.isChecked()

        if self._kind == "line":
            result["linestyle"]    = lineStyleOptions[self.lineStyleCombo.currentText()]
            result["linewidth"]    = self._getLinewidth()
            result["smoothing"]    = self._smoothCheck.isChecked()
            result["smoothWindow"] = self._smoothSpin.value()
        else:  # scatter
            result["scatterSize"] = self._scatterSizeSpin.value()
            if result["marker"] is None:
                result["marker"] = "o"
            if hasattr(self, "_colorByCheck") and self._dataFrames:
                result["colorByCol"] = (
                    self._colorByCombo.currentData()
                    if self._colorByCheck.isChecked() else None
                )

        if hasattr(self, "_errCheck") and self._dataFrames:
            result["errData"] = (
                self._errCombo.currentData()
                if self._errCheck.isChecked() else None
            )

        return result
