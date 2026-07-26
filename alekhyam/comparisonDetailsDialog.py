from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from .metricAnnotationDialog import MetricAnnotationDialog

_METRIC_HELP = {
    "RMSD": "Root-mean-square deviation — typical error magnitude, in data units.",
    "MAE":  "Mean absolute error — average size of the differences.",
    "MSE":  "Mean squared error — penalises large errors more heavily.",
}


class ComparisonDetailsDialog(QDialog):
    """Show every metric for one comparison and let the user place each on the plot."""

    def __init__(self, entry, results, parent=None):
        super().__init__(parent)
        self._entry = entry
        self._results = results
        self.setWindowTitle("Comparison details")
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        # ── What is being compared ────────────────────────────────────
        ref = self._fmt(entry.get("refData"))
        cmp = self._fmt(entry.get("cmpData"))
        header = QLabel(f"<b>Compare</b>&nbsp; {cmp} &nbsp;<b>vs</b>&nbsp; {ref}")
        header.setWordWrap(True)
        root.addWidget(header)

        if results:
            n = QLabel(f"Based on {results['n']:,} paired, non-empty values.")
        else:
            n = QLabel("Select a numeric Reference and Compare column with matching "
                       "row counts to compute metrics.")
        n.setWordWrap(True)
        n.setStyleSheet("color: #8a93a6; font-size: 12px;")
        root.addWidget(n)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: palette(mid);")
        root.addWidget(line)

        # ── Per-metric rows ───────────────────────────────────────────
        self._addChecks = {}
        grp = QGroupBox("Metrics")
        grid = QGridLayout(grp)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(8)
        grid.addWidget(self._colHeader("Metric"), 0, 0)
        grid.addWidget(self._colHeader("Value"),  0, 1)
        grid.addWidget(self._colHeader("On plot"), 0, 2)
        grid.addWidget(self._colHeader(""),        0, 3)

        for r, key in enumerate(("RMSD", "MAE", "MSE"), start=1):
            cfg = entry["metrics"][key]

            name = QLabel(f"<b>{key}</b>")
            name.setToolTip(_METRIC_HELP[key])
            grid.addWidget(name, r, 0)

            if results:
                dec = cfg["settings"].get("decimals", 4)
                unit = cfg["settings"].get("unit", "")
                txt = f"{results[key]:.{dec}f}" + (f" {unit}" if unit else "")
            else:
                txt = "—"
            val = QLabel(txt)
            val.setStyleSheet("font-family: monospace;")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(val, r, 1)

            cb = QCheckBox()
            cb.setChecked(cfg["add"])
            cb.setEnabled(results is not None)
            self._addChecks[key] = cb
            cbCell = QHBoxLayout(); cbCell.addStretch(); cbCell.addWidget(cb); cbCell.addStretch()
            from PySide6.QtWidgets import QWidget
            cbWidget = QWidget(); cbWidget.setLayout(cbCell)
            grid.addWidget(cbWidget, r, 2)

            styleBtn = QPushButton("Style…")
            styleBtn.setToolTip(f"Position and format the {key} label on the plot")
            styleBtn.clicked.connect(lambda _=False, k=key: self._editStyle(k))
            grid.addWidget(styleBtn, r, 3)

        root.addWidget(grp)

        hint = QLabel("Tick “On plot” to stamp a metric onto the figure as a label; "
                      "use Style… to move or format it.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        root.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _colHeader(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8a93a6; font-size: 12px; font-weight: 600;")
        return lbl

    @staticmethod
    def _fmt(spec):
        if not spec:
            return "<i>(unset)</i>"
        label, col = spec
        return f"{col} [{label}]"

    def _editStyle(self, key):
        settings = self._entry["metrics"][key]["settings"]
        dlg = MetricAnnotationDialog(settings, key, self)
        if dlg.exec():
            settings.update(dlg.resultValues())

    def accept(self):
        for key, cb in self._addChecks.items():
            self._entry["metrics"][key]["add"] = cb.isChecked()
        super().accept()
