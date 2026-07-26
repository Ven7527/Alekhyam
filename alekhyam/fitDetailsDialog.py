from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QCheckBox, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .computedColumnDialog import buildFunctionPalette, columnRef, insertSnippet
from .curveFit import extractParameters
from .widgets import colorPicker


class FitDetailsDialog(QDialog):
    """Edit a fit's model, run it, and control how the fitted curve is drawn.

    Uses the same formula-builder interface as the New-column dialog: an
    <b>x</b> chip, the shared function/operator palette, and live feedback.
    `fitFn()` returns (result, error) using the row's currently selected X/Y
    columns and the model / p0 stored on the entry.
    """

    def __init__(self, entry, fitFn, columns=(), parent=None):
        super().__init__(parent)
        self._entry = entry
        self._fitFn = fitFn
        self._columns = list(columns)   # covariate columns usable in the model
        self.setWindowTitle("Curve fit")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        # ── Model ─────────────────────────────────────────────────────
        root.addWidget(QLabel("Model  (use <b>x</b>, free parameters like a, b, c, "
                              "and any column names)"))
        modelRow = QHBoxLayout()
        modelRow.addWidget(QLabel("y ="))
        self._modelEdit = QLineEdit(entry.get("model", ""))
        self._modelEdit.setPlaceholderText("a * exp(-b * x) + c")
        self._modelEdit.setStyleSheet("font-family: monospace; padding: 6px;")
        self._modelEdit.textChanged.connect(self._onModelChanged)
        modelRow.addWidget(self._modelEdit, 1)
        root.addLayout(modelRow)

        # ── Insert x / columns  +  function palette (shared with New column) ──
        varGroup = QGroupBox("Variable && columns  —  click to insert")
        varLayout = QHBoxLayout(varGroup)
        varLayout.setContentsMargins(8, 8, 8, 8)
        varLayout.setSpacing(4)
        chipCss = (
            "QPushButton { border: 1px solid palette(mid); border-radius: 4px;"
            " padding: 2px 12px; font-family: monospace; }"
            "QPushButton:hover { border-color: palette(highlight); }"
        )
        for name in ["x", *self._columns]:
            chip = QPushButton(name)
            chip.setFixedHeight(26)
            chip.setStyleSheet(chipCss)
            snippet = "x" if name == "x" else columnRef(name)
            chip.clicked.connect(lambda _=False, s=snippet: self._insert(s, 0))
            varLayout.addWidget(chip)
        varLayout.addStretch()
        root.addWidget(varGroup)

        root.addWidget(buildFunctionPalette(self._insert))

        # ── Live parameter feedback ───────────────────────────────────
        self._paramLabel = QLabel()
        self._paramLabel.setWordWrap(True)
        self._paramLabel.setMinimumHeight(20)
        self._paramLabel.setStyleSheet("font-size: 11px; padding: 2px;")
        root.addWidget(self._paramLabel)

        guessRow = QHBoxLayout()
        guessRow.addWidget(QLabel("Initial guesses"))
        self._p0Edit = QLineEdit(entry.get("p0", ""))
        self._p0Edit.setPlaceholderText("optional — comma-separated, one per parameter")
        guessRow.addWidget(self._p0Edit, 1)
        self._runBtn = QPushButton("Run fit")
        self._runBtn.clicked.connect(self._runFit)
        guessRow.addWidget(self._runBtn)
        root.addLayout(guessRow)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: palette(mid);")
        root.addWidget(line)

        # ── Results (populated by _runFit) ────────────────────────────
        self._resultsBox = QGroupBox("Result")
        self._resultsLayout = QVBoxLayout(self._resultsBox)
        self._resultsLayout.setSpacing(6)
        self._statusLabel = QLabel("Press “Run fit” to fit the model.")
        self._statusLabel.setWordWrap(True)
        self._resultsLayout.addWidget(self._statusLabel)
        root.addWidget(self._resultsBox)

        # ── Overlay controls ──────────────────────────────────────────
        self._overlayCheck = QCheckBox("Overlay the fitted curve on the plot")
        self._overlayCheck.setChecked(entry.get("overlay", True))
        root.addWidget(self._overlayCheck)

        self._eqCheck = QCheckBox("Show the fitted equation in the legend")
        self._eqCheck.setChecked(entry.get("showEq", True))
        root.addWidget(self._eqCheck)

        colorRow = QHBoxLayout()
        colorRow.addWidget(QLabel("Curve color"))
        colorContainer, self._getColor, _ = colorPicker(entry.get("color"))
        colorRow.addWidget(colorContainer)
        colorRow.addStretch()
        cw = QWidget(); cw.setLayout(colorRow)
        root.addWidget(cw)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Initial state: show detected parameters, and auto-run if a model
        # is already present.
        self._onModelChanged()
        if entry.get("model", "").strip():
            self._runFit()

    # ------------------------------------------------------------------

    def _insert(self, snippet, cursorBack):
        insertSnippet(self._modelEdit, snippet, cursorBack)

    def _onModelChanged(self):
        expr = self._modelEdit.text().strip()
        if not expr:
            self._paramLabel.setText("The model uses x, any free parameters (a, b, c …), "
                                     "and column names.")
            self._paramLabel.setStyleSheet("color: #8a93a6; font-size: 12px; padding: 2px;")
            return
        from .computedColumnDialog import substituteColumns
        expr2, tokenMap = substituteColumns(expr)
        try:
            params = extractParameters(expr, columns=self._columns)
        except SyntaxError:
            self._paramLabel.setText("✗  Syntax error in model.")
            self._paramLabel.setStyleSheet("color: #c62828; font-size: 11px; padding: 2px;")
            return
        import ast
        referenced = set(tokenMap.values()) | {
            n.id for n in ast.walk(ast.parse(expr2, mode="eval"))
            if isinstance(n, ast.Name)
        }
        colsUsed = [c for c in self._columns if c in referenced]

        if params:
            text = "Parameters to fit:  " + ", ".join(params)
            if colsUsed:
                text += "     ·     Columns used:  " + ", ".join(colsUsed)
            self._paramLabel.setText(text)
            self._paramLabel.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 2px;")
        else:
            self._paramLabel.setText("No free parameters yet — add names like a, b, c to fit.")
            self._paramLabel.setStyleSheet("color: #b26a00; font-size: 11px; padding: 2px;")

    def _clearResults(self):
        while self._resultsLayout.count():
            item = self._resultsLayout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _runFit(self):
        # Push the edited model / guesses onto the entry so fitFn sees them.
        self._entry["model"] = self._modelEdit.text().strip()
        self._entry["p0"] = self._p0Edit.text().strip()
        result, error = self._fitFn()

        self._clearResults()
        if error:
            lbl = QLabel(f"✗ {error}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #c62828;")
            self._resultsLayout.addWidget(lbl)
            return

        good = QLabel(f"✓ Converged.   R² = {result['r2']:.5f}")
        good.setStyleSheet("color: #2e7d32; font-weight: 600;")
        self._resultsLayout.addWidget(good)

        if result.get("warning"):
            warn = QLabel("⚠ " + result["warning"])
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #b26a00; font-size: 11px;")
            self._resultsLayout.addWidget(warn)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        for c, h in enumerate(("Parameter", "Value", "± 1σ")):
            hl = QLabel(h)
            hl.setStyleSheet("color: #8a93a6; font-size: 12px; font-weight: 600;")
            grid.addWidget(hl, 0, c)
        for r, (name, val, err) in enumerate(
            zip(result["paramNames"], result["popt"], result["perr"]), start=1
        ):
            grid.addWidget(QLabel(f"<b>{name}</b>"), r, 0)
            v = QLabel(f"{val:.6g}")
            v.setStyleSheet("font-family: monospace;")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(v, r, 1)
            e = QLabel("—" if err != err else f"{err:.3g}")
            e.setStyleSheet("font-family: monospace; color: #8a93a6;")
            grid.addWidget(e, r, 2)
        gridWidget = QWidget(); gridWidget.setLayout(grid)
        self._resultsLayout.addWidget(gridWidget)

        eqn = QLabel(f"<b>Fitted:</b> <code>y = {result['equation']}</code>")
        eqn.setWordWrap(True)
        eqn.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._resultsLayout.addWidget(eqn)

    def accept(self):
        self._entry["model"] = self._modelEdit.text().strip()
        self._entry["p0"] = self._p0Edit.text().strip()
        self._entry["overlay"] = self._overlayCheck.isChecked()
        self._entry["showEq"] = self._eqCheck.isChecked()
        self._entry["color"] = self._getColor()
        super().accept()
