import keyword
import re

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

# Function / constant namespace exposed to formulas. Everything here is a
# NumPy ufunc or constant — no builtins — so eval() with an empty __builtins__
# is safe against arbitrary code while still feeling like a spreadsheet.
FORMULA_NAMESPACE = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "arcsin": np.arcsin, "arccos": np.arccos, "arctan": np.arctan,
    "arctan2": np.arctan2, "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "exp": np.exp, "log": np.log, "log10": np.log10, "log2": np.log2,
    "sqrt": np.sqrt, "abs": np.abs, "mean": np.mean,
    "floor": np.floor, "ceil": np.ceil, "round": np.round,
    "minimum": np.minimum, "maximum": np.maximum,
    "pi": np.pi, "e": np.e,
}

_BACKTICK_RE = re.compile(r"`([^`]+)`")


def columnRef(name):
    """How to reference a column in a formula.

    A simple identifier that doesn't collide with a function/constant can be
    used bare; anything else (spaces, keywords, or names like ``sin``) must be
    backtick-quoted so it is unambiguously the column.
    """
    name = str(name)
    if (name.isidentifier() and not keyword.iskeyword(name)
            and name not in FORMULA_NAMESPACE):
        return name
    return f"`{name}`"


def substituteColumns(expr):
    """Replace every ```col name``` with a safe identifier token.

    Returns ``(rewritten_expr, {token: column_name})``. This lets column names
    with spaces, keywords, or function-name collisions be used in formulas that
    are otherwise evaluated as plain Python.
    """
    tokenMap = {}

    def repl(match):
        token = f"_bt{len(tokenMap)}_"
        tokenMap[token] = match.group(1)
        return token

    return _BACKTICK_RE.sub(repl, expr), tokenMap


def formulaNamespace(df):
    """Base namespace for a formula: functions/constants plus every column that
    can be referenced bare (a valid identifier that isn't a function name)."""
    ns = dict(FORMULA_NAMESPACE)
    for col in df.columns:
        col = str(col)
        if col.isidentifier() and col not in FORMULA_NAMESPACE:
            ns[col] = df[col].to_numpy()
    return ns


def evaluateFormula(df, expr):
    """Evaluate a spreadsheet-style formula against a dataframe's columns.

    Columns are referenced by name (backtick-quote names with spaces or that
    clash with a function). FORMULA_NAMESPACE provides functions and constants.
    Builtins are disabled so this cannot execute arbitrary code. Returns a
    numpy array (scalars are broadcast to the frame length).
    """
    expr2, tokenMap = substituteColumns(expr)
    namespace = formulaNamespace(df)
    columns = set(map(str, df.columns))
    for token, name in tokenMap.items():
        if name not in columns:
            raise ValueError(f"Unknown column: `{name}`")
        namespace[token] = df[name].to_numpy()
    result = eval(expr2, {"__builtins__": {}}, namespace)  # noqa: S307
    arr = np.asarray(result, dtype=float)
    if arr.ndim == 0:                       # scalar → broadcast to column length
        arr = np.full(len(df), float(arr))
    return arr


# Function-palette layout: (button label, snippet to insert, cursor-back offset)
_FUNCTIONS = [
    ("sin", "sin()", 1), ("cos", "cos()", 1), ("tan", "tan()", 1),
    ("arcsin", "arcsin()", 1), ("arccos", "arccos()", 1), ("arctan", "arctan()", 1),
    ("exp", "exp()", 1), ("log", "log()", 1), ("log10", "log10()", 1),
    ("sqrt", "sqrt()", 1), ("abs", "abs()", 1), ("mean", "mean()", 1),
    ("sinh", "sinh()", 1), ("cosh", "cosh()", 1), ("tanh", "tanh()", 1),
    ("floor", "floor()", 1), ("ceil", "ceil()", 1),
]
_OPERATORS = [
    ("+", " + ", 0), ("−", " - ", 0), ("×", " * ", 0), ("÷", " / ", 0),
    ("xⁿ", " ** ", 0), ("(", "(", 0), (")", ")", 0),
    ("π", "pi", 0), ("e", "e", 0),
]


def insertSnippet(lineEdit, snippet, cursorBack):
    """Insert `snippet` at the cursor of a QLineEdit, moving back `cursorBack`."""
    lineEdit.insert(snippet)
    if cursorBack:
        lineEdit.setCursorPosition(lineEdit.cursorPosition() - cursorBack)
    lineEdit.setFocus()


def buildFunctionPalette(insertFn, title="Functions && operators", perRow=8):
    """A grid of operator/function buttons that call insertFn(snippet, back).

    Shared by the New-column builder and the Curve-fit model editor so both
    offer the same palette.
    """
    group = QGroupBox(title)
    grid = QGridLayout(group)
    grid.setContentsMargins(8, 8, 8, 8)
    grid.setSpacing(4)
    for i, (lbl, snippet, back) in enumerate(_OPERATORS + _FUNCTIONS):
        btn = QPushButton(lbl)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda _=False, s=snippet, b=back: insertFn(s, b))
        grid.addWidget(btn, i // perRow, i % perRow)
    return group


class ComputedColumnDialog(QDialog):
    """Spreadsheet-style builder for a new column derived from a formula."""

    def __init__(self, dataFrames, parent=None):
        super().__init__(parent)
        self._dataFrames = dataFrames
        self.setWindowTitle("New computed column")
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        # ── Destination + name ────────────────────────────────────────
        topRow = QHBoxLayout()
        topRow.setSpacing(8)
        topRow.addWidget(QLabel("Add to file"))
        self.fileCombo = QComboBox()
        self.fileCombo.addItems(list(dataFrames.keys()))
        self.fileCombo.currentTextChanged.connect(self._onFileChanged)
        topRow.addWidget(self.fileCombo, 1)
        topRow.addWidget(QLabel("Name"))
        self.nameEdit = QLineEdit()
        self.nameEdit.setPlaceholderText("new_column")
        self.nameEdit.setMaximumWidth(160)
        topRow.addWidget(self.nameEdit)
        root.addLayout(topRow)

        # ── Formula field ─────────────────────────────────────────────
        root.addWidget(QLabel("Formula"))
        self.exprEdit = QLineEdit()
        self.exprEdit.setPlaceholderText("e.g.  sqrt(x**2 + y**2)   or   exp(-time) * amplitude")
        self.exprEdit.setStyleSheet("font-family: monospace; padding: 6px;")
        self.exprEdit.textChanged.connect(self._updatePreview)
        root.addWidget(self.exprEdit)

        # ── Columns (click to insert) ─────────────────────────────────
        colsGroup = QGroupBox("Columns  —  click to insert")
        colsLayout = QVBoxLayout(colsGroup)
        colsLayout.setContentsMargins(8, 8, 8, 8)
        self._colsRow = QWidget()
        self._colsRowLayout = QHBoxLayout(self._colsRow)
        self._colsRowLayout.setContentsMargins(0, 0, 0, 0)
        self._colsRowLayout.setSpacing(4)
        colsLayout.addWidget(self._colsRow)
        root.addWidget(colsGroup)

        # ── Functions & operators ─────────────────────────────────────
        root.addWidget(buildFunctionPalette(self._insert))

        # ── Live preview ──────────────────────────────────────────────
        self.previewLabel = QLabel("Preview appears here as you type.")
        self.previewLabel.setWordWrap(True)
        self.previewLabel.setMinimumHeight(34)
        self.previewLabel.setStyleSheet(
            "color: #8a93a6; font-size: 12px; padding: 2px;"
        )
        root.addWidget(self.previewLabel)

        # ── Buttons ───────────────────────────────────────────────────
        self._buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._buttonBox.button(QDialogButtonBox.Ok).setText("Add column")
        self._buttonBox.accepted.connect(self.accept)
        self._buttonBox.rejected.connect(self.reject)
        root.addWidget(self._buttonBox)

        self._onFileChanged(self.fileCombo.currentText())

    # ------------------------------------------------------------------

    def _currentDf(self):
        return self._dataFrames.get(self.fileCombo.currentText())

    def _onFileChanged(self, _label):
        # Rebuild the clickable column chips for the selected file.
        while self._colsRowLayout.count():
            item = self._colsRowLayout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        df = self._currentDf()
        if df is None:
            return
        for col in df.columns:
            chip = QPushButton(str(col))
            chip.setFixedHeight(26)
            chip.setStyleSheet(
                "QPushButton { border: 1px solid palette(mid); border-radius: 4px;"
                " padding: 2px 8px; } QPushButton:hover { border-color: palette(highlight); }"
            )
            # Insert the correct reference form (bare or backtick-quoted).
            chip.clicked.connect(lambda _=False, c=columnRef(col): self._insert(c, 0))
            self._colsRowLayout.addWidget(chip)
        self._colsRowLayout.addStretch()
        self._updatePreview()

    def _insert(self, snippet, cursorBack):
        insertSnippet(self.exprEdit, snippet, cursorBack)

    def _updatePreview(self):
        expr = self.exprEdit.text().strip()
        df = self._currentDf()
        okBtn = self._buttonBox.button(QDialogButtonBox.Ok)
        if not expr or df is None:
            self.previewLabel.setText("Preview appears here as you type.")
            self.previewLabel.setStyleSheet("color: #8a93a6; font-size: 12px; padding: 2px;")
            okBtn.setEnabled(True)
            return
        try:
            arr = evaluateFormula(df, expr)
            head = ", ".join(f"{v:.4g}" for v in np.asarray(arr, dtype=float)[:5])
            more = " …" if len(arr) > 5 else ""
            self.previewLabel.setText(f"✓  Result:  [{head}{more}]")
            self.previewLabel.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 2px;")
            okBtn.setEnabled(True)
        except Exception as exc:
            self.previewLabel.setText(f"✗  {type(exc).__name__}: {exc}")
            self.previewLabel.setStyleSheet("color: #c62828; font-size: 11px; padding: 2px;")
            okBtn.setEnabled(False)

    def values(self):
        return (
            self.fileCombo.currentText(),
            self.nameEdit.text().strip(),
            self.exprEdit.text().strip(),
        )
