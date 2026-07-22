import copy
import itertools
import json
import os

import numpy as np
import pandas as pd
from PySide6.QtCore import (
    QFileSystemWatcher, QPoint, QSettings, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .appResources import iconPath, resourceDir
from .icons import (
    aspectIcon, clipboardIcon, copyIcon, ellipseIcon, exportIcon, fitIcon,
    flipHIcon, flipVIcon, folderIcon, gearIcon, gridIcon, hLineIcon, imageIcon,
    minusIcon, openFileIcon, paletteIcon, plusIcon, ratioIcon, rectIcon,
    resetViewIcon, saveIcon, slidersIcon, templateIcon, trashIcon, vLineIcon,
)
from .plotCanvas import PlotCanvas, markerOptions, tabColors
from .computedColumnDialog import (
    ComputedColumnDialog, evaluateFormula, substituteColumns,
)
from .curveFit import fitCurve
from .fitDetailsDialog import FitDetailsDialog
from .fillStyleDialog import FillStyleDialog
from .comparisonDetailsDialog import ComparisonDetailsDialog
from .referenceLineStyleDialog import ReferenceLineStyleDialog
from .seriesStyleDialog import SeriesStyleDialog
from .tableModel import DataFrameModel
from .textAnnotationDialog import TextAnnotationDialog
from .widgets import colorPicker, iconButton, sliderSpinPair

previewRowLimit = 1000
seriesColumns   = ["", "", "X", "Y", "Type", ""]
_MAX_RECENT     = 8
_MAX_UNDO       = 20

_SUPPORTED_EXTS = (".csv", ".txt", ".npy", ".npz")
_FILE_DIALOG_FILTER = (
    "Data files (*.csv *.txt *.npy *.npz);;"
    "CSV Files (*.csv);;Text Files (*.txt);;"
    "NumPy Array (*.npy);;NumPy Archive (*.npz);;All Files (*)"
)


def _cssColor(color):
    """Resolve any matplotlib colour spec (e.g. 'tab:blue') to a '#rrggbb' hex
    string that Qt stylesheets understand. Falls back to the input unchanged."""
    try:
        from matplotlib.colors import to_hex
        return to_hex(color)
    except Exception:
        return color


def _arrayToFrame(arr, prefix=None):
    """Convert a numpy array into a DataFrame with sensible column names."""
    arr = np.asarray(arr)
    if arr.dtype.names:  # structured array — field names become columns
        return pd.DataFrame(arr)
    if arr.ndim == 1:
        return pd.DataFrame({prefix or "value": arr})
    if arr.ndim == 2:
        cols = [f"{prefix}_{i}" if prefix else f"col{i}" for i in range(arr.shape[1])]
        return pd.DataFrame(arr, columns=cols)
    raise ValueError(f"Unsupported array shape {arr.shape} (must be 1D or 2D)")


def _readDataFile(path):
    """Load a CSV, whitespace/delimited text, .npy, or .npz file into a DataFrame."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".txt"):
        return pd.read_csv(path, sep=None, engine="python")
    if ext == ".npy":
        return _arrayToFrame(np.load(path, allow_pickle=False))
    if ext == ".npz":
        archive = np.load(path, allow_pickle=False)
        if not archive.files:
            raise ValueError("NPZ archive contains no arrays")
        frames = [_arrayToFrame(archive[key], prefix=key) for key in archive.files]
        # Horizontal concat aligns by row index, padding shorter arrays with NaN.
        return pd.concat(frames, axis=1)
    raise ValueError(f"Unsupported file type: {ext}")

# Brand accent (fixed across light/dark). Neutrals use palette() so the whole
# UI follows the applied light/dark theme automatically.
_ACCENT = "#2e73b8"

# Qt QSS cannot draw a combo/spin arrow with the CSS border-triangle trick
# (it renders as a solid block), so real arrow images are used instead — the
# light/dark variant is chosen from the active theme when the sheet is built.
_APP_STYLE_TMPL = """
/* ── Group boxes as flat cards (no fragile outlines) ─────────── */
QGroupBox {
    font-weight: 700;
    border: none;
    border-radius: 10px;
    background: palette(alternate-base);
    margin-top: 6px;
    padding: 28px 12px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 14px;
    top: 9px;
    padding: 0;
    color: palette(text);
}

/* ── Tabs ────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid palette(mid);
    border-radius: 9px;
    top: -1px;
}
QTabBar::tab {
    padding: 7px 12px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: palette(text);
}
QTabBar::tab:hover        { background: palette(alternate-base); }
QTabBar::tab:selected {
    background: palette(base);
    border: 1px solid palette(mid);
    border-bottom: 2px solid __ACCENT__;
}

/* ── Text inputs / combos / spin boxes ───────────────────────── */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    border: 1px solid palette(mid);
    border-radius: 7px;
    padding: 4px 8px;
    background: palette(base);
    color: palette(text);
    selection-background-color: __ACCENT__;
    selection-color: white;
    min-height: 22px;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: palette(dark);
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus {
    border: 1px solid __ACCENT__;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
}
QComboBox::down-arrow { image: url(__DOWN__); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    border: 1px solid palette(mid);
    border-radius: 0;
    background: palette(base);
    selection-background-color: __ACCENT__;
    selection-color: white;
    outline: none;
    padding: 3px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 18px; border: none; border-top-right-radius: 6px;
    background: palette(alternate-base);
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 18px; border: none; border-bottom-right-radius: 6px;
    background: palette(alternate-base);
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: palette(mid);
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow     { image: url(__UP__);   width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url(__DOWN__); width: 10px; height: 10px; }

/* ── Generic buttons (primary/CTA buttons style themselves) ───── */
QPushButton {
    border: 1px solid palette(mid);
    border-radius: 7px;
    padding: 6px 14px;
    background: palette(button);
    color: palette(button-text);
}
QPushButton:hover    { background: palette(light); border-color: palette(dark); }
QPushButton:pressed  { background: palette(mid); }
QPushButton:disabled { color: palette(mid); border-color: palette(mid); }

/* ── Item views ──────────────────────────────────────────────── */
QListWidget, QTableView, QTableWidget {
    border: 1px solid palette(mid);
    border-radius: 9px;
    background: palette(base);
    alternate-background-color: palette(alternate-base);
    outline: none;
    gridline-color: palette(mid);
}
QListWidget::item, QTableView::item { padding: 3px; }
QListWidget::item:selected, QTableView::item:selected, QTableWidget::item:selected {
    background: __ACCENT__;
    color: white;
}
QHeaderView::section {
    background: palette(window);
    color: palette(text);
    border: none;
    border-bottom: 1px solid palette(mid);
    padding: 6px 6px;
    font-weight: 600;
}
QTableCornerButton::section { background: palette(window); border: none; }

/* ── Checkboxes / radios (indicator size for legibility) ─────── */
QCheckBox, QRadioButton { spacing: 7px; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }

/* ── Menus ───────────────────────────────────────────────────── */
QMenuBar { background: transparent; }
QMenuBar::item { padding: 5px 11px; border-radius: 6px; }
QMenuBar::item:selected { background: palette(alternate-base); }
/* Popup windows (menus, combo lists, tooltips) keep square corners: a
   rounded top-level popup shows broken opaque corners unless the window is
   translucent, which isn't reliable across platforms. */
QMenu {
    border: 1px solid palette(mid);
    border-radius: 0;
    padding: 5px;
    background: palette(base);
}
QMenu::item { padding: 6px 26px 6px 16px; border-radius: 6px; }
QMenu::item:selected { background: __ACCENT__; color: white; }
QMenu::separator { height: 1px; background: palette(mid); margin: 4px 8px; }

/* ── Slim scrollbars ─────────────────────────────────────────── */
QScrollBar:vertical   { background: transparent; width: 12px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:vertical   { background: palette(mid); border-radius: 5px; min-height: 32px; }
QScrollBar::handle:horizontal { background: palette(mid); border-radius: 5px; min-width: 32px; }
QScrollBar::handle:hover      { background: palette(dark); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ── Misc ────────────────────────────────────────────────────── */
QToolBar   { border: none; spacing: 5px; padding: 4px; }
QStatusBar { border-top: 1px solid palette(mid); }
QToolTip {
    border: 1px solid palette(mid);
    border-radius: 0;
    padding: 5px 9px;
    background: palette(base);
    color: palette(text);
}
"""


def _buildAppStyle(dark):
    """Fill the stylesheet template with the accent and theme-matched arrows."""
    suffix = "dark" if dark else "light"
    res = resourceDir()
    return (_APP_STYLE_TMPL
            .replace("__ACCENT__", _ACCENT)
            .replace("__DOWN__", (res / f"arrow_down_{suffix}.png").as_posix())
            .replace("__UP__",   (res / f"arrow_up_{suffix}.png").as_posix()))


class SeriesTable(QTableWidget):
    rowsReordered      = Signal(int, int)
    deleteRequested    = Signal()
    duplicateRequested = Signal()
    soloRequested      = Signal()
    showAllRequested   = Signal()

    def dropEvent(self, event):
        src = self.currentRow()
        tgt = self.indexAt(event.position().toPoint())
        tgtRow = tgt.row() if tgt.isValid() else self.rowCount() - 1
        event.ignore()
        if src >= 0 and tgtRow >= 0 and src != tgtRow:
            self.rowsReordered.emit(src, tgtRow)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.deleteRequested.emit()
            return
        if event.key() == Qt.Key_D and event.modifiers() & Qt.ControlModifier:
            self.duplicateRequested.emit()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Solo (show only this)", self.soloRequested.emit)
        menu.addAction("Show all", self.showAllRequested.emit)
        menu.addSeparator()
        menu.addAction("Duplicate", self.duplicateRequested.emit)
        menu.addAction("Remove", self.deleteRequested.emit)
        menu.exec(event.globalPos())


class _TableHeaderBar(QWidget):
    """A slim header strip that paints its column labels left-aligned, mirroring
    a table's live column geometry.

    Qt centres header text (ignoring setDefaultAlignment) as soon as
    ``QHeaderView::section`` is styled via a stylesheet, so the table's own
    header is hidden and this widget is placed directly above it instead. It
    reads ``columnViewportPosition``/``columnWidth`` on every paint, so the
    labels stay aligned with the columns even when a scrollbar appears or the
    panel is resized.
    """

    def __init__(self, table, labels, parent=None):
        super().__init__(parent)
        self._table = table
        self._labels = labels            # {column index: label text}
        self.setFixedHeight(30)
        table.horizontalHeader().hide()
        hh = table.horizontalHeader()
        hh.sectionResized.connect(lambda *_: self.update())
        hh.geometriesChanged.connect(self.update)
        table.horizontalScrollBar().valueChanged.connect(lambda *_: self.update())

    def paintEvent(self, _event):
        painter = QPainter(self)
        h = self.height()
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.palette().color(QPalette.WindowText))
        # Map each column's position through global coordinates so the labels
        # align with the cells regardless of where this strip sits in the layout.
        viewport = self._table.viewport()
        for col, text in self._labels.items():
            global_x = viewport.mapToGlobal(
                QPoint(self._table.columnViewportPosition(col), 0)).x()
            x = self.mapFromGlobal(QPoint(global_x, 0)).x()
            w = self._table.columnWidth(col)
            painter.drawText(x + 9, 0, max(w - 11, 10), h,
                             Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.setPen(self.palette().color(QPalette.Mid))
        painter.drawLine(0, h - 1, self.width(), h - 1)


class MainWindow(QMainWindow):
    def __init__(self, appIcon=None):
        super().__init__()
        self.setWindowTitle("Alekhyam")
        if appIcon:
            self.setWindowIcon(appIcon)
        self.resize(1340, 820)

        self._settings = QSettings("alekhyam", "Alekhyam")

        self.dataFrames         = {}
        self.seriesRows         = []
        self.referenceLineRows  = []
        self.fillRows           = []
        self.textAnnotationRows = []
        self.comparisonRows     = []
        self.fitRows            = []
        self.shapeRows          = []     # rectangles / ellipses / images
        self._imageCache        = {}     # id -> numpy image array (kept out of undo)
        self._legendLoc         = None   # None = named position; (x,y) = dragged
        self._idCounter         = itertools.count(1)
        # Live reload: watch loaded files and re-read them when they change.
        self._filePaths         = {}     # label -> absolute path
        self._liveReload        = True
        self._watcher           = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._onFileChanged)
        self._pendingReload     = set()
        self._reloadTimer       = QTimer(self)
        self._reloadTimer.setSingleShot(True)
        self._reloadTimer.setInterval(250)
        self._reloadTimer.timeout.connect(self._flushReloads)
        # WindowText is the primary text colour — reliably high-contrast in
        # both light and dark themes (ButtonText can be low-contrast on some).
        self._iconColor         = self.palette().color(QPalette.WindowText)
        self._uiIconSize        = 24
        self._autoPlot          = True
        self._undoStack         = []
        self._redoStack         = []

        self._darkTheme = self.palette().color(QPalette.Window).lightness() < 128
        self.setAcceptDrops(True)
        self.setStyleSheet(_buildAppStyle(self._darkTheme))
        self._buildUi()
        self._buildActionsAndMenus()
        self._installShortcuts()
        self.statusBar().showMessage("Open one or more data files to begin")

        # Restore window geometry, or open maximised on first launch.
        geom = self._settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
        splState = self._settings.value("splitter")
        if splState:
            self._splitter.restoreState(splState)

        # Restore export settings (a corrupted value must not block launch)
        try:
            self.exportDpiSpin.setValue(int(self._settings.value("exportDpi", 300)))
        except (TypeError, ValueError):
            pass
        fmt = self._settings.value("exportFormat", "PNG")
        idx = self.exportFormatCombo.findText(fmt)
        if idx >= 0:
            self.exportFormatCombo.setCurrentIndex(idx)
        self.exportTransparentCheck.setChecked(
            self._settings.value("exportTransparent", False, type=bool)
        )

        # Restore tab visibility choices
        for name in self._tabVisible:
            self._tabVisible[name] = self._settings.value(
                f"tabVisible/{name}", self._tabVisible[name], type=bool
            )
        if not any(self._tabVisible.values()):
            self._tabVisible["series"] = True
        self._rebuildTabWidget()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _buildUi(self):
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self._buildControlPanel())

        self.canvas = PlotCanvas()
        self.canvas.annotationDragged.connect(self._onAnnotationDragged)
        self.canvas.referenceLineDragged.connect(self._onReferenceLineDragged)
        self.canvas.metricDragged.connect(self._onMetricDragged)
        self.canvas.legendDragged.connect(self._onLegendDragged)
        self.canvas.shapeChanged.connect(self._onShapeChanged)
        self.canvas.shapeRotated.connect(self._onShapeRotated)
        self.canvas.shapeSelected.connect(self._onShapeSelected)
        self.canvas.shapeDeleteRequested.connect(self._onShapeDeleteRequested)
        self.canvas.shapeDuplicateRequested.connect(self._duplicateShape)
        self.canvas.shapeNudgeRequested.connect(self._onShapeNudge)
        self.canvas.shapeRaiseRequested.connect(lambda sid: self._reorderShape(sid, "front"))
        self.canvas.shapeLowerRequested.connect(lambda sid: self._reorderShape(sid, "back"))
        self.canvas.plotRightClicked.connect(self._onPlotRightClicked)
        self.canvas.legendItemPicked.connect(self._onLegendItemPicked)
        # Rotated shapes are pinned in display space, so redraw them (debounced)
        # after the plot area is resized to keep them correct.
        self._resizeReplot = QTimer(self)
        self._resizeReplot.setSingleShot(True)
        self._resizeReplot.setInterval(120)
        self._resizeReplot.timeout.connect(lambda: self.drawPlot())
        self.canvas.canvas.mpl_connect("resize_event", self._onCanvasResize)
        self._splitter.addWidget(self.canvas)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([500, 840])
        self.setCentralWidget(self._splitter)

        resetAct = QAction(resetViewIcon(self._iconColor), "Reset view", self.canvas.toolbar)
        resetAct.setToolTip("Reset plot to current settings (undo zoom/pan)")
        resetAct.triggered.connect(lambda: self.drawPlot(_force=True))
        self.canvas.toolbar.addAction(resetAct)

    def _buildControlPanel(self):
        panel = QWidget()
        panel.setMinimumWidth(460)
        panel.setMaximumWidth(560)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        c = self._iconColor
        # Tab definitions: (internal key, display label, icon). Order follows the
        # workflow: pick data → label the axes → style it → advanced → export.
        self._tabDefs = [
            ("series",   "Data & Series",  folderIcon(c)),
            ("axes",     "Axes & Labels",  slidersIcon(c)),
            ("style",    "Plot Style",     paletteIcon(c)),
            ("advanced", "Advanced",       fitIcon(c)),
            ("export",   "Export",         exportIcon(c)),
        ]
        # Build each tab widget exactly once and cache
        self._tabWidgets = {
            "series":   self._buildDataTab(),
            "axes":     self._buildAxesTab(),
            "style":    self._buildStyleTab(),
            "advanced": self._buildAdvancedTab(),
            "export":   self._buildExportTab(),
        }
        self._tabVisible = {
            "series":   True,
            "axes":     True,
            "style":    True,
            "advanced": True,
            "export":   True,
        }

        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(self._uiIconSize, self._uiIconSize))
        self._rebuildTabWidget()

        # Corner button to show/hide individual tabs
        cornerBtn = QPushButton()
        cornerBtn.setIcon(slidersIcon(c))
        cornerBtn.setIconSize(QSize(13, 13))
        cornerBtn.setFlat(True)
        cornerBtn.setFixedSize(22, 22)
        cornerBtn.setToolTip("Show / hide tabs")
        cornerBtn.clicked.connect(self._showTabVisibilityMenu)
        self.tabs.setCornerWidget(cornerBtn, Qt.TopRightCorner)

        layout.addWidget(self.tabs)

        # Bottom row: Auto toggle + Plot button
        bottomRow = QHBoxLayout()
        bottomRow.setSpacing(8)

        self.autoPlotCheck = QCheckBox("Auto")
        self.autoPlotCheck.setChecked(True)
        self.autoPlotCheck.setToolTip("Re-plot automatically on every change")
        self.autoPlotCheck.toggled.connect(self._onAutoPlotToggled)
        bottomRow.addWidget(self.autoPlotCheck)

        self.plotButton = QPushButton("  Plot")
        from PySide6.QtWidgets import QStyle as _QStyle
        self.plotButton.setIcon(self.style().standardIcon(_QStyle.SP_MediaPlay))
        self.plotButton.setIconSize(QSize(16, 16))
        self.plotButton.clicked.connect(lambda: self.drawPlot(_force=True))
        self.plotButton.setEnabled(False)
        self.plotButton.setFixedHeight(38)
        self.plotButton.setCursor(Qt.PointingHandCursor)
        self.plotButton.setStyleSheet("""
            QPushButton {
                background-color: #2e73b8;
                color: white;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 600;
                border: none;
                padding: 0 16px;
            }
            QPushButton:hover    { background-color: #3a86d0; }
            QPushButton:pressed  { background-color: #255f99; }
            QPushButton:disabled { background-color: palette(mid); color: palette(midlight); }
        """)
        bottomRow.addWidget(self.plotButton, 1)

        self._copyBtn = iconButton(
            clipboardIcon(self._iconColor),
            "Copy current plot as PNG to clipboard", diameter=38)
        self._copyBtn.setEnabled(False)
        self._copyBtn.clicked.connect(self._copyPlotToClipboard)
        bottomRow.addWidget(self._copyBtn)

        layout.addLayout(bottomRow)
        return panel

    # ---- Table helpers --------------------------------------------------

    def _tightCells(self, table):
        """Drop the inherited 3px item padding so cell widgets (combo boxes,
        the gear button) sit centred in the row instead of overflowing it, and
        turn off the table's own scrollbar — the tab scrolls as a whole."""
        table.setStyleSheet("QTableView::item { padding: 0px; }")
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _autoSizeTable(self, table, empty_height=60):
        """Fix a table's height to its contents so it grows with its rows and
        the enclosing tab provides a single scrollbar.

        Uses ``isHidden()``/``sizeHint()`` rather than ``isVisible()``/``height()``
        so the result is correct even when this runs before the window is first
        shown (``isVisible()`` is False until then, which would drop the header)."""
        header = table.horizontalHeader()
        height = 0 if header.isHidden() else header.sizeHint().height()
        if table.rowCount() == 0:
            height += empty_height
        else:
            for r in range(table.rowCount()):
                height += table.rowHeight(r)
        table.setFixedHeight(height + 2 * table.frameWidth() + 2)

    # ---- Data tab -------------------------------------------------------

    def _buildDataTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── 1. Loaded files (compact) ─────────────────────────────────
        filesGroup = QGroupBox("Data files")
        filesLayout = QVBoxLayout(filesGroup)
        filesLayout.setSpacing(6)
        self.filesList = QListWidget()
        self.filesList.setFixedHeight(70)
        self.filesList.currentItemChanged.connect(self._onPreviewFileChanged)
        filesLayout.addWidget(self.filesList)
        filesBtnRow = QHBoxLayout()
        filesBtnRow.setSpacing(6)
        self.openFileButton = QPushButton("  Open…")
        self.openFileButton.setIcon(openFileIcon(self._iconColor))
        self.openFileButton.clicked.connect(self.openCsv)
        self._computedColBtn = QPushButton("New column…")
        self._computedColBtn.setToolTip("Add a new column from a formula")
        self._computedColBtn.setEnabled(False)
        self._computedColBtn.clicked.connect(self._addComputedColumn)
        self._previewBtn = QPushButton("Preview")
        self._previewBtn.setCheckable(True)
        self._previewBtn.setToolTip("Show / hide the raw data preview")
        self._previewBtn.setEnabled(False)
        self._previewBtn.toggled.connect(lambda on: self.previewTable.setVisible(on))
        self._statsBtn = QPushButton("Stats")
        self._statsBtn.setToolTip("Per-column stats for the selected file")
        self._statsBtn.setEnabled(False)
        self._statsBtn.clicked.connect(self._showColumnStats)
        filesBtnRow.addWidget(self.openFileButton)
        filesBtnRow.addWidget(self._computedColBtn)
        filesBtnRow.addWidget(self._previewBtn)
        filesBtnRow.addWidget(self._statsBtn)
        filesBtnRow.addStretch()
        self._clearFilesBtn = iconButton(
            trashIcon(self._iconColor), "Remove all loaded files and their series")
        self._clearFilesBtn.setEnabled(False)
        self._clearFilesBtn.clicked.connect(self.clearLoadedFiles)
        filesBtnRow.addWidget(self._clearFilesBtn)
        filesLayout.addLayout(filesBtnRow)
        layout.addWidget(filesGroup)

        # ── Data preview (hidden until toggled) ───────────────────────
        self.previewTable = QTableView()
        self.previewTable.setModel(DataFrameModel())
        self.previewTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.previewTable.setAlternatingRowColors(True)
        self.previewTable.setMaximumHeight(150)
        self.previewTable.horizontalHeader().setStretchLastSection(True)
        self.previewTable.setVisible(False)
        layout.addWidget(self.previewTable)

        # ── 2. Series — the focus of this tab, fills remaining space ───
        seriesGroup = QGroupBox("Series")
        seriesLayout = QVBoxLayout(seriesGroup)
        seriesLayout.setSpacing(6)

        self.seriesTable = SeriesTable(0, len(seriesColumns))
        self.seriesTable.setHorizontalHeaderLabels(seriesColumns)
        hdr = self.seriesTable.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)    # show
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)    # color swatch
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)  # X
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)  # Y
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)    # type
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)    # gear
        self.seriesTable.setColumnWidth(0, 32)
        self.seriesTable.setColumnWidth(1, 28)
        self.seriesTable.setColumnWidth(4, 96)
        self.seriesTable.setColumnWidth(5, 40)
        self.seriesTable.verticalHeader().setVisible(False)
        self.seriesTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.seriesTable.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.seriesTable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._tightCells(self.seriesTable)
        self.seriesTable.setDragDropMode(QAbstractItemView.InternalMove)
        self.seriesTable.setDragEnabled(True)
        self.seriesTable.setAcceptDrops(True)
        self.seriesTable.setDropIndicatorShown(True)
        self.seriesTable.rowsReordered.connect(self._onSeriesRowsReordered)
        self.seriesTable.itemChanged.connect(self._onSeriesShowToggle)
        self.seriesTable.deleteRequested.connect(self._removeSelectedSeries)
        self.seriesTable.duplicateRequested.connect(self._duplicateSeries)
        self.seriesTable.soloRequested.connect(self._soloSelectedSeries)
        self.seriesTable.showAllRequested.connect(self._showAllSeries)
        seriesLayout.addWidget(_TableHeaderBar(self.seriesTable,
                                               {2: "X", 3: "Y", 4: "Type"}))
        seriesLayout.addWidget(self.seriesTable)

        btnRow = QHBoxLayout()
        btnRow.setSpacing(6)
        self.addSeriesButton = iconButton(plusIcon(self._iconColor), "Add series")
        self.addSeriesButton.clicked.connect(lambda: self._addSeriesEntry())
        self.addSeriesButton.setEnabled(False)
        self.removeSeriesButton = iconButton(minusIcon(self._iconColor), "Remove selected")
        self.removeSeriesButton.clicked.connect(self._removeSelectedSeries)
        self.removeSeriesButton.setEnabled(False)
        self.dupSeriesButton = iconButton(copyIcon(self._iconColor), "Duplicate series")
        self.dupSeriesButton.clicked.connect(self._duplicateSeries)
        self.dupSeriesButton.setEnabled(False)
        self.addAllButton = QPushButton("Add all")
        self.addAllButton.setToolTip("Add a series for every numeric column")
        self.addAllButton.setEnabled(False)
        self.addAllButton.clicked.connect(self._addAllColumns)
        self.paletteButton = iconButton(paletteIcon(self._iconColor),
                                        "Apply a colour palette to all series")
        self.paletteButton.setEnabled(False)
        palMenu = QMenu(self.paletteButton)
        for pname in ["Default"] + list(self._PALETTE_MAPS):
            palMenu.addAction(pname, lambda p=pname: self._applyPalette(p))
        self.paletteButton.setMenu(palMenu)
        self.paletteButton.setStyleSheet(
            self.paletteButton.styleSheet()
            + "QPushButton::menu-indicator{image:none;width:0px;}")
        btnRow.addWidget(self.addSeriesButton)
        btnRow.addWidget(self.removeSeriesButton)
        btnRow.addWidget(self.dupSeriesButton)
        btnRow.addWidget(self.paletteButton)
        btnRow.addWidget(self.addAllButton)
        btnRow.addStretch()
        hint = QLabel("drag rows to reorder")
        hint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        btnRow.addWidget(hint)
        self.clearSeriesButton = iconButton(trashIcon(self._iconColor), "Remove all series")
        self.clearSeriesButton.setEnabled(False)
        self.clearSeriesButton.clicked.connect(self._clearSeries)
        btnRow.addWidget(self.clearSeriesButton)
        seriesLayout.addLayout(btnRow)

        layout.addWidget(seriesGroup)
        layout.addStretch()
        self._autoSizeTable(self.seriesTable)

        # One scroll for the whole tab: the series table grows with its rows
        # (rather than scrolling internally at a fixed size).
        scroll = QScrollArea()
        scroll.setWidget(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    # ---- Style tab ------------------------------------------------------

    def _iconToggle(self, icon=None, text=None, tooltip="", onToggle=None):
        """A compact checkable pill for an on/off plot option. The tooltip
        carries the full description so the control itself stays small."""
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setFixedHeight(34)
        if icon is not None:
            btn.setIcon(icon)
            btn.setIconSize(QSize(17, 17))
            btn.setFixedWidth(42)
        if text:
            btn.setText(text)
            btn.setMinimumWidth(50)
        btn.setStyleSheet(
            "QPushButton {"
            "  border: 1px solid palette(mid); border-radius: 8px;"
            "  background: palette(base); color: palette(text);"
            "  font-size: 12px; font-weight: 600; padding: 0 8px;"
            "}"
            "QPushButton:hover { border-color: #2e73b8; }"
            "QPushButton:checked {"
            "  background: rgba(46,115,184,0.16);"
            "  border: 1px solid #2e73b8; color: #2e73b8;"
            "}"
        )
        if onToggle is not None:
            btn.toggled.connect(onToggle)
        return btn

    def _buildStyleTab(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        appGroup = QGroupBox("Appearance")
        appLayout = QVBoxLayout(appGroup)
        appLayout.setSpacing(8)
        c = self._iconColor

        # Compact toggle "chips" instead of a tall stack of checkboxes — each
        # carries a tooltip with the full description (hover to read it).
        # Row 1: grid, reverse axes, log scales.
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self.gridCheckBox = self._iconToggle(
            icon=gridIcon(c), tooltip="Show grid",
            onToggle=lambda _: self.drawPlot())
        self.reverseXCheck = self._iconToggle(
            icon=flipHIcon(c), tooltip="Reverse X axis",
            onToggle=lambda _: self.drawPlot())
        self.reverseYCheck = self._iconToggle(
            icon=flipVIcon(c), tooltip="Reverse Y axis",
            onToggle=lambda _: self.drawPlot())
        self.xLogCheck = self._iconToggle(
            text="log x", tooltip="X axis — logarithmic scale",
            onToggle=lambda _: self.drawPlot())
        self.yLogCheck = self._iconToggle(
            text="log y", tooltip="Y axis — logarithmic scale",
            onToggle=lambda _: self.drawPlot())
        for b in (self.gridCheckBox, self.reverseXCheck, self.reverseYCheck,
                  self.xLogCheck, self.yLogCheck):
            row1.addWidget(b)
        row1.addStretch()
        appLayout.addLayout(row1)

        # Row 2: aspect toggles, then the width : height controls inline.
        row2 = QHBoxLayout(); row2.setSpacing(6)
        self.equalAspectCheck = self._iconToggle(
            icon=aspectIcon(c),
            tooltip="Equal aspect ratio  (1 data unit X = 1 Y)",
            onToggle=lambda _: self.drawPlot())
        self.boxAspectCheck = self._iconToggle(
            icon=ratioIcon(c), tooltip="Custom axes width : height ratio",
            onToggle=self._onBoxAspectToggled)
        row2.addWidget(self.equalAspectCheck)
        row2.addWidget(self.boxAspectCheck)

        boxRow = QHBoxLayout()
        boxRow.setContentsMargins(6, 0, 0, 0)
        boxRow.setSpacing(4)
        boxRow.addWidget(QLabel("W"))
        self.boxAspectW = QDoubleSpinBox()
        self.boxAspectW.setRange(0.1, 20.0)
        self.boxAspectW.setValue(4.0)
        self.boxAspectW.setDecimals(1)
        self.boxAspectW.setSingleStep(0.5)
        self.boxAspectW.setFixedWidth(58)
        self.boxAspectW.valueChanged.connect(lambda _: self.drawPlot())
        boxRow.addWidget(self.boxAspectW)
        boxRow.addWidget(QLabel(":"))
        self.boxAspectH = QDoubleSpinBox()
        self.boxAspectH.setRange(0.1, 20.0)
        self.boxAspectH.setValue(3.0)
        self.boxAspectH.setDecimals(1)
        self.boxAspectH.setSingleStep(0.5)
        self.boxAspectH.setFixedWidth(58)
        self.boxAspectH.valueChanged.connect(lambda _: self.drawPlot())
        boxRow.addWidget(self.boxAspectH)
        boxRow.addWidget(QLabel("H"))
        self.boxAspectWidget = QWidget()
        self.boxAspectWidget.setLayout(boxRow)
        self.boxAspectWidget.setEnabled(False)
        row2.addWidget(self.boxAspectWidget)
        row2.addStretch()
        appLayout.addLayout(row2)

        layout.addWidget(appGroup)

        refGroup = QGroupBox("Reference lines")
        refLayout = QVBoxLayout(refGroup)
        refLayout.setSpacing(4)

        self.referenceLineTable = QTableWidget(0, 4)
        self.referenceLineTable.setHorizontalHeaderLabels(["", "Axis", "Position", ""])
        rHdr = self.referenceLineTable.horizontalHeader()
        rHdr.setSectionResizeMode(0, QHeaderView.Fixed)
        rHdr.setSectionResizeMode(1, QHeaderView.Fixed)
        rHdr.setSectionResizeMode(2, QHeaderView.Stretch)
        rHdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.referenceLineTable.setColumnWidth(0, 32)
        self.referenceLineTable.setColumnWidth(1, 80)
        self.referenceLineTable.setColumnWidth(3, 40)
        self.referenceLineTable.verticalHeader().setVisible(False)
        self.referenceLineTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tightCells(self.referenceLineTable)
        self.referenceLineTable.itemChanged.connect(self._onReferenceLineShowToggle)
        refLayout.addWidget(_TableHeaderBar(self.referenceLineTable,
                                            {1: "Axis", 2: "Position"}))
        refLayout.addWidget(self.referenceLineTable)

        refBtnRow = QHBoxLayout()
        refBtnRow.setSpacing(4)
        addHBtn = iconButton(hLineIcon(self._iconColor), "Add horizontal line")
        addHBtn.clicked.connect(lambda: self._addReferenceLine("horizontal"))
        addVBtn = iconButton(vLineIcon(self._iconColor), "Add vertical line")
        addVBtn.clicked.connect(lambda: self._addReferenceLine("vertical"))
        rmLineBtn = iconButton(minusIcon(self._iconColor), "Remove selected line")
        rmLineBtn.clicked.connect(self._removeSelectedReferenceLine)
        clearLineBtn = iconButton(trashIcon(self._iconColor), "Remove all reference lines")
        clearLineBtn.clicked.connect(self._clearReferenceLines)
        refBtnRow.addWidget(addHBtn)
        refBtnRow.addWidget(addVBtn)
        refBtnRow.addWidget(rmLineBtn)
        refBtnRow.addStretch()
        refBtnRow.addWidget(clearLineBtn)
        refLayout.addLayout(refBtnRow)
        layout.addWidget(refGroup)

        # Fill bands
        fillGroup = QGroupBox("Fill bands")
        fillLayout = QVBoxLayout(fillGroup)
        fillLayout.setSpacing(4)

        self.fillTable = QTableWidget(0, 5)
        self.fillTable.setHorizontalHeaderLabels(["", "Axis", "Start", "End", ""])
        fHdr = self.fillTable.horizontalHeader()
        fHdr.setSectionResizeMode(0, QHeaderView.Fixed)
        fHdr.setSectionResizeMode(1, QHeaderView.Fixed)
        fHdr.setSectionResizeMode(2, QHeaderView.Stretch)
        fHdr.setSectionResizeMode(3, QHeaderView.Stretch)
        fHdr.setSectionResizeMode(4, QHeaderView.Fixed)
        self.fillTable.setColumnWidth(0, 32)
        self.fillTable.setColumnWidth(1, 80)
        self.fillTable.setColumnWidth(4, 40)
        self.fillTable.verticalHeader().setVisible(False)
        self.fillTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tightCells(self.fillTable)
        self.fillTable.itemChanged.connect(self._onFillShowToggle)
        fillLayout.addWidget(_TableHeaderBar(self.fillTable,
                                             {1: "Axis", 2: "Start", 3: "End"}))
        fillLayout.addWidget(self.fillTable)

        fillBtnRow = QHBoxLayout()
        fillBtnRow.setSpacing(4)
        addHFillBtn = iconButton(hLineIcon(self._iconColor), "Add horizontal fill")
        addHFillBtn.clicked.connect(lambda: self._addFill("horizontal"))
        addVFillBtn = iconButton(vLineIcon(self._iconColor), "Add vertical fill")
        addVFillBtn.clicked.connect(lambda: self._addFill("vertical"))
        rmFillBtn = iconButton(minusIcon(self._iconColor), "Remove selected fill")
        rmFillBtn.clicked.connect(self._removeSelectedFill)
        clearFillBtn = iconButton(trashIcon(self._iconColor), "Remove all fill bands")
        clearFillBtn.clicked.connect(self._clearFills)
        fillBtnRow.addWidget(addHFillBtn)
        fillBtnRow.addWidget(addVFillBtn)
        fillBtnRow.addWidget(rmFillBtn)
        fillBtnRow.addStretch()
        fillBtnRow.addWidget(clearFillBtn)
        fillLayout.addLayout(fillBtnRow)
        layout.addWidget(fillGroup)

        # Text annotations (moved here from the Axes & Labels tab)
        annGroup = QGroupBox("Text annotations")
        annLayout = QVBoxLayout(annGroup)
        annLayout.setSpacing(4)

        self.textAnnotationTable = QTableWidget(0, 4)
        self.textAnnotationTable.setHorizontalHeaderLabels(["", "Text", "Position", ""])
        tHdr = self.textAnnotationTable.horizontalHeader()
        tHdr.setSectionResizeMode(0, QHeaderView.Fixed)
        tHdr.setSectionResizeMode(1, QHeaderView.Stretch)
        tHdr.setSectionResizeMode(2, QHeaderView.Fixed)
        tHdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.textAnnotationTable.setColumnWidth(0, 32)
        self.textAnnotationTable.setColumnWidth(2, 90)
        self.textAnnotationTable.setColumnWidth(3, 40)
        self.textAnnotationTable.verticalHeader().setVisible(False)
        self.textAnnotationTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.textAnnotationTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tightCells(self.textAnnotationTable)
        self.textAnnotationTable.itemChanged.connect(self._onTextAnnotationShowToggle)
        annLayout.addWidget(_TableHeaderBar(self.textAnnotationTable,
                                            {1: "Text", 2: "Position"}))
        annLayout.addWidget(self.textAnnotationTable)

        annBtnRow = QHBoxLayout()
        annBtnRow.setSpacing(4)
        addAnnBtn = iconButton(plusIcon(self._iconColor), "Add text annotation")
        addAnnBtn.clicked.connect(self._addTextAnnotation)
        rmAnnBtn = iconButton(minusIcon(self._iconColor), "Remove selected annotation")
        rmAnnBtn.clicked.connect(self._removeSelectedTextAnnotation)
        clearAnnBtn = iconButton(trashIcon(self._iconColor), "Remove all annotations")
        clearAnnBtn.clicked.connect(self._clearTextAnnotations)
        annBtnRow.addWidget(addAnnBtn)
        annBtnRow.addWidget(rmAnnBtn)
        annBtnRow.addStretch()
        annBtnRow.addWidget(clearAnnBtn)
        annLayout.addLayout(annBtnRow)
        layout.addWidget(annGroup)

        # ── Shapes & images ──────────────────────────────────────────
        shapeGroup = QGroupBox("Shapes && images")
        shapeLayout = QVBoxLayout(shapeGroup)
        shapeLayout.setSpacing(4)

        self.shapeTable = QTableWidget(0, 3)
        self.shapeTable.setHorizontalHeaderLabels(["", "Type", ""])
        sHdr = self.shapeTable.horizontalHeader()
        sHdr.setSectionResizeMode(0, QHeaderView.Fixed)
        sHdr.setSectionResizeMode(1, QHeaderView.Stretch)
        sHdr.setSectionResizeMode(2, QHeaderView.Fixed)
        self.shapeTable.setColumnWidth(0, 32)
        self.shapeTable.setColumnWidth(2, 40)
        self.shapeTable.verticalHeader().setVisible(False)
        self.shapeTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.shapeTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tightCells(self.shapeTable)
        self.shapeTable.itemChanged.connect(self._onShapeShowToggle)
        self.shapeTable.itemSelectionChanged.connect(self._onShapeRowSelected)
        self.shapeTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.shapeTable.customContextMenuRequested.connect(self._shapeTableMenu)
        shapeLayout.addWidget(_TableHeaderBar(self.shapeTable, {1: "Type"}))
        shapeLayout.addWidget(self.shapeTable)

        shapeBtnRow = QHBoxLayout()
        shapeBtnRow.setSpacing(4)
        addShapeBtn = iconButton(rectIcon(self._iconColor), "Add a shape")
        shapeMenu = QMenu(addShapeBtn)
        for label, kind in [
            ("Rectangle", "rect"), ("Rounded rectangle", "roundrect"),
            ("Circle / ellipse", "ellipse"), ("Triangle", "triangle"),
            ("Pentagon", "pentagon"), ("Hexagon", "hexagon"), ("Star", "star"),
        ]:
            shapeMenu.addAction(label, lambda k=kind: self._addShape(k))
        addShapeBtn.setMenu(shapeMenu)
        addShapeBtn.setStyleSheet(
            addShapeBtn.styleSheet()
            + "QPushButton::menu-indicator{image:none;width:0px;}")
        addImageBtn = iconButton(imageIcon(self._iconColor), "Import an image")
        addImageBtn.clicked.connect(self._importImage)
        rmShapeBtn = iconButton(minusIcon(self._iconColor), "Remove selected shape")
        rmShapeBtn.clicked.connect(self._removeSelectedShape)
        clearShapeBtn = iconButton(trashIcon(self._iconColor), "Remove all shapes")
        clearShapeBtn.clicked.connect(self._clearShapes)
        for b in (addShapeBtn, addImageBtn, rmShapeBtn):
            shapeBtnRow.addWidget(b)
        shapeHint = QLabel("drag · handles resize · Ctrl locks · Delete removes")
        shapeHint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        shapeBtnRow.addSpacing(6)
        shapeBtnRow.addWidget(shapeHint)
        shapeBtnRow.addStretch()
        shapeBtnRow.addWidget(clearShapeBtn)
        shapeLayout.addLayout(shapeBtnRow)
        layout.addWidget(shapeGroup)

        layout.addStretch()
        for _t in (self.referenceLineTable, self.fillTable,
                   self.textAnnotationTable, self.shapeTable):
            self._autoSizeTable(_t)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    # ---- Axes & Labels tab ----------------------------------------------

    def _buildAxesTab(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Labels & limits (moved here from the Data tab) ────────────
        labelsGroup = QGroupBox("Labels && limits")
        labelsForm = QFormLayout(labelsGroup)
        labelsForm.setVerticalSpacing(7)
        labelsForm.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.titleEdit = QLineEdit();  self.titleEdit.setPlaceholderText("auto")
        self.titleEdit.editingFinished.connect(self.drawPlot)
        labelsForm.addRow("Title", self.titleEdit)
        self.xLabelEdit = QLineEdit(); self.xLabelEdit.setPlaceholderText("auto")
        self.xLabelEdit.editingFinished.connect(self.drawPlot)
        labelsForm.addRow("X label", self.xLabelEdit)
        self.yLabelEdit = QLineEdit(); self.yLabelEdit.setPlaceholderText("auto")
        self.yLabelEdit.editingFinished.connect(self.drawPlot)
        labelsForm.addRow("Y label", self.yLabelEdit)

        self.xMinEdit = QLineEdit(); self.xMinEdit.setPlaceholderText("min")
        self.xMaxEdit = QLineEdit(); self.xMaxEdit.setPlaceholderText("max")
        xRow = QHBoxLayout(); xRow.setSpacing(6)
        xRow.addWidget(self.xMinEdit); xRow.addWidget(self.xMaxEdit)
        labelsForm.addRow("X range", xRow)
        self.yMinEdit = QLineEdit(); self.yMinEdit.setPlaceholderText("min")
        self.yMaxEdit = QLineEdit(); self.yMaxEdit.setPlaceholderText("max")
        yRow = QHBoxLayout(); yRow.setSpacing(6)
        yRow.addWidget(self.yMinEdit); yRow.addWidget(self.yMaxEdit)
        labelsForm.addRow("Y range", yRow)
        for e in (self.xMinEdit, self.xMaxEdit, self.yMinEdit, self.yMaxEdit):
            e.editingFinished.connect(self.drawPlot)
        layout.addWidget(labelsGroup)

        # Font
        fontGroup = QGroupBox("Figure font")
        fontLayout = QFormLayout(fontGroup)
        fontLayout.setVerticalSpacing(6)
        self.fontFamilyCombo = QComboBox()
        self.fontFamilyCombo.setEditable(True)
        from matplotlib import font_manager as _fm
        families = sorted(set(f.name for f in _fm.fontManager.ttflist))
        self.fontFamilyCombo.addItems(families)
        idx = self.fontFamilyCombo.findText("DejaVu Serif")
        if idx >= 0:
            self.fontFamilyCombo.setCurrentIndex(idx)
        self.fontFamilyCombo.activated.connect(lambda _: self.drawPlot())
        self.fontFamilyCombo.lineEdit().editingFinished.connect(self.drawPlot)
        fontLayout.addRow("Family", self.fontFamilyCombo)
        layout.addWidget(fontGroup)

        # Tick labels
        ticksGroup = QGroupBox("Tick labels")
        ticksForm = QFormLayout(ticksGroup)
        ticksForm.setVerticalSpacing(6)
        xTSContainer, self._getXTickSize, self._setXTickSize = sliderSpinPair(6, 24, 11, step=1, decimals=0, onChange=lambda _: self.drawPlot())
        ticksForm.addRow("X label size", xTSContainer)
        xTCContainer, self._getXTickCount, self._setXTickCount = sliderSpinPair(2, 30,  8, step=1, decimals=0, onChange=lambda _: self.drawPlot())
        ticksForm.addRow("X tick count", xTCContainer)
        yTSContainer, self._getYTickSize, self._setYTickSize = sliderSpinPair(6, 24, 11, step=1, decimals=0, onChange=lambda _: self.drawPlot())
        ticksForm.addRow("Y label size", yTSContainer)
        yTCContainer, self._getYTickCount, self._setYTickCount = sliderSpinPair(2, 30,  8, step=1, decimals=0, onChange=lambda _: self.drawPlot())
        ticksForm.addRow("Y tick count", yTCContainer)
        layout.addWidget(ticksGroup)

        # Legend
        legendGroup = QGroupBox("Legend")
        legendForm = QFormLayout(legendGroup)
        legendForm.setVerticalSpacing(6)
        self.showLegendCheck = QCheckBox("Show legend")
        self.showLegendCheck.setChecked(True)
        self.showLegendCheck.toggled.connect(lambda _: self.drawPlot())
        legendForm.addRow(self.showLegendCheck)
        self.legendFrameCheck = QCheckBox("Show frame border")
        self.legendFrameCheck.setChecked(True)
        self.legendFrameCheck.toggled.connect(lambda _: self.drawPlot())
        legendForm.addRow(self.legendFrameCheck)
        self.legendPosCombo = QComboBox()
        self.legendPosCombo.addItems([
            "best", "upper right", "upper left", "lower left",
            "lower right", "center", "upper center", "lower center",
        ])
        self.legendPosCombo.currentIndexChanged.connect(lambda _: self.drawPlot())
        # `activated` fires only on user selection (not programmatic changes),
        # so picking a named position clears any dragged custom placement while
        # undo/template restores of the combo leave a dragged legend intact.
        self.legendPosCombo.activated.connect(
            lambda _: setattr(self, "_legendLoc", None))
        legendForm.addRow("Position", self.legendPosCombo)
        layout.addWidget(legendGroup)

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    # ---- Advanced tab (curve fitting + series comparison) ---------------

    def _buildAdvancedTab(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Curve fit ────────────────────────────────────────────────
        fitGroup = QGroupBox("Curve fit")
        fitLayout = QVBoxLayout(fitGroup)
        fitLayout.setSpacing(4)

        self.fitTable = QTableWidget(0, 4)
        self.fitTable.setHorizontalHeaderLabels(["X", "Y", "R²", ""])
        fHdr = self.fitTable.horizontalHeader()
        fHdr.setSectionResizeMode(0, QHeaderView.Stretch)
        fHdr.setSectionResizeMode(1, QHeaderView.Stretch)
        fHdr.setSectionResizeMode(2, QHeaderView.Fixed)
        fHdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.fitTable.setColumnWidth(2, 74)
        self.fitTable.setColumnWidth(3, 40)
        self.fitTable.verticalHeader().setVisible(False)
        self.fitTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.fitTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fitTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tightCells(self.fitTable)
        fitLayout.addWidget(_TableHeaderBar(self.fitTable,
                                            {0: "X", 1: "Y", 2: "R²"}))
        fitLayout.addWidget(self.fitTable)

        modelRow = QHBoxLayout()
        modelRow.setSpacing(4)
        self.addFitButton = iconButton(plusIcon(self._iconColor), "Add fit")
        self.addFitButton.clicked.connect(self._addFit)
        self.addFitButton.setEnabled(False)
        self.removeFitButton = iconButton(minusIcon(self._iconColor), "Remove selected")
        self.removeFitButton.clicked.connect(self._removeSelectedFit)
        self.removeFitButton.setEnabled(False)
        clearFitBtn = iconButton(trashIcon(self._iconColor), "Remove all fits")
        clearFitBtn.clicked.connect(self._clearFits)
        modelRow.addWidget(self.addFitButton)
        modelRow.addWidget(self.removeFitButton)
        modelRow.addSpacing(8)
        fitHint = QLabel("any model of x  ·  ⚙ to edit")
        fitHint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        modelRow.addWidget(fitHint)
        modelRow.addStretch()
        modelRow.addWidget(clearFitBtn)
        fitLayout.addLayout(modelRow)
        layout.addWidget(fitGroup)

        # ── Compare series ───────────────────────────────────────────
        cmpGroup = QGroupBox("Compare series")
        cmpLayout = QVBoxLayout(cmpGroup)
        cmpLayout.setSpacing(4)

        self.comparisonTable = QTableWidget(0, 4)
        self.comparisonTable.setHorizontalHeaderLabels(
            ["Reference", "Compare", "RMSD", ""]
        )
        cHdr = self.comparisonTable.horizontalHeader()
        cHdr.setSectionResizeMode(0, QHeaderView.Stretch)
        cHdr.setSectionResizeMode(1, QHeaderView.Stretch)
        cHdr.setSectionResizeMode(2, QHeaderView.Fixed)
        cHdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.comparisonTable.setColumnWidth(2, 84)
        self.comparisonTable.setColumnWidth(3, 40)
        self.comparisonTable.verticalHeader().setVisible(False)
        self.comparisonTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.comparisonTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.comparisonTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tightCells(self.comparisonTable)
        cmpLayout.addWidget(_TableHeaderBar(self.comparisonTable,
                                            {0: "Reference", 1: "Compare", 2: "RMSD"}))
        cmpLayout.addWidget(self.comparisonTable)

        btnRow = QHBoxLayout()
        btnRow.setSpacing(4)
        self.addComparisonButton = iconButton(plusIcon(self._iconColor), "Add comparison")
        self.addComparisonButton.clicked.connect(self._addComparison)
        self.addComparisonButton.setEnabled(False)
        self.removeComparisonButton = iconButton(minusIcon(self._iconColor), "Remove selected")
        self.removeComparisonButton.clicked.connect(self._removeSelectedComparison)
        self.removeComparisonButton.setEnabled(False)
        clearCmpBtn = iconButton(trashIcon(self._iconColor), "Remove all comparisons")
        clearCmpBtn.clicked.connect(self._clearComparisons)
        btnRow.addWidget(self.addComparisonButton)
        btnRow.addWidget(self.removeComparisonButton)
        btnRow.addSpacing(8)
        cmpHint = QLabel("RMSD · MAE · MSE  ·  ⚙ for details")
        cmpHint.setStyleSheet("color: #8a93a6; font-size: 12px;")
        btnRow.addWidget(cmpHint)
        btnRow.addStretch()
        btnRow.addWidget(clearCmpBtn)
        cmpLayout.addLayout(btnRow)
        layout.addWidget(cmpGroup)

        layout.addStretch()
        self._autoSizeTable(self.fitTable)
        self._autoSizeTable(self.comparisonTable)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        return scroll

    # ---- Export tab -----------------------------------------------------

    def _buildExportTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        fileGroup = QGroupBox("Save image")
        fileLayout = QFormLayout(fileGroup)
        fileLayout.setVerticalSpacing(8)

        fnRow = QHBoxLayout()
        fnRow.setSpacing(6)
        self.exportFilenameEdit = QLineEdit("plot")
        self.exportFilenameEdit.setPlaceholderText("plot")
        self.exportFilenameEdit.setMinimumWidth(60)
        fnRow.addWidget(self.exportFilenameEdit, 1)
        browseBtn = iconButton(folderIcon(self._iconColor),
                               "Browse for a location…", diameter=32)
        browseBtn.clicked.connect(self._browseExportPath)
        fnRow.addWidget(browseBtn, 0, Qt.AlignVCenter)
        fileLayout.addRow("Filename", fnRow)

        self.exportFormatCombo = QComboBox()
        self.exportFormatCombo.addItems(["PNG", "PDF", "SVG"])
        self.exportFormatCombo.currentIndexChanged.connect(self._onExportFormatChanged)
        fileLayout.addRow("Format", self.exportFormatCombo)

        self.exportDpiSpin = QSpinBox()
        self.exportDpiSpin.setRange(72, 600)
        self.exportDpiSpin.setValue(300)
        self.exportDpiSpin.setSingleStep(25)
        self.exportDpiSpin.setSuffix(" dpi")
        fileLayout.addRow("Resolution", self.exportDpiSpin)

        self.exportTransparentCheck = QCheckBox("Transparent background")
        self.exportTransparentCheck.toggled.connect(lambda _: self.drawPlot())
        fileLayout.addRow(self.exportTransparentCheck)

        layout.addWidget(fileGroup)

        self.saveButton = QPushButton("  Save plot")
        self.saveButton.setIcon(saveIcon(self._iconColor))
        self.saveButton.setIconSize(QSize(18, 18))
        self.saveButton.clicked.connect(self.exportPlot)
        self.saveButton.setEnabled(False)
        self.saveButton.setFixedHeight(40)
        self.saveButton.setCursor(Qt.PointingHandCursor)
        self.saveButton.setStyleSheet("""
            QPushButton {
                background-color: palette(base);
                border: 1px solid #2e73b8;
                border-radius: 9px;
                color: #2e73b8;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover   { background-color: rgba(46,115,184,0.10); }
            QPushButton:pressed { background-color: rgba(46,115,184,0.20); }
            QPushButton:disabled { color: palette(mid); border-color: palette(mid); }
        """)
        layout.addWidget(self.saveButton)

        self.exportDataButton = QPushButton("  Export plotted data (CSV)…")
        self.exportDataButton.setToolTip(
            "Save the plotted X/Y data (after filters and computed columns) to a CSV")
        self.exportDataButton.clicked.connect(self._exportData)
        layout.addWidget(self.exportDataButton)

        layout.addStretch()
        return tab

    # ---- Actions / menus / toolbar --------------------------------------

    def _buildActionsAndMenus(self):
        self.openAction = QAction(openFileIcon(self._iconColor), "&Open…", self)
        self.openAction.setShortcut(QKeySequence.Open)
        self.openAction.setToolTip("Open data file(s) — CSV, TXT, NPY, NPZ")
        self.openAction.triggered.connect(self.openCsv)

        self.clearFilesAction = QAction(trashIcon(self._iconColor), "&Clear loaded files", self)
        self.clearFilesAction.setToolTip("Remove all loaded files and their series")
        self.clearFilesAction.setEnabled(False)
        self.clearFilesAction.triggered.connect(self.clearLoadedFiles)

        self.exitAction = QAction("E&xit", self)
        self.exitAction.setShortcut(QKeySequence.Quit)
        self.exitAction.triggered.connect(self.close)

        self.saveProjectAction = QAction("&Save project…", self)
        self.saveProjectAction.setShortcut("Ctrl+S")
        self.saveProjectAction.setToolTip("Save data + all settings to a .plot file")
        self.saveProjectAction.triggered.connect(self._saveProject)

        self.openProjectAction = QAction("Open &project…", self)
        self.openProjectAction.setShortcut("Ctrl+Shift+O")
        self.openProjectAction.triggered.connect(lambda: self._openProject())

        self.undoAction = QAction("&Undo", self)
        self.undoAction.setShortcut(QKeySequence.Undo)
        self.undoAction.setEnabled(False)
        self.undoAction.triggered.connect(self.undo)

        self.redoAction = QAction("&Redo", self)
        self.redoAction.setShortcut(QKeySequence.Redo)
        self.redoAction.setEnabled(False)
        self.redoAction.triggered.connect(self.redo)

        aboutAction = QAction("&About", self)
        aboutAction.triggered.connect(self.showAbout)

        helpAction = QAction("&User guide", self)
        helpAction.setShortcut("F1")
        helpAction.setToolTip("Open the built-in user guide")
        helpAction.triggered.connect(self._showHelp)

        self.copyPlotAction = QAction(clipboardIcon(self._iconColor), "&Copy plot", self)
        self.copyPlotAction.setShortcut("Ctrl+Shift+C")
        self.copyPlotAction.setToolTip("Copy current plot as PNG to clipboard")
        self.copyPlotAction.setEnabled(False)
        self.copyPlotAction.triggered.connect(self._copyPlotToClipboard)

        self.saveTemplateAction = QAction(templateIcon(self._iconColor), "Save template…", self)
        self.saveTemplateAction.setToolTip("Save current axis / style settings as a reusable template")
        self.saveTemplateAction.triggered.connect(self._saveTemplate)

        self.loadTemplateAction = QAction(templateIcon(self._iconColor), "Load template…", self)
        self.loadTemplateAction.setToolTip("Load a saved template and apply its settings")
        self.loadTemplateAction.triggered.connect(self._loadTemplate)

        # File menu
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction(self.openAction)
        self._recentMenu = fileMenu.addMenu("Recent files")
        self._rebuildRecentFilesMenu()
        fileMenu.addSeparator()
        fileMenu.addAction(self.openProjectAction)
        fileMenu.addAction(self.saveProjectAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.saveTemplateAction)
        fileMenu.addAction(self.loadTemplateAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.clearFilesAction)
        fileMenu.addAction(self.exitAction)

        # Edit menu
        editMenu = self.menuBar().addMenu("&Edit")
        editMenu.addAction(self.undoAction)
        editMenu.addAction(self.redoAction)
        editMenu.addSeparator()
        editMenu.addAction(self.copyPlotAction)

        # View menu
        viewMenu = self.menuBar().addMenu("&View")
        iconSizeMenu = viewMenu.addMenu("Icon size")
        sizeGroup = QActionGroup(self)
        sizeGroup.setExclusive(True)
        for label, size in [("Small (18)", 18), ("Medium (24)", 24),
                             ("Large (30)", 30), ("Extra large (38)", 38)]:
            act = QAction(label, self, checkable=True)
            act.setChecked(size == self._uiIconSize)
            act.triggered.connect(lambda checked, s=size: self._setUiIconSize(s))
            sizeGroup.addAction(act)
            iconSizeMenu.addAction(act)

        viewMenu.addSeparator()
        reloadAction = QAction("&Reload files now", self)
        reloadAction.setShortcut("Ctrl+R")
        reloadAction.triggered.connect(self.reloadAllFiles)
        viewMenu.addAction(reloadAction)
        liveAction = QAction("Auto-reload changed files", self, checkable=True)
        liveAction.setChecked(self._liveReload)
        liveAction.toggled.connect(self._setLiveReload)
        viewMenu.addAction(liveAction)

        shortcutsAction = QAction("&Keyboard shortcuts", self)
        shortcutsAction.setShortcut("Shift+?")
        shortcutsAction.triggered.connect(self._showShortcuts)

        helpMenu = self.menuBar().addMenu("&Help")
        helpMenu.addAction(helpAction)
        helpMenu.addAction(shortcutsAction)
        helpMenu.addSeparator()
        helpMenu.addAction(aboutAction)

    def _installShortcuts(self):
        # Ctrl+1..9 jump to the Nth visible tab.
        for i in range(1, 10):
            sc = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc.activated.connect(lambda n=i: self._switchToVisibleTab(n - 1))
        QShortcut(QKeySequence("?"), self).activated.connect(self._showShortcuts)

    def _switchToVisibleTab(self, index):
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    _SHORTCUTS = [
        ("Open file(s)", "Ctrl+O"), ("Save project", "Ctrl+S"),
        ("Open project", "Ctrl+Shift+O"), ("Copy chart to clipboard", "Ctrl+Shift+C"),
        ("Undo / Redo", "Ctrl+Z / Ctrl+Y"), ("Switch to tab 1–5", "Ctrl+1 … Ctrl+5"),
        ("Remove selected series / shape", "Delete"),
        ("Duplicate selected series / shape", "Ctrl+D"),
        ("Nudge selected shape", "Arrow keys"),
        ("Lock aspect while resizing a shape", "Hold Ctrl"),
        ("Snap while dragging", "on by default — hold Alt to disable"),
        ("User guide", "F1"), ("This shortcuts sheet", "?"), ("Quit", "Ctrl+Q"),
    ]

    def _showShortcuts(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard shortcuts")
        layout = QVBoxLayout(dlg)
        table = QTableWidget(len(self._SHORTCUTS), 2)
        table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for r, (action, keys) in enumerate(self._SHORTCUTS):
            table.setItem(r, 0, QTableWidgetItem(action))
            table.setItem(r, 1, QTableWidgetItem(keys))
        table.resizeRowsToContents()
        table.setMinimumWidth(460)
        table.setMinimumHeight(min(430, 40 + 30 * len(self._SHORTCUTS)))
        layout.addWidget(table)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        layout.addWidget(bb)
        dlg.exec()

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def openCsv(self):
        lastDir = self._settings.value("lastDir", "")
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open data file", lastDir, _FILE_DIALOG_FILTER
        )
        if not paths:
            return
        self._settings.setValue("lastDir", os.path.dirname(paths[0]))

        loadedAny = any(self._loadFile(p) for p in paths)
        if loadedAny:
            self._postFileLoad()

    def _loadFile(self, path):
        try:
            df = _readDataFile(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to open file", f"{path}\n{exc}")
            return False
        if df.empty or len(df.columns) == 0:
            QMessageBox.warning(self, "Empty file", f"{path} has no data, skipping.")
            return False
        label = self._makeFileLabel(path)
        self.dataFrames[label] = df
        item = QListWidgetItem(f"{label}  ({len(df)}×{len(df.columns)})")
        item.setData(Qt.UserRole, label)
        self.filesList.addItem(item)
        self._addToRecentFiles(path)
        self._filePaths[label] = os.path.abspath(path)
        self._watcher.addPath(os.path.abspath(path))
        return True

    def _postFileLoad(self):
        if not self.seriesRows:
            first = next(iter(self.dataFrames))
            df    = self.dataFrames[first]
            cols  = list(df.columns)
            num   = list(df.select_dtypes(include="number").columns)
            defX  = cols[0]
            defY  = next((c for c in num if c != defX), cols[-1] if len(cols) > 1 else cols[0])
            self._addSeriesEntry(xDefault=(first, defX), yDefault=(first, defY))
        else:
            self._rebuildSeriesTable()
            self.drawPlot()

        self.filesList.setCurrentRow(self.filesList.count() - 1)
        self.statusBar().showMessage(f"Loaded {len(self.dataFrames)} file(s)", 5000)
        self._enableDataButtons(True)
        self._rebuildComparisonTable()
        self._rebuildFitTable()
        self.drawPlot(_force=True)

    def _enableDataButtons(self, enabled):
        self.plotButton.setEnabled(enabled)
        self.addSeriesButton.setEnabled(enabled)
        self.removeSeriesButton.setEnabled(enabled)
        self.dupSeriesButton.setEnabled(enabled)
        self.addAllButton.setEnabled(enabled)
        self.paletteButton.setEnabled(enabled)
        self.clearSeriesButton.setEnabled(enabled)
        self.clearFilesAction.setEnabled(enabled)
        self._clearFilesBtn.setEnabled(enabled)
        self._statsBtn.setEnabled(enabled)
        self._computedColBtn.setEnabled(enabled)
        self._previewBtn.setEnabled(enabled)
        self.addComparisonButton.setEnabled(enabled)
        self.addFitButton.setEnabled(enabled)

    # ---- Live reload -----------------------------------------------------

    def _onFileChanged(self, path):
        if not self._liveReload:
            return
        self._pendingReload.add(path)
        self._reloadTimer.start()   # debounce bursts of writes

    def _flushReloads(self):
        paths, self._pendingReload = self._pendingReload, set()
        changed = False
        for path in paths:
            # Editors often replace the file (new inode) — re-arm the watch.
            if os.path.exists(path):
                if path not in self._watcher.files():
                    self._watcher.addPath(path)
                label = next((lbl for lbl, p in self._filePaths.items() if p == path), None)
                if label and self._reloadFile(label, path):
                    changed = True
        if changed:
            self._rebuildSeriesTable()
            self._rebuildComparisonTable()
            self._rebuildFitTable()
            self.drawPlot(_force=True)
            self.statusBar().showMessage("Reloaded changed file(s)", 3000)

    def _reloadFile(self, label, path):
        try:
            df = _readDataFile(path)
        except Exception:
            return False   # likely a partial write; the next event will retry
        if df.empty or len(df.columns) == 0:
            return False
        self.dataFrames[label] = df
        # refresh the row count shown in the file list
        for i in range(self.filesList.count()):
            it = self.filesList.item(i)
            if it.data(Qt.UserRole) == label:
                it.setText(f"{label}  ({len(df)}×{len(df.columns)})")
                break
        if self.filesList.currentItem() and \
                self.filesList.currentItem().data(Qt.UserRole) == label:
            self.previewTable.model().setDataFrame(df.head(previewRowLimit))
        return True

    def reloadAllFiles(self):
        n = 0
        for label, path in list(self._filePaths.items()):
            if os.path.exists(path) and self._reloadFile(label, path):
                n += 1
        if n:
            self._rebuildSeriesTable()
            self._rebuildComparisonTable()
            self._rebuildFitTable()
            self.drawPlot(_force=True)
        self.statusBar().showMessage(f"Reloaded {n} file(s)", 3000)

    def _setLiveReload(self, on):
        self._liveReload = on

    def _makeFileLabel(self, path):
        base = os.path.basename(path)
        if base not in self.dataFrames:
            return base
        n = 2
        while f"{base} ({n})" in self.dataFrames:
            n += 1
        return f"{base} ({n})"

    def _onPreviewFileChanged(self, item, _previous=None):
        if item is None:
            return
        label = item.data(Qt.UserRole)
        df    = self.dataFrames.get(label)
        if df is None:
            return
        self.previewTable.setModel(DataFrameModel(df.head(previewRowLimit)))
        self.previewTable.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------

    def _recentFilesList(self):
        # QSettings stores a one-element list as a plain string on some
        # backends; normalise so list("path") never splits into characters.
        val = self._settings.value("recentFiles", [])
        if val is None:
            return []
        if isinstance(val, str):
            return [val] if val else []
        return list(val)

    def _addToRecentFiles(self, path):
        path  = os.path.abspath(path)
        paths = self._recentFilesList()
        if path in paths:
            paths.remove(path)
        paths.insert(0, path)
        self._settings.setValue("recentFiles", paths[:_MAX_RECENT])
        self._rebuildRecentFilesMenu()

    def _rebuildRecentFilesMenu(self):
        self._recentMenu.clear()
        paths = self._recentFilesList()
        if not paths:
            act = self._recentMenu.addAction("(empty)")
            act.setEnabled(False)
            return
        for path in paths:
            act = QAction(os.path.basename(path), self)
            act.setToolTip(path)
            act.triggered.connect(lambda checked=False, p=path: self._openRecentFile(p))
            self._recentMenu.addAction(act)
        self._recentMenu.addSeparator()
        clearAct = QAction("Clear recent files", self)
        clearAct.triggered.connect(self._clearRecentFiles)
        self._recentMenu.addAction(clearAct)

    def _openRecentFile(self, path):
        if not os.path.exists(path):
            QMessageBox.warning(self, "File not found", f"File no longer exists:\n{path}")
            paths = self._recentFilesList()
            if path in paths:
                paths.remove(path)
            self._settings.setValue("recentFiles", paths)
            self._rebuildRecentFilesMenu()
            return
        if self._loadFile(path):
            self._postFileLoad()

    def _clearRecentFiles(self):
        self._settings.setValue("recentFiles", [])
        self._rebuildRecentFilesMenu()

    # ------------------------------------------------------------------
    # Series table
    # ------------------------------------------------------------------

    def _findComboIndexByData(self, combo, data):
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                return i
        return -1

    def _populateColumnCombo(self, combo):
        combo.blockSignals(True)
        combo.clear()
        for label, df in self.dataFrames.items():
            for col in df.columns:
                combo.addItem(f"{col}: {label}", (label, col))
        combo.blockSignals(False)
        # Type-to-filter for wide datasets (keeps the item data intact — only
        # existing entries can be chosen, so currentData() stays valid).
        if not combo.isEditable():
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.completer().setCompletionMode(QCompleter.PopupCompletion)
            combo.completer().setCaseSensitivity(Qt.CaseInsensitive)
            combo.completer().setFilterMode(Qt.MatchContains)
            combo.lineEdit().editingFinished.connect(
                lambda c=combo: c.lineEdit().setText(c.itemText(c.currentIndex())))

    def _newSeriesEntry(self, xDefault=None, yDefault=None, kind="line",
                        marker=None, show=True):
        return {
            "id":           next(self._idCounter),
            "show":         show,
            "xData":        xDefault,
            "yData":        yDefault,
            "kind":         kind,
            "marker":       marker,
            "linestyle":    "-",
            "color":        None,
            "linewidth":    2.5,
            "scatterSize":  60,
            "alpha":        0.9,
            "legendLabel":  "",
            "markerEdge":   True,
            "useRightAxis": False,
            # Advanced per-series options
            "errData":      None,
            "smoothing":    False,
            "smoothWindow": 10,
            "bins":         20,
            "filterExpr":   "",
            "colorByCol":   None,
        }

    def _findSeriesById(self, rowId):
        return next((e for e in self.seriesRows if e["id"] == rowId), None)

    def _addSeriesEntry(self, xDefault=None, yDefault=None,
                        kindDefault="line", checked=True):
        if not self.dataFrames:
            return
        if xDefault is None or yDefault is None:
            first = next(iter(self.dataFrames))
            df    = self.dataFrames[first]
            cols  = list(df.columns)
            num   = list(df.select_dtypes(include="number").columns)
            if xDefault is None:
                xDefault = (first, cols[0])
            if yDefault is None:
                used = {e["yData"][1] for e in self.seriesRows if e["yData"] is not None}
                yDefault = (first, next(
                    (c for c in num if c != xDefault[1] and c not in used),
                    next((c for c in num if c != xDefault[1]),
                         cols[-1] if len(cols) > 1 else cols[0]),
                ))
        self._pushUndoState()
        entry = self._newSeriesEntry(
            xDefault=xDefault, yDefault=yDefault,
            kind=kindDefault, show=checked,
        )
        self.seriesRows.append(entry)
        self._rebuildSeriesTable()
        self.drawPlot()

    def _rebuildSeriesTable(self):
        self.seriesTable.blockSignals(True)
        self.seriesTable.setRowCount(0)
        for entry in self.seriesRows:
            self._buildSeriesTableRow(entry)
        self.seriesTable.blockSignals(False)
        self._autoSizeTable(self.seriesTable)

    def _buildSeriesTableRow(self, entry):
        row   = self.seriesTable.rowCount()
        self.seriesTable.insertRow(row)
        rowId = entry["id"]

        # Col 0: show checkbox (centred in its column)
        showItem = QTableWidgetItem()
        showItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        showItem.setCheckState(Qt.Checked if entry["show"] else Qt.Unchecked)
        showItem.setData(Qt.UserRole, rowId)
        showItem.setTextAlignment(Qt.AlignCenter)
        self.seriesTable.setItem(row, 0, showItem)

        # Col 1: color swatch. tabColors holds matplotlib names ("tab:blue"),
        # which Qt stylesheets don't understand — resolve to a hex string so the
        # swatch actually shows the colour the series is drawn in.
        entry_idx = next((i for i, e in enumerate(self.seriesRows) if e["id"] == rowId), 0)
        swatch_color = _cssColor(
            entry.get("color") or tabColors[entry_idx % len(tabColors)])
        swatchBtn = QPushButton()
        swatchBtn.setFixedSize(18, 18)
        swatchBtn.setStyleSheet(
            f"QPushButton {{ background-color: {swatch_color}; border: 1px solid palette(mid);"
            f" border-radius: 3px; padding: 0; }}"
            f"QPushButton:hover {{ border: 2px solid palette(highlight); }}"
        )
        swatchBtn.setToolTip("Click to change color")
        swatchBtn.clicked.connect(lambda _, rid=rowId: self._openColorFromSwatch(rid))
        cell1 = QWidget()
        cell1L = QHBoxLayout(cell1)
        cell1L.setContentsMargins(4, 4, 4, 4)
        cell1L.addWidget(swatchBtn, 0, Qt.AlignCenter)
        self.seriesTable.setCellWidget(row, 1, cell1)

        # Col 2: X combo
        xCombo = QComboBox()
        self._populateColumnCombo(xCombo)
        if entry["xData"] is not None:
            idx = self._findComboIndexByData(xCombo, entry["xData"])
            if idx >= 0:
                xCombo.setCurrentIndex(idx)
        xCombo.currentIndexChanged.connect(
            lambda _, rid=rowId, c=xCombo: self._onSeriesFieldChanged(rid, "xData", c.currentData())
        )
        self.seriesTable.setCellWidget(row, 2, xCombo)

        # Col 3: Y combo
        yCombo = QComboBox()
        self._populateColumnCombo(yCombo)
        if entry["yData"] is not None:
            idx = self._findComboIndexByData(yCombo, entry["yData"])
            if idx >= 0:
                yCombo.setCurrentIndex(idx)
        yCombo.currentIndexChanged.connect(
            lambda _, rid=rowId, c=yCombo: self._onSeriesFieldChanged(rid, "yData", c.currentData())
        )
        self.seriesTable.setCellWidget(row, 3, yCombo)

        # Col 4: type combo (encodes both kind and right-Y axis)
        typeCombo = QComboBox()
        typeCombo.addItems(["Line", "Scatter", "Histogram", "Line (R)", "Scatter (R)"])
        _type_text = entry["kind"].capitalize()
        if entry.get("useRightAxis"):
            _type_text += " (R)"
        typeCombo.setCurrentText(_type_text)
        typeCombo.currentIndexChanged.connect(
            lambda _, rid=rowId, c=typeCombo: self._onSeriesTypeChanged(rid, c.currentText())
        )
        self.seriesTable.setCellWidget(row, 4, typeCombo)

        # Col 5: style gear button
        styleBtn = iconButton(gearIcon(self._iconColor), "Series style…", diameter=self._btnDiameter())
        styleBtn.clicked.connect(lambda _, rid=rowId: self._openSeriesStyleDialog(rid))
        cell5 = QWidget()
        cell5L = QHBoxLayout(cell5)
        cell5L.setContentsMargins(2, 2, 2, 2)
        cell5L.addWidget(styleBtn, 0, Qt.AlignCenter)
        self.seriesTable.setCellWidget(row, 5, cell5)

        self.seriesTable.setRowHeight(row, 36)

    def _onSeriesFieldChanged(self, rowId, field, value):
        entry = self._findSeriesById(rowId)
        if entry:
            entry[field] = value
            self.drawPlot()

    def _onSeriesTypeChanged(self, rowId, text):
        entry = self._findSeriesById(rowId)
        if not entry:
            return
        right = "(R)" in text
        entry["kind"]         = text.replace(" (R)", "").lower()
        entry["useRightAxis"] = right
        self.drawPlot()

    def _onSeriesShowToggle(self, item):
        if item.column() != 0:
            return
        entry = self._findSeriesById(item.data(Qt.UserRole))
        if entry:
            entry["show"] = item.checkState() == Qt.Checked
            self.drawPlot()

    def _onSeriesRowsReordered(self, src, tgt):
        if src == tgt or src >= len(self.seriesRows):
            return
        self._pushUndoState()
        entry = self.seriesRows.pop(src)
        self.seriesRows.insert(tgt, entry)
        self._rebuildSeriesTable()
        self.drawPlot()

    def _removeSelectedSeries(self):
        rows = sorted({i.row() for i in self.seriesTable.selectedIndexes()}, reverse=True)
        if not rows and self.seriesTable.rowCount():
            rows = [self.seriesTable.rowCount() - 1]
        ids = set()
        for r in rows:
            item = self.seriesTable.item(r, 0)
            if item:
                ids.add(item.data(Qt.UserRole))
        if not ids:
            return
        self._pushUndoState()
        self.seriesRows = [e for e in self.seriesRows if e["id"] not in ids]
        self._rebuildSeriesTable()
        self.drawPlot()

    # ---- Clear-all buttons ----------------------------------------------

    def _clearSeries(self):
        if not self.seriesRows:
            return
        self._pushUndoState()
        self.seriesRows.clear()
        self._rebuildSeriesTable()
        self.drawPlot()

    def _clearReferenceLines(self):
        if not self.referenceLineRows:
            return
        self._pushUndoState()
        self.referenceLineRows.clear()
        self._rebuildReferenceLineTable()
        self.drawPlot()

    def _clearFills(self):
        if not self.fillRows:
            return
        self._pushUndoState()
        self.fillRows.clear()
        self._rebuildFillTable()
        self.drawPlot()

    def _clearTextAnnotations(self):
        if not self.textAnnotationRows:
            return
        self._pushUndoState()
        self.textAnnotationRows.clear()
        self._rebuildTextAnnotationTable()
        self.drawPlot()

    def _clearFits(self):
        if not self.fitRows:
            return
        self.fitRows.clear()
        self._rebuildFitTable()
        self.removeFitButton.setEnabled(False)
        self.drawPlot()

    def _clearComparisons(self):
        if not self.comparisonRows:
            return
        self.comparisonRows.clear()
        self._rebuildComparisonTable()
        self.removeComparisonButton.setEnabled(False)
        self.drawPlot()

    # ---- Shapes & images -------------------------------------------------

    def _newShapeEntry(self, kind):
        n = len(self.shapeRows)
        off = min(0.03 * n, 0.2)
        w = 0.2
        # Default to a *visual* square/circle: convert equal pixels into the
        # axes-fraction height for the current plot-area aspect ratio.
        if kind == "image":
            h = 0.2
        else:
            h = min(0.85, round(w * self.canvas.axesPixelAspect(), 4))
        cx, cy = 0.42 + off * 0.5, 0.55 - off * 0.5
        return {
            "id": next(self._idCounter), "kind": kind, "show": True,
            "x": round(cx - w / 2, 4), "y": round(cy - h / 2, 4),
            "w": w, "h": h, "angle": 0.0, "locked": False,
            "color": "#e4572e", "fill": None, "alpha": 1.0, "linewidth": 2.0,
            "imageId": None, "path": None,
        }

    def _findShapeById(self, sid):
        return next((e for e in self.shapeRows if e["id"] == sid), None)

    def _shapeTypeLabel(self, entry):
        name = {"rect": "Rectangle", "roundrect": "Rounded rectangle",
                "ellipse": "Ellipse", "triangle": "Triangle",
                "pentagon": "Pentagon", "hexagon": "Hexagon", "star": "Star",
                "image": "Image"}.get(entry["kind"], "Shape")
        return name + ("  (locked)" if entry.get("locked") else "")

    def _shapeTableMenu(self, pos):
        item = self.shapeTable.itemAt(pos)
        if item is None:
            return
        sid = item.data(Qt.UserRole)
        entry = self._findShapeById(sid)
        if entry is None:
            return
        menu = QMenu(self)
        menu.addAction("Duplicate", lambda: self._duplicateShape(sid))
        menu.addAction("Bring to front", lambda: self._reorderShape(sid, "front"))
        menu.addAction("Send to back", lambda: self._reorderShape(sid, "back"))
        menu.addAction("Unlock" if entry.get("locked") else "Lock",
                       lambda: self._toggleShapeLock(sid))
        menu.addSeparator()
        menu.addAction("Remove", lambda: self._deleteShape(sid))
        menu.exec(self.shapeTable.viewport().mapToGlobal(pos))

    def _addShape(self, kind):
        if not self.dataFrames:
            self.statusBar().showMessage("Plot some data before adding shapes", 4000)
            return
        self._pushUndoState()
        entry = self._newShapeEntry(kind)
        self.shapeRows.append(entry)
        self._rebuildShapeTable()
        self.drawPlot()
        self.canvas.selectShape(entry["id"])

    def _rebuildShapeTable(self):
        self.shapeTable.blockSignals(True)
        self.shapeTable.setRowCount(0)
        for entry in self.shapeRows:
            self._buildShapeTableRow(entry)
        self.shapeTable.blockSignals(False)
        self._autoSizeTable(self.shapeTable)

    def _buildShapeTableRow(self, entry):
        row = self.shapeTable.rowCount()
        self.shapeTable.insertRow(row)
        rowId = entry["id"]
        showItem = QTableWidgetItem()
        showItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        showItem.setCheckState(Qt.Checked if entry.get("show", True) else Qt.Unchecked)
        showItem.setData(Qt.UserRole, rowId)
        showItem.setTextAlignment(Qt.AlignCenter)
        self.shapeTable.setItem(row, 0, showItem)
        typeItem = QTableWidgetItem("  " + self._shapeTypeLabel(entry))
        typeItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        typeItem.setData(Qt.UserRole, rowId)
        self.shapeTable.setItem(row, 1, typeItem)
        gearBtn = iconButton(gearIcon(self._iconColor), "Shape style…",
                             diameter=self._btnDiameter())
        gearBtn.clicked.connect(lambda _, rid=rowId: self._openShapeStyleDialog(rid))
        cell = QWidget()
        cl = QHBoxLayout(cell)
        cl.setContentsMargins(2, 2, 2, 2)
        cl.addWidget(gearBtn, 0, Qt.AlignCenter)
        self.shapeTable.setCellWidget(row, 2, cell)
        self.shapeTable.setRowHeight(row, 36)

    def _onShapeShowToggle(self, item):
        if item.column() != 0:
            return
        entry = self._findShapeById(item.data(Qt.UserRole))
        if entry:
            entry["show"] = item.checkState() == Qt.Checked
            self.drawPlot()

    def _onShapeRowSelected(self):
        sel = self.shapeTable.selectedItems()
        if not sel:
            return
        rid = sel[0].data(Qt.UserRole)
        if rid is not None:
            self.canvas.selectShape(rid)

    def _removeSelectedShape(self):
        sid = self.canvas._selectedShapeId
        if sid is None:
            sel = self.shapeTable.selectedItems()
            sid = sel[0].data(Qt.UserRole) if sel else None
        if sid is None:
            return
        self._deleteShape(sid)

    def _clearShapes(self):
        if not self.shapeRows:
            return
        self._pushUndoState()
        self.shapeRows.clear()
        self.canvas.clearShapeSelection()
        self._rebuildShapeTable()
        self.drawPlot()

    def _deleteShape(self, sid):
        if self._findShapeById(sid) is None:
            return
        self._pushUndoState()
        self.shapeRows = [e for e in self.shapeRows if e["id"] != sid]
        self.canvas.clearShapeSelection()
        self._rebuildShapeTable()
        self.drawPlot()

    def _duplicateShape(self, sid):
        entry = self._findShapeById(sid)
        if entry is None:
            return
        self._pushUndoState()
        new = copy.deepcopy(entry)
        new["id"] = next(self._idCounter)
        new["x"] = round(min(entry["x"] + 0.03, max(0.0, 1.0 - entry["w"])), 4)
        new["y"] = round(max(entry["y"] - 0.03, 0.0), 4)
        new["locked"] = False
        if entry["kind"] == "image":
            new["imageId"] = new["id"]
            self._imageCache[new["id"]] = self._imageCache.get(entry.get("imageId"))
        self.shapeRows.insert(self.shapeRows.index(entry) + 1, new)
        self._rebuildShapeTable()
        self.drawPlot()
        self.canvas.selectShape(new["id"])

    def _onShapeNudge(self, sid, dx, dy):
        entry = self._findShapeById(sid)
        if entry is None or entry.get("locked"):
            return
        import time
        now = time.monotonic()
        if now - getattr(self, "_lastNudgeAt", 0.0) > 0.6:   # coalesce a burst
            self._pushUndoState()
        self._lastNudgeAt = now
        entry["x"] = round(min(max(0.0, entry["x"] + dx), max(0.0, 1.0 - entry["w"])), 4)
        entry["y"] = round(min(max(0.0, entry["y"] + dy), max(0.0, 1.0 - entry["h"])), 4)
        self.drawPlot()

    def _reorderShape(self, sid, where):
        entry = self._findShapeById(sid)
        if entry is None:
            return
        self._pushUndoState()
        self.shapeRows.remove(entry)
        if where == "front":
            self.shapeRows.append(entry)
        else:
            self.shapeRows.insert(0, entry)
        self._rebuildShapeTable()
        self.drawPlot()
        self.canvas.selectShape(sid)

    def _toggleShapeLock(self, sid):
        entry = self._findShapeById(sid)
        if entry is None:
            return
        self._pushUndoState()
        entry["locked"] = not entry.get("locked", False)
        if entry["locked"] and self.canvas._selectedShapeId == sid:
            self.canvas.clearShapeSelection()
        self._rebuildShapeTable()
        self.drawPlot()

    def _addShapeAt(self, kind, fx, fy):
        if not self.dataFrames:
            return
        self._pushUndoState()
        entry = self._newShapeEntry(kind)
        entry["x"] = round(min(max(0.0, fx - entry["w"] / 2), max(0.0, 1.0 - entry["w"])), 4)
        entry["y"] = round(min(max(0.0, fy - entry["h"] / 2), max(0.0, 1.0 - entry["h"])), 4)
        self.shapeRows.append(entry)
        self._rebuildShapeTable()
        self.drawPlot()
        self.canvas.selectShape(entry["id"])

    def _onPlotRightClicked(self, fx, fy):
        from PySide6.QtGui import QCursor
        menu = QMenu(self)
        menu.addAction(self.copyPlotAction)
        act_save = menu.addAction("Save plot…")
        act_save.triggered.connect(self.exportPlot)
        act_save.setEnabled(self.saveButton.isEnabled())
        menu.addAction("Reset view", lambda: self.drawPlot(_force=True))
        if self.dataFrames:
            menu.addSeparator()
            menu.addAction("Add rectangle here", lambda: self._addShapeAt("rect", fx, fy))
            menu.addAction("Add ellipse here", lambda: self._addShapeAt("ellipse", fx, fy))
        menu.exec(QCursor.pos())

    def _onLegendItemPicked(self, sid):
        entry = self._findSeriesById(sid)
        if entry is None:
            return
        self._pushUndoState()
        entry["show"] = not entry.get("show", True)
        self._rebuildSeriesTable()
        self.drawPlot()

    def _onShapeChanged(self, sid, x, y, w, h):
        entry = self._findShapeById(sid)
        if entry is None:
            return
        self._pushUndoState()
        entry["x"], entry["y"], entry["w"], entry["h"] = (
            round(x, 4), round(y, 4), round(w, 4), round(h, 4))
        self.drawPlot()

    def _onShapeRotated(self, sid, angle):
        entry = self._findShapeById(sid)
        if entry is None:
            return
        self._pushUndoState()
        entry["angle"] = round(angle, 2)
        self.drawPlot()

    def _onCanvasResize(self, _event):
        if any(e.get("angle") for e in self.shapeRows):
            self._resizeReplot.start()

    def _onShapeSelected(self, sid):
        self.shapeTable.blockSignals(True)
        if sid < 0:
            self.shapeTable.clearSelection()
        else:
            for r in range(self.shapeTable.rowCount()):
                it = self.shapeTable.item(r, 0)
                if it and it.data(Qt.UserRole) == sid:
                    self.shapeTable.selectRow(r)
                    break
        self.shapeTable.blockSignals(False)

    def _onShapeDeleteRequested(self, sid):
        self._deleteShape(sid)

    def _importImage(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import image", self._settings.value("lastDir", ""),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*)")
        if not path:
            return
        try:
            import matplotlib.image as mpimg
            arr = mpimg.imread(path)
        except Exception as exc:
            self.statusBar().showMessage(f"Could not load image: {exc}", 5000)
            return
        if not self.dataFrames:
            self.statusBar().showMessage("Plot some data before adding an image", 4000)
            return
        self._settings.setValue("lastDir", os.path.dirname(path))
        self._pushUndoState()
        entry = self._newShapeEntry("image")
        ih, iw = arr.shape[0], arr.shape[1]
        if iw and ih:
            entry["w"] = 0.3
            entry["h"] = round(min(0.7, 0.3 * ih / iw), 4)
        entry["imageId"] = entry["id"]
        entry["path"] = path
        self._imageCache[entry["id"]] = arr
        self.shapeRows.append(entry)
        self._rebuildShapeTable()
        self.drawPlot()
        self.canvas.selectShape(entry["id"])

    def _openShapeStyleDialog(self, sid):
        entry = self._findShapeById(sid)
        if entry is None:
            return
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{self._shapeTypeLabel(entry)} style")
        form = QFormLayout(dlg)
        is_image = entry["kind"] == "image"
        if not is_image:
            lineWidget, getLine, _ = colorPicker(entry.get("color") or "#e4572e",
                                                 autoLabel="—")
            form.addRow("Line colour", lineWidget)
            fillChk = QCheckBox("Filled")
            fillChk.setChecked(bool(entry.get("fill")))
            form.addRow(fillChk)
            fillWidget, getFill, _ = colorPicker(entry.get("fill") or "#cfe3ff",
                                                 autoLabel="—")
            form.addRow("Fill colour", fillWidget)
            lwSpin = QDoubleSpinBox()
            lwSpin.setRange(0.5, 12.0)
            lwSpin.setSingleStep(0.5)
            lwSpin.setValue(entry.get("linewidth", 2.0))
            form.addRow("Line width", lwSpin)
        alphaSpin = QDoubleSpinBox()
        alphaSpin.setRange(0.05, 1.0)
        alphaSpin.setSingleStep(0.05)
        alphaSpin.setDecimals(2)
        alphaSpin.setValue(entry.get("alpha", 1.0))
        form.addRow("Opacity", alphaSpin)
        angleSpin = None
        if not is_image:
            angleSpin = QDoubleSpinBox()
            angleSpin.setRange(0.0, 359.9)
            angleSpin.setSingleStep(5.0)
            angleSpin.setDecimals(1)
            angleSpin.setSuffix("°")
            angleSpin.setWrapping(True)
            angleSpin.setValue(entry.get("angle", 0.0))
            form.addRow("Rotation", angleSpin)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec():
            self._pushUndoState()
            if not is_image:
                entry["color"] = getLine() or "#e4572e"
                entry["fill"] = getFill() if fillChk.isChecked() else None
                entry["linewidth"] = lwSpin.value()
                entry["angle"] = angleSpin.value()
            entry["alpha"] = alphaSpin.value()
            self.drawPlot()

    def _openSeriesStyleDialog(self, rowId):
        entry = self._findSeriesById(rowId)
        if not entry:
            return
        dlg = SeriesStyleDialog(entry, self, dataFrames=self.dataFrames)
        if dlg.exec():
            self._pushUndoState()
            entry.update(dlg.resultValues())
            self._rebuildSeriesTable()
            self.drawPlot()

    def _duplicateSeries(self):
        rows = sorted({i.row() for i in self.seriesTable.selectedIndexes()})
        row  = rows[0] if rows else (len(self.seriesRows) - 1 if self.seriesRows else -1)
        if row < 0 or row >= len(self.seriesRows):
            return
        self._pushUndoState()
        new_entry = copy.deepcopy(self.seriesRows[row])
        new_entry["id"] = next(self._idCounter)
        self.seriesRows.insert(row + 1, new_entry)
        self._rebuildSeriesTable()
        self.drawPlot()

    def _soloSelectedSeries(self):
        ids = {self.seriesTable.item(r, 0).data(Qt.UserRole)
               for r in {i.row() for i in self.seriesTable.selectedIndexes()}
               if self.seriesTable.item(r, 0)}
        if not ids:
            return
        self._pushUndoState()
        for e in self.seriesRows:
            e["show"] = e["id"] in ids
        self._rebuildSeriesTable()
        self.drawPlot()

    def _showAllSeries(self):
        if not self.seriesRows or all(e.get("show", True) for e in self.seriesRows):
            return
        self._pushUndoState()
        for e in self.seriesRows:
            e["show"] = True
        self._rebuildSeriesTable()
        self.drawPlot()

    def _addAllColumns(self):
        if not self.dataFrames:
            return
        first = next(iter(self.dataFrames))
        df    = self.dataFrames[first]
        cols  = list(df.columns)
        num   = list(df.select_dtypes(include="number").columns)
        if not num:
            self.statusBar().showMessage("No numeric columns found", 4000)
            return
        defX    = cols[0]
        existing = {e["yData"][1] for e in self.seriesRows if e["yData"]}
        to_add  = [c for c in num if c != defX and c not in existing]
        if not to_add:
            self.statusBar().showMessage("All numeric columns are already plotted", 4000)
            return
        self._pushUndoState()
        for col in to_add:
            entry = self._newSeriesEntry(xDefault=(first, defX), yDefault=(first, col))
            self.seriesRows.append(entry)
        self._rebuildSeriesTable()
        self.drawPlot()

    def _openColorFromSwatch(self, rowId):
        entry = self._findSeriesById(rowId)
        if not entry:
            return
        initial = QColor(entry.get("color") or "#1f77b4")
        color   = QColorDialog.getColor(initial, self, "Choose series color")
        if color.isValid():
            self._pushUndoState()
            entry["color"] = color.name()
            self._rebuildSeriesTable()
            self.drawPlot()

    # ------------------------------------------------------------------
    # Reference lines
    # ------------------------------------------------------------------

    def _newReferenceLineEntry(self, orientation="horizontal"):
        return {
            "id":          next(self._idCounter),
            "show":        True,
            "orientation": orientation,
            "position":    0.0,
            "color":       None,
            "linestyle":   "--",
            "linewidth":   1.5,
            "alpha":       0.8,
        }

    def _findReferenceLineById(self, rowId):
        return next((e for e in self.referenceLineRows if e["id"] == rowId), None)

    def _addReferenceLine(self, orientation="horizontal"):
        self._pushUndoState()
        entry = self._newReferenceLineEntry(orientation)
        self.referenceLineRows.append(entry)
        self._rebuildReferenceLineTable()
        self.drawPlot()

    def _removeSelectedReferenceLine(self):
        rows = sorted({i.row() for i in self.referenceLineTable.selectedIndexes()}, reverse=True)
        if not rows and self.referenceLineTable.rowCount():
            rows = [self.referenceLineTable.rowCount() - 1]
        ids = set()
        for r in rows:
            item = self.referenceLineTable.item(r, 0)
            if item:
                ids.add(item.data(Qt.UserRole))
        if not ids:
            return
        self._pushUndoState()
        self.referenceLineRows = [e for e in self.referenceLineRows if e["id"] not in ids]
        self._rebuildReferenceLineTable()
        self.drawPlot()

    def _rebuildReferenceLineTable(self):
        self.referenceLineTable.blockSignals(True)
        self.referenceLineTable.setRowCount(0)
        for entry in self.referenceLineRows:
            self._buildReferenceLineTableRow(entry)
        self.referenceLineTable.blockSignals(False)
        self._autoSizeTable(self.referenceLineTable)

    def _buildReferenceLineTableRow(self, entry):
        row   = self.referenceLineTable.rowCount()
        self.referenceLineTable.insertRow(row)
        rowId = entry["id"]

        showItem = QTableWidgetItem()
        showItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        showItem.setCheckState(Qt.Checked if entry["show"] else Qt.Unchecked)
        showItem.setData(Qt.UserRole, rowId)
        self.referenceLineTable.setItem(row, 0, showItem)

        icon = hLineIcon if entry["orientation"] == "horizontal" else vLineIcon
        axisBtn = QPushButton()
        axisBtn.setIcon(icon(self._iconColor))
        axisBtn.setToolTip(entry["orientation"].capitalize())
        axisBtn.setFlat(True)
        axisBtn.setFixedWidth(72)
        self.referenceLineTable.setCellWidget(row, 1, axisBtn)

        posSpin = QDoubleSpinBox()
        posSpin.setRange(-1e12, 1e12)
        posSpin.setDecimals(4)
        posSpin.setValue(entry["position"])
        posSpin.valueChanged.connect(
            lambda v, rid=rowId: self._onReferenceLineFieldChanged(rid, "position", v)
        )
        self.referenceLineTable.setCellWidget(row, 2, posSpin)

        styleBtn = iconButton(gearIcon(self._iconColor), "Line style…", diameter=self._btnDiameter())
        styleBtn.clicked.connect(lambda _, rid=rowId: self._openRefLineStyleDialog(rid))
        cell = QWidget()
        cellL = QHBoxLayout(cell)
        cellL.setContentsMargins(2, 2, 2, 2)
        cellL.addWidget(styleBtn, 0, Qt.AlignCenter)
        self.referenceLineTable.setCellWidget(row, 3, cell)

        self.referenceLineTable.setRowHeight(row, 32)

    def _openRefLineStyleDialog(self, rowId):
        entry = self._findReferenceLineById(rowId)
        if not entry:
            return
        dlg = ReferenceLineStyleDialog(entry, self)
        if dlg.exec():
            self._pushUndoState()
            entry.update(dlg.resultValues())
            self.drawPlot()

    def _onReferenceLineFieldChanged(self, rowId, field, value):
        entry = self._findReferenceLineById(rowId)
        if entry:
            entry[field] = value
            self.drawPlot()

    def _onReferenceLineShowToggle(self, item):
        if item.column() != 0:
            return
        entry = self._findReferenceLineById(item.data(Qt.UserRole))
        if entry:
            entry["show"] = item.checkState() == Qt.Checked
            self.drawPlot()

    # ------------------------------------------------------------------
    # Fill bands
    # ------------------------------------------------------------------

    def _newFillEntry(self, orientation="horizontal"):
        return {
            "id":           next(self._idCounter),
            "show":         True,
            "orientation":  orientation,
            "start":        0.0,
            "end":          1.0,
            "color":        None,
            "alpha":        0.2,
            "legendLabel":  "",
        }

    def _findFillById(self, rowId):
        return next((e for e in self.fillRows if e["id"] == rowId), None)

    def _addFill(self, orientation="horizontal"):
        self._pushUndoState()
        entry = self._newFillEntry(orientation)
        self.fillRows.append(entry)
        self._rebuildFillTable()
        self.drawPlot()

    def _removeSelectedFill(self):
        rows = sorted({i.row() for i in self.fillTable.selectedIndexes()}, reverse=True)
        if not rows and self.fillTable.rowCount():
            rows = [self.fillTable.rowCount() - 1]
        ids = set()
        for r in rows:
            item = self.fillTable.item(r, 0)
            if item:
                ids.add(item.data(Qt.UserRole))
        if not ids:
            return
        self._pushUndoState()
        self.fillRows = [e for e in self.fillRows if e["id"] not in ids]
        self._rebuildFillTable()
        self.drawPlot()

    def _rebuildFillTable(self):
        self.fillTable.blockSignals(True)
        self.fillTable.setRowCount(0)
        for entry in self.fillRows:
            self._buildFillTableRow(entry)
        self.fillTable.blockSignals(False)
        self._autoSizeTable(self.fillTable)

    def _buildFillTableRow(self, entry):
        row   = self.fillTable.rowCount()
        self.fillTable.insertRow(row)
        rowId = entry["id"]

        showItem = QTableWidgetItem()
        showItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        showItem.setCheckState(Qt.Checked if entry["show"] else Qt.Unchecked)
        showItem.setData(Qt.UserRole, rowId)
        self.fillTable.setItem(row, 0, showItem)

        icon = hLineIcon if entry["orientation"] == "horizontal" else vLineIcon
        axisBtn = QPushButton()
        axisBtn.setIcon(icon(self._iconColor))
        axisBtn.setToolTip(entry["orientation"].capitalize())
        axisBtn.setFlat(True)
        axisBtn.setFixedWidth(72)
        self.fillTable.setCellWidget(row, 1, axisBtn)

        startSpin = QDoubleSpinBox()
        startSpin.setRange(-1e12, 1e12)
        startSpin.setDecimals(4)
        startSpin.setValue(entry["start"])
        startSpin.valueChanged.connect(
            lambda v, rid=rowId: self._onFillFieldChanged(rid, "start", v)
        )
        self.fillTable.setCellWidget(row, 2, startSpin)

        endSpin = QDoubleSpinBox()
        endSpin.setRange(-1e12, 1e12)
        endSpin.setDecimals(4)
        endSpin.setValue(entry["end"])
        endSpin.valueChanged.connect(
            lambda v, rid=rowId: self._onFillFieldChanged(rid, "end", v)
        )
        self.fillTable.setCellWidget(row, 3, endSpin)

        styleBtn = iconButton(gearIcon(self._iconColor), "Fill style…", diameter=self._btnDiameter())
        styleBtn.clicked.connect(lambda _, rid=rowId: self._openFillStyleDialog(rid))
        cell = QWidget()
        cellL = QHBoxLayout(cell)
        cellL.setContentsMargins(2, 2, 2, 2)
        cellL.addWidget(styleBtn, 0, Qt.AlignCenter)
        self.fillTable.setCellWidget(row, 4, cell)

        self.fillTable.setRowHeight(row, 32)

    def _openFillStyleDialog(self, rowId):
        entry = self._findFillById(rowId)
        if not entry:
            return
        dlg = FillStyleDialog(entry, self)
        if dlg.exec():
            self._pushUndoState()
            entry.update(dlg.resultValues())
            self.drawPlot()

    def _onFillFieldChanged(self, rowId, field, value):
        entry = self._findFillById(rowId)
        if entry:
            entry[field] = value
            self.drawPlot()

    def _onFillShowToggle(self, item):
        if item.column() != 0:
            return
        entry = self._findFillById(item.data(Qt.UserRole))
        if entry:
            entry["show"] = item.checkState() == Qt.Checked
            self.drawPlot()

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def _getSeriesArrays(self, xFile, xCol, yFile, yCol):
        xDf = self.dataFrames.get(xFile)
        yDf = self.dataFrames.get(yFile)
        if xDf is None or yDf is None:
            return None
        if xCol not in xDf.columns or yCol not in yDf.columns:
            return None
        if len(xDf) != len(yDf):
            return None
        combined = pd.DataFrame({
            "x": xDf[xCol].reset_index(drop=True),
            "y": yDf[yCol].reset_index(drop=True),
        }).dropna()
        return combined["x"], combined["y"]

    def _parseLimit(self, minEdit, maxEdit):
        mn, mx = minEdit.text().strip(), maxEdit.text().strip()
        if not mn or not mx:
            return None
        try:
            return float(mn), float(mx)
        except ValueError:
            return None

    def drawPlot(self, *_, _force=False):
        if not self.dataFrames:
            return
        if not _force and not self._autoPlot:
            return

        seriesList, skipped = [], []
        for entry in self.seriesRows:
            if not entry["show"] or entry["xData"] is None or entry["yData"] is None:
                continue
            _, xCol = entry["xData"]
            _, yCol = entry["yData"]
            label  = entry["legendLabel"] or f"{yCol} vs {xCol}"
            data   = self._buildSeriesData(entry)
            if data is None:
                skipped.append(f"{yCol} vs {xCol}")
                continue
            seriesList.append({
                "id":           entry["id"],
                "xLabel":       xCol,
                "xValues":      data["x"],
                "yLabel":       yCol,
                "yValues":      data["y"],
                "errValues":    data.get("e"),
                "colorValues":  data.get("c"),
                "kind":         entry["kind"],
                "marker":       entry["marker"],
                "linestyle":    entry["linestyle"],
                "label":        label,
                "color":        entry["color"],
                "linewidth":    entry["linewidth"],
                "scatterSize":  entry.get("scatterSize", 60),
                "alpha":        entry["alpha"],
                "markerEdge":   entry.get("markerEdge", True),
                "useRightAxis": entry.get("useRightAxis", False),
                "smoothing":    entry.get("smoothing", False),
                "smoothWindow": entry.get("smoothWindow", 10),
                "bins":         entry.get("bins", 20),
            })

        # Fitted-curve overlays are drawn as ordinary dashed line series.
        for fitEntry in self.fitRows:
            overlay = self._fitOverlaySeries(fitEntry)
            if overlay is not None:
                seriesList.append(overlay)

        if skipped:
            self.canvas.showWarning("Length mismatch, skipped: " + ", ".join(skipped))
        else:
            self.canvas.clearWarning()

        refLines = [
            {k: e[k] for k in ("id", "orientation", "position", "color", "linestyle", "linewidth", "alpha")}
            for e in self.referenceLineRows if e["show"]
        ]

        fillBands = [
            {k: e[k] for k in ("orientation", "start", "end", "color", "alpha", "legendLabel")}
            for e in self.fillRows if e.get("show", True)
        ]

        shapes = []
        for e in self.shapeRows:
            if not e.get("show", True):
                continue
            sh = {k: e.get(k) for k in
                  ("id", "kind", "x", "y", "w", "h", "color", "fill",
                   "alpha", "linewidth", "angle", "locked")}
            if e["kind"] == "image":
                sh["array"] = self._imageCache.get(e.get("imageId"))
            shapes.append(sh)

        if not seriesList:
            self.canvas.clear("Enable at least one series to plot")
            if not skipped:
                self.statusBar().showMessage("Enable at least one series to plot", 6000)
            self.saveButton.setEnabled(False)
            self.copyPlotAction.setEnabled(False)
            self._copyBtn.setEnabled(False)
            return

        def _label(edit):
            """None = auto-derive, '' = suppress (#none), text = explicit."""
            t = edit.text().strip()
            return "" if t.lower() == "#none" else (t or None)

        title_raw = self.titleEdit.text().strip()
        if title_raw.lower() == "#none":
            title = ""
        elif title_raw:
            title = title_raw
        else:
            title = next(iter(self.dataFrames)) if len(self.dataFrames) == 1 else None

        activeAnnotations = [e for e in self.textAnnotationRows if e.get("show", True)]

        # Inject any comparison metric flagged "add to plot" as an annotation.
        for entry in self.comparisonRows:
            metrics = entry.get("metrics", {})
            if not any(m["add"] for m in metrics.values()):
                continue
            results = self._computeComparison(entry)
            if not results:
                continue
            for key in self._METRIC_KEYS:
                cfg = metrics[key]
                if not cfg["add"]:
                    continue
                s = cfg["settings"]
                dec = s.get("decimals", 4)
                unit = s.get("unit", "")
                text = f"{key}: {results[key]:.{dec}f}"
                if unit:
                    text += f" {unit}"
                activeAnnotations.append({
                    "text":       text,
                    "coordType":  "axes",
                    "x":          s["x"],
                    "y":          s["y"],
                    "fontSize":   s["fontSize"],
                    "fontWeight": s["fontWeight"],
                    "color":      s["color"],
                    "rotation":   0,
                    "ha":         s["ha"],
                    "va":         s["va"],
                    "show":       True,
                    "metricRef":  {"cmpId": entry["id"], "key": key},
                })

        box_aspect = None
        if self.boxAspectCheck.isChecked():
            w = self.boxAspectW.value()
            h = self.boxAspectH.value()
            if w > 0:
                box_aspect = h / w

        try:
            self.canvas.plot(
                series=seriesList, title=title,
                xLim=self._parseLimit(self.xMinEdit, self.xMaxEdit),
                yLim=self._parseLimit(self.yMinEdit, self.yMaxEdit),
                xLabel=_label(self.xLabelEdit),
                yLabel=_label(self.yLabelEdit),
                xTickSize=self._getXTickSize(), yTickSize=self._getYTickSize(),
                xTickCount=self._getXTickCount(), yTickCount=self._getYTickCount(),
                showGrid=self.gridCheckBox.isChecked(),
                transparentBackground=self.exportTransparentCheck.isChecked(),
                referenceLines=refLines,
                fillBands=fillBands,
                showLegend=self.showLegendCheck.isChecked(),
                legendPos=(self._legendLoc if self._legendLoc is not None
                           else self.legendPosCombo.currentText()),
                legendFrame=self.legendFrameCheck.isChecked(),
                textAnnotations=activeAnnotations,
                fontFamily=self.fontFamilyCombo.currentText() or None,
                xScale="log" if self.xLogCheck.isChecked() else "linear",
                yScale="log" if self.yLogCheck.isChecked() else "linear",
                reverseX=self.reverseXCheck.isChecked(),
                reverseY=self.reverseYCheck.isChecked(),
                equalAspect=self.equalAspectCheck.isChecked(),
                boxAspect=box_aspect,
                shapes=shapes,
            )
        except Exception as exc:
            # A single malformed series or invalid setting must not take the
            # whole UI down — surface it and leave the previous plot in place.
            self.canvas.showWarning(f"Could not render plot: {exc}")
            self.statusBar().showMessage(f"Plot error: {exc}", 6000)
            return
        self.saveButton.setEnabled(True)
        self.copyPlotAction.setEnabled(True)
        self._copyBtn.setEnabled(True)
        self.statusBar().showMessage("Plot updated", 2000)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _onExportFormatChanged(self, *_):
        fmt  = self.exportFormatCombo.currentText().lower()
        fn   = self.exportFilenameEdit.text().strip()
        base = os.path.splitext(fn)[0] if fn else "plot"
        self.exportFilenameEdit.setText(base + "." + fmt)

    def _browseExportPath(self):
        fmt    = self.exportFormatCombo.currentText()
        extMap = {"PNG": "PNG Image (*.png)", "PDF": "PDF Document (*.pdf)", "SVG": "SVG Image (*.svg)"}
        dlg    = QFileDialog(self, "Choose save location",
                             self.exportFilenameEdit.text() or f"plot.{fmt.lower()}")
        dlg.setNameFilter(f"{extMap[fmt]};;All Files (*)")
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setLabelText(QFileDialog.Accept, "Select")
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                self.exportFilenameEdit.setText(files[0])

    def exportPlot(self):
        if not self.dataFrames:
            return
        path = self.exportFilenameEdit.text().strip()
        if not path:
            path = "plot"
        fmt = self.exportFormatCombo.currentText().lower()
        if not path.lower().endswith(f".{fmt}"):
            path = os.path.splitext(path)[0] + f".{fmt}"
        path = os.path.abspath(path)
        dpi = self.exportDpiSpin.value()
        try:
            self.canvas.figure.savefig(
                path, dpi=dpi,
                transparent=self.exportTransparentCheck.isChecked(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        # Auto-increment so the next save doesn't silently overwrite this one.
        base = os.path.splitext(os.path.basename(path))[0]
        self.exportFilenameEdit.setText(self._incrementName(base))
        self.statusBar().showMessage(f"Saved {path}", 6000)

    @staticmethod
    def _incrementName(name):
        i = len(name)
        while i > 0 and name[i - 1].isdigit():
            i -= 1
        if i < len(name):
            return name[:i] + str(int(name[i:]) + 1)
        return name + "_1"

    def _exportData(self):
        cols = {}
        for entry in self.seriesRows:
            if not entry.get("show", True) or entry["xData"] is None or entry["yData"] is None:
                continue
            data = self._buildSeriesData(entry)
            if data is None:
                continue
            label = entry["legendLabel"] or f"{entry['yData'][1]} vs {entry['xData'][1]}"
            cols[f"{label} · x"] = pd.Series(np.asarray(data["x"]))
            cols[f"{label} · y"] = pd.Series(np.asarray(data["y"]))
        if not cols:
            self.statusBar().showMessage("No plotted series to export", 4000)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export plotted data",
            os.path.join(self._settings.value("lastDir", ""), "plot_data.csv"),
            "CSV files (*.csv)")
        if not path:
            return
        try:
            pd.DataFrame(cols).to_csv(path, index=False)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported data to {os.path.basename(path)}", 5000)

    _PALETTE_MAPS = {"Viridis": "viridis", "Plasma": "plasma", "Cividis": "cividis",
                     "Cool → warm": "coolwarm", "Turbo": "turbo", "Grayscale": "gray"}

    def _paletteColors(self, name, n):
        from matplotlib import colormaps
        from matplotlib.colors import to_hex
        if name == "Default":
            return [tabColors[i % len(tabColors)] for i in range(n)]
        cmap = colormaps[self._PALETTE_MAPS[name]]
        if n <= 1:
            return [to_hex(cmap(0.5))]
        return [to_hex(cmap(0.05 + 0.9 * i / (n - 1))) for i in range(n)]

    def _applyPalette(self, name):
        if not self.seriesRows:
            return
        self._pushUndoState()
        for entry, color in zip(self.seriesRows,
                                self._paletteColors(name, len(self.seriesRows))):
            entry["color"] = color
        self._rebuildSeriesTable()
        self.drawPlot()

    def _showColumnStats(self):
        item = self.filesList.currentItem()
        label = (item.data(Qt.UserRole) if item else
                 (next(iter(self.dataFrames)) if self.dataFrames else None))
        if label is None or label not in self.dataFrames:
            return
        num = self.dataFrames[label].select_dtypes(include="number")
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Column stats — {label}")
        lay = QVBoxLayout(dlg)
        headers = ["Column", "Count", "Min", "Max", "Mean", "Std"]
        table = QTableWidget(len(num.columns), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for r, c in enumerate(num.columns):
            s = num[c]
            vals = [c, str(int(s.count())), f"{s.min():.4g}", f"{s.max():.4g}",
                    f"{s.mean():.4g}", f"{s.std():.4g}"]
            for k, v in enumerate(vals):
                table.setItem(r, k, QTableWidgetItem(v))
        table.resizeColumnsToContents()
        table.setMinimumWidth(520)
        table.setMinimumHeight(min(440, 60 + 28 * max(1, len(num.columns))))
        lay.addWidget(table)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()

        # Persist export settings
        self._settings.setValue("exportDpi", self.exportDpiSpin.value())
        self._settings.setValue("exportFormat", self.exportFormatCombo.currentText())
        self._settings.setValue("exportTransparent", self.exportTransparentCheck.isChecked())

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def _pushUndoState(self):
        self._undoStack.append(self._currentState())
        if len(self._undoStack) > _MAX_UNDO:
            self._undoStack.pop(0)
        self._redoStack.clear()
        self._updateUndoRedoActions()

    def _restoreState(self, state):
        self.seriesRows         = state["series"]
        self.referenceLineRows  = state["refLines"]
        self.fillRows           = state.get("fills", [])
        self.textAnnotationRows = state["annotations"]
        self.shapeRows          = state.get("shapes", [])
        self._rebuildSeriesTable()
        self._rebuildReferenceLineTable()
        self._rebuildFillTable()
        self._rebuildTextAnnotationTable()
        self._rebuildShapeTable()
        self.canvas.clearShapeSelection()
        self.drawPlot(_force=True)

    def _currentState(self):
        return {
            "series":      copy.deepcopy(self.seriesRows),
            "refLines":    copy.deepcopy(self.referenceLineRows),
            "fills":       copy.deepcopy(self.fillRows),
            "annotations": copy.deepcopy(self.textAnnotationRows),
            "shapes":      copy.deepcopy(self.shapeRows),
        }

    def undo(self):
        if not self._undoStack:
            return
        self._redoStack.append(self._currentState())
        self._restoreState(self._undoStack.pop())
        self._updateUndoRedoActions()

    def redo(self):
        if not self._redoStack:
            return
        self._undoStack.append(self._currentState())
        self._restoreState(self._redoStack.pop())
        self._updateUndoRedoActions()

    def _updateUndoRedoActions(self):
        self.undoAction.setEnabled(bool(self._undoStack))
        self.redoAction.setEnabled(bool(self._redoStack))

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def showAbout(self):
        from . import __version__
        QMessageBox.about(
            self, "About Alekhyam",
            f"Alekhyam {__version__}\n\nA lightweight multi-file viewer and "
            f"line/scatter plotter.\n\n“ālekhyam” (आलेख्यम्) — a painting or picture.",
        )

    def clearLoadedFiles(self):
        if not self.dataFrames:
            return
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())
        self._filePaths.clear()
        self._pendingReload.clear()
        self.dataFrames.clear()
        self.filesList.clear()
        self.previewTable.setModel(DataFrameModel())
        self.seriesRows.clear()
        self.seriesTable.setRowCount(0)
        self.fillRows.clear()
        self.fillTable.setRowCount(0)
        self.referenceLineRows.clear()
        self.referenceLineTable.setRowCount(0)
        self.textAnnotationRows.clear()
        self.textAnnotationTable.setRowCount(0)
        self.shapeRows.clear()
        self._imageCache.clear()
        self.canvas.clearShapeSelection()
        self.shapeTable.setRowCount(0)
        # Old undo states reference the dropped dataframes; restoring one
        # would resurrect series rows pointing at files that no longer exist.
        self._undoStack.clear()
        self._redoStack.clear()
        self._updateUndoRedoActions()
        self.canvas.clear()
        self.canvas.clearWarning()
        self.saveButton.setEnabled(False)
        self.copyPlotAction.setEnabled(False)
        self._copyBtn.setEnabled(False)
        self._enableDataButtons(False)
        self.comparisonRows.clear()
        self._rebuildComparisonTable()
        self.removeComparisonButton.setEnabled(False)
        self.fitRows.clear()
        self._rebuildFitTable()
        self.removeFitButton.setEnabled(False)
        self.statusBar().showMessage("Cleared all loaded files", 4000)

    def _onAutoPlotToggled(self, checked):
        self._autoPlot = checked
        if checked:
            self.drawPlot(_force=True)

    def _onBoxAspectToggled(self, checked):
        self.boxAspectWidget.setEnabled(checked)
        self.drawPlot()

    # ------------------------------------------------------------------
    # Compare series  (RMSD / MAE / MSE between column pairs)
    # ------------------------------------------------------------------

    _METRIC_KEYS = ("RMSD", "MAE", "MSE")

    @staticmethod
    def _defaultAnnotationSettings(slot):
        """Default annotation styling for one metric, stacked vertically."""
        base = {"fontSize": 11, "fontWeight": "normal", "color": "#000000",
                "ha": "left", "va": "top", "decimals": 4, "unit": ""}
        return dict(base, x=0.05, y=0.95 - 0.07 * slot)

    def _newComparisonEntry(self):
        slot = len(self.comparisonRows) * len(self._METRIC_KEYS)
        return {
            "id":      next(self._idCounter),
            "refData": None,
            "cmpData": None,
            "metrics": {
                key: {"add": False,
                      "settings": self._defaultAnnotationSettings(slot + i)}
                for i, key in enumerate(self._METRIC_KEYS)
            },
        }

    def _findComparisonById(self, rowId):
        return next((e for e in self.comparisonRows if e["id"] == rowId), None)

    def _numericColumnItems(self):
        items = [("(select column)", None)]
        for label, df in self.dataFrames.items():
            for col in df.select_dtypes(include="number").columns:
                items.append((f"{col}  [{label}]", (label, col)))
        return items

    def _comparisonColumnCombo(self, current, rowId, field):
        combo = QComboBox()
        for text, data in self._numericColumnItems():
            combo.addItem(text, data)
        if current is not None:
            idx = self._findComboIndexByData(combo, current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _, rid=rowId, f=field, c=combo:
            self._onComparisonFieldChanged(rid, f, c.currentData())
        )
        return combo

    def _addComparison(self):
        if not self.dataFrames:
            return
        self.comparisonRows.append(self._newComparisonEntry())
        self._rebuildComparisonTable()
        self.removeComparisonButton.setEnabled(True)

    def _removeSelectedComparison(self):
        rows = sorted({i.row() for i in self.comparisonTable.selectedIndexes()},
                      reverse=True)
        if not rows and self.comparisonTable.rowCount():
            rows = [self.comparisonTable.rowCount() - 1]
        ids = set()
        for r in rows:
            item = self.comparisonTable.item(r, 0)
            if item:
                ids.add(item.data(Qt.UserRole))
        # combos live in cell widgets, so also map row → id via order
        if not ids:
            ids = {self.comparisonRows[r]["id"] for r in rows
                   if 0 <= r < len(self.comparisonRows)}
        self.comparisonRows = [e for e in self.comparisonRows if e["id"] not in ids]
        self._rebuildComparisonTable()
        self.removeComparisonButton.setEnabled(bool(self.comparisonRows))
        self.drawPlot()

    def _rebuildComparisonTable(self):
        self.comparisonTable.setRowCount(0)
        for entry in self.comparisonRows:
            self._buildComparisonRow(entry)
        self._autoSizeTable(self.comparisonTable)

    def _buildComparisonRow(self, entry):
        row = self.comparisonTable.rowCount()
        self.comparisonTable.insertRow(row)
        rowId = entry["id"]

        refCombo = self._comparisonColumnCombo(entry["refData"], rowId, "refData")
        self.comparisonTable.setCellWidget(row, 0, refCombo)
        cmpCombo = self._comparisonColumnCombo(entry["cmpData"], rowId, "cmpData")
        self.comparisonTable.setCellWidget(row, 1, cmpCombo)

        # RMSD summary cell (also holds the row id for selection lookups)
        results = self._computeComparison(entry)
        summary = f"{results['RMSD']:.4g}" if results else "—"
        summaryItem = QTableWidgetItem(summary)
        summaryItem.setData(Qt.UserRole, rowId)
        summaryItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        summaryItem.setTextAlignment(Qt.AlignCenter)
        self.comparisonTable.setItem(row, 2, summaryItem)

        gearBtn = iconButton(gearIcon(self._iconColor), "Details & add to plot…",
                             diameter=self._btnDiameter())
        gearBtn.clicked.connect(lambda _, rid=rowId: self._openComparisonDetails(rid))
        cell = QWidget()
        cellL = QHBoxLayout(cell)
        cellL.setContentsMargins(2, 2, 2, 2)
        cellL.addWidget(gearBtn, 0, Qt.AlignCenter)
        self.comparisonTable.setCellWidget(row, 3, cell)

        self.comparisonTable.setRowHeight(row, 34)

    def _onComparisonFieldChanged(self, rowId, field, value):
        entry = self._findComparisonById(rowId)
        if not entry:
            return
        entry[field] = value
        self._refreshComparisonSummary(rowId)
        if any(m["add"] for m in entry["metrics"].values()):
            self.drawPlot()

    def _refreshComparisonSummary(self, rowId):
        for row in range(self.comparisonTable.rowCount()):
            item = self.comparisonTable.item(row, 2)
            if item and item.data(Qt.UserRole) == rowId:
                entry = self._findComparisonById(rowId)
                results = self._computeComparison(entry)
                item.setText(f"{results['RMSD']:.4g}" if results else "—")
                return

    def _computeComparison(self, entry):
        """Return {RMSD, MAE, MSE, n} for a comparison, or None if not computable."""
        if entry is None or entry["refData"] is None or entry["cmpData"] is None:
            return None
        refFile, refCol = entry["refData"]
        cmpFile, cmpCol = entry["cmpData"]
        refDf = self.dataFrames.get(refFile)
        cmpDf = self.dataFrames.get(cmpFile)
        if refDf is None or cmpDf is None:
            return None
        if refCol not in refDf.columns or cmpCol not in cmpDf.columns:
            return None
        if len(refDf) != len(cmpDf):
            return None
        combined = pd.DataFrame({
            "ref": refDf[refCol].reset_index(drop=True),
            "cmp": cmpDf[cmpCol].reset_index(drop=True),
        }).dropna()
        if combined.empty:
            return None
        diff = combined["cmp"] - combined["ref"]
        mse  = float((diff ** 2).mean())
        return {
            "RMSD": float(mse ** 0.5),
            "MAE":  float(diff.abs().mean()),
            "MSE":  mse,
            "n":    int(len(combined)),
        }

    def _openComparisonDetails(self, rowId):
        entry = self._findComparisonById(rowId)
        if not entry:
            return
        results = self._computeComparison(entry)
        dlg = ComparisonDetailsDialog(entry, results, self)
        if dlg.exec():
            self._refreshComparisonSummary(rowId)
            self.drawPlot()

    # ------------------------------------------------------------------
    # Curve fit  (fit an arbitrary model to a column pair)
    # ------------------------------------------------------------------

    def _newFitEntry(self):
        return {
            "id":      next(self._idCounter),
            "xData":   None,
            "yData":   None,
            "model":   "",
            "p0":      "",
            "overlay": True,
            "showEq":  True,
            "color":   None,   # None → take a color from the plot's cycle
        }

    def _findFitById(self, rowId):
        return next((e for e in self.fitRows if e["id"] == rowId), None)

    def _fitColumnCombo(self, current, rowId, field):
        combo = QComboBox()
        for text, data in self._numericColumnItems():
            combo.addItem(text, data)
        if current is not None:
            idx = self._findComboIndexByData(combo, current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _, rid=rowId, f=field, c=combo:
            self._onFitFieldChanged(rid, f, c.currentData())
        )
        return combo

    def _addFit(self):
        if not self.dataFrames:
            return
        self.fitRows.append(self._newFitEntry())
        self._rebuildFitTable()
        self.removeFitButton.setEnabled(True)

    def _removeSelectedFit(self):
        rows = sorted({i.row() for i in self.fitTable.selectedIndexes()}, reverse=True)
        if not rows and self.fitTable.rowCount():
            rows = [self.fitTable.rowCount() - 1]
        ids = {self.fitRows[r]["id"] for r in rows if 0 <= r < len(self.fitRows)}
        self.fitRows = [e for e in self.fitRows if e["id"] not in ids]
        self._rebuildFitTable()
        self.removeFitButton.setEnabled(bool(self.fitRows))
        self.drawPlot()

    def _rebuildFitTable(self):
        self.fitTable.setRowCount(0)
        for entry in self.fitRows:
            self._buildFitRow(entry)
        self._autoSizeTable(self.fitTable)

    def _buildFitRow(self, entry):
        row = self.fitTable.rowCount()
        self.fitTable.insertRow(row)
        rowId = entry["id"]

        self.fitTable.setCellWidget(row, 0, self._fitColumnCombo(entry["xData"], rowId, "xData"))
        self.fitTable.setCellWidget(row, 1, self._fitColumnCombo(entry["yData"], rowId, "yData"))

        result, _ = self._computeFit(entry)
        summary = f"{result['r2']:.4f}" if result else "—"
        item = QTableWidgetItem(summary)
        item.setData(Qt.UserRole, rowId)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(Qt.AlignCenter)
        self.fitTable.setItem(row, 2, item)

        gearBtn = iconButton(gearIcon(self._iconColor), "Edit model & fit…",
                             diameter=self._btnDiameter())
        gearBtn.clicked.connect(lambda _, rid=rowId: self._openFitDetails(rid))
        cell = QWidget()
        cellL = QHBoxLayout(cell)
        cellL.setContentsMargins(2, 2, 2, 2)
        cellL.addWidget(gearBtn, 0, Qt.AlignCenter)
        self.fitTable.setCellWidget(row, 3, cell)
        self.fitTable.setRowHeight(row, 34)

    def _onFitFieldChanged(self, rowId, field, value):
        entry = self._findFitById(rowId)
        if not entry:
            return
        entry[field] = value
        self._refreshFitSummary(rowId)
        if entry.get("overlay"):
            self.drawPlot()

    def _refreshFitSummary(self, rowId):
        for row in range(self.fitTable.rowCount()):
            item = self.fitTable.item(row, 2)
            if item and item.data(Qt.UserRole) == rowId:
                result, _ = self._computeFit(self._findFitById(rowId))
                item.setText(f"{result['r2']:.4f}" if result else "—")
                return

    def _fitExtraColumns(self, entry):
        """Numeric columns of the Y file usable as fit covariates.

        Excludes the Y column itself and the X column (already available as
        the variable ``x``).
        """
        if entry.get("yData") is None:
            return []
        yFile, yCol = entry["yData"]
        yDf = self.dataFrames.get(yFile)
        if yDf is None:
            return []
        exclude = {yCol}
        if entry.get("xData") and entry["xData"][0] == yFile:
            exclude.add(entry["xData"][1])
        return [c for c in yDf.select_dtypes(include="number").columns
                if c not in exclude]

    def _fitArrays(self, entry):
        """Return (x, y, extra) aligned Series for a fit, or None.

        `extra` maps each covariate column referenced in the model to its data.
        """
        import ast
        xFile, xCol = entry["xData"]
        yFile, yCol = entry["yData"]
        xDf = self.dataFrames.get(xFile)
        yDf = self.dataFrames.get(yFile)
        if xDf is None or yDf is None:
            return None
        if xCol not in xDf.columns or yCol not in yDf.columns:
            return None
        if len(xDf) != len(yDf):
            return None

        # Which covariate columns does the model reference (bare or backtick)?
        available = set(self._fitExtraColumns(entry))
        expr2, tokenMap = substituteColumns(entry.get("model", ""))
        referenced = set(tokenMap.values())
        try:
            referenced |= {n.id for n in ast.walk(ast.parse(expr2, mode="eval"))
                           if isinstance(n, ast.Name)}
        except SyntaxError:
            pass
        extraCols = [c for c in available if c in referenced]

        cols = {
            "__x": xDf[xCol].reset_index(drop=True),
            "__y": yDf[yCol].reset_index(drop=True),
        }
        for c in extraCols:
            cols[c] = yDf[c].reset_index(drop=True)
        combined = pd.DataFrame(cols).dropna()
        if combined.empty:
            return None
        extra = {c: combined[c] for c in extraCols}
        return combined["__x"], combined["__y"], extra

    def _computeFit(self, entry):
        """Fit the model to the entry's X/Y columns. Returns (result, error)."""
        if entry is None or entry["xData"] is None or entry["yData"] is None:
            return None, "Select X and Y columns."
        if not entry.get("model", "").strip():
            return None, "Enter a model formula in x."
        arrays = self._fitArrays(entry)
        if arrays is None:
            return None, "X and Y must be numeric columns of equal length."
        x, y, extra = arrays
        try:
            p0 = None
            if entry.get("p0", "").strip():
                p0 = [float(t) for t in entry["p0"].split(",") if t.strip()]
            result = fitCurve(
                x.to_numpy(), y.to_numpy(), entry["model"], p0=p0,
                extra={c: s.to_numpy() for c, s in extra.items()},
            )
            return result, None
        except ValueError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"Could not fit: {exc}"

    def _openFitDetails(self, rowId):
        entry = self._findFitById(rowId)
        if not entry:
            return
        columns = self._fitExtraColumns(entry)
        dlg = FitDetailsDialog(
            entry, lambda e=entry: self._computeFit(e), columns, self
        )
        if dlg.exec():
            self._refreshFitSummary(rowId)
            self.drawPlot()

    def _fitOverlaySeries(self, entry):
        """Return a synthetic line-series dict for a fit overlay, or None."""
        if not entry.get("overlay"):
            return None
        result, _ = self._computeFit(entry)
        if not result:
            return None
        import numpy as _np
        fx = _np.asarray(result["fittedX"], dtype=float)
        if fx.size < 2:
            return None
        if result["usesExtra"]:
            # Model depends on other columns → plot predictions at the data
            # points (a smooth grid can't supply the covariate values).
            xfit, yfit = result["fittedX"], result["fittedY"]
        else:
            xfit = _np.linspace(fx.min(), fx.max(), 300)
            try:
                yfit = result["predict"](xfit)
            except Exception:
                return None
        _, yCol = entry["yData"]
        _, xCol = entry["xData"]
        label = f"fit: y = {result['equation']}" if entry.get("showEq") else f"{yCol} fit"
        return {
            "xLabel":       xCol,
            "xValues":      xfit,
            "yLabel":       yCol,
            "yValues":      yfit,
            "errValues":    None,
            "colorValues":  None,
            "kind":         "line",
            "marker":       None,
            "linestyle":    "--",
            "label":        label,
            "color":        entry.get("color"),
            "linewidth":    2.0,
            "scatterSize":  60,
            "alpha":        0.95,
            "markerEdge":   False,
            "useRightAxis": False,
            "smoothing":    False,
            "smoothWindow": 10,
            "bins":         20,
        }

    # ------------------------------------------------------------------
    # In-app help
    # ------------------------------------------------------------------

    def _showHelp(self):
        from .helpDialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Drag-and-drop data files
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            files = [
                u.toLocalFile() for u in event.mimeData().urls()
                if u.toLocalFile().lower().endswith(_SUPPORTED_EXTS)
            ]
            if files:
                event.setDropAction(Qt.CopyAction)
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        paths = [
            u.toLocalFile() for u in event.mimeData().urls()
            if u.toLocalFile().lower().endswith(_SUPPORTED_EXTS)
        ]
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        loaded = any(self._loadFile(p) for p in paths)
        if loaded:
            self._postFileLoad()

    # ------------------------------------------------------------------
    # Copy plot to clipboard
    # ------------------------------------------------------------------

    def _copyPlotToClipboard(self):
        if self.canvas.copyToClipboard():
            self.statusBar().showMessage("Plot copied to clipboard", 3000)
        else:
            self.statusBar().showMessage("Copy to clipboard failed", 3000)

    # ------------------------------------------------------------------
    # Computed columns
    # ------------------------------------------------------------------

    def _addComputedColumn(self):
        if not self.dataFrames:
            return
        dlg = ComputedColumnDialog(self.dataFrames, self)
        if not dlg.exec():
            return
        label, name, expr = dlg.values()
        if not name or not expr:
            QMessageBox.warning(self, "Invalid input",
                                "Column name and expression are both required.")
            return
        df = self.dataFrames.get(label)
        if df is None:
            return
        if name in df.columns:
            reply = QMessageBox.question(
                self, "Overwrite column?",
                f"Column '{name}' already exists in {label}. Overwrite it?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        try:
            df[name] = evaluateFormula(df, expr)
            self._rebuildSeriesTable()
            item = self.filesList.currentItem()
            if item and item.data(Qt.UserRole) == label:
                self.previewTable.setModel(DataFrameModel(df.head(previewRowLimit)))
                self.previewTable.resizeColumnsToContents()
            self.statusBar().showMessage(
                f"Added column '{name}' to {label}", 5000
            )
        except Exception as exc:
            QMessageBox.critical(self, "Expression error", str(exc))

    # ------------------------------------------------------------------
    # Plot templates
    # ------------------------------------------------------------------

    def _templateDict(self):
        from . import __version__
        return {
            "version":     __version__,
            "title":       self.titleEdit.text(),
            "xLabel":      self.xLabelEdit.text(),
            "yLabel":      self.yLabelEdit.text(),
            "xMin":        self.xMinEdit.text(),
            "xMax":        self.xMaxEdit.text(),
            "yMin":        self.yMinEdit.text(),
            "yMax":        self.yMaxEdit.text(),
            "xLog":        self.xLogCheck.isChecked(),
            "yLog":        self.yLogCheck.isChecked(),
            "reverseX":    self.reverseXCheck.isChecked(),
            "reverseY":    self.reverseYCheck.isChecked(),
            "equalAspect": self.equalAspectCheck.isChecked(),
            "boxAspect":   self.boxAspectCheck.isChecked(),
            "boxAspectW":  self.boxAspectW.value(),
            "boxAspectH":  self.boxAspectH.value(),
            "xTickSize":   self._getXTickSize(),
            "xTickCount":  self._getXTickCount(),
            "yTickSize":   self._getYTickSize(),
            "yTickCount":  self._getYTickCount(),
            "fontFamily":  self.fontFamilyCombo.currentText(),
            "showLegend":  self.showLegendCheck.isChecked(),
            "legendPos":   self.legendPosCombo.currentText(),
            "legendFrame": self.legendFrameCheck.isChecked(),
            "showGrid":    self.gridCheckBox.isChecked(),
        }

    def _saveTemplate(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save template", "template.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w") as fh:
                json.dump(self._templateDict(), fh, indent=2)
            self.statusBar().showMessage(f"Template saved to {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _loadTemplate(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load template", "", "JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path) as fh:
                t = json.load(fh)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        self._applyTemplateDict(t)
        self.statusBar().showMessage(f"Template loaded: {os.path.basename(path)}", 4000)

    # ---- Project save / open (.plot) ------------------------------------

    def _projectDict(self):
        import base64
        import io
        import matplotlib.image as mpimg
        from . import __version__
        files = {}
        for label, df in self.dataFrames.items():
            dt = [c for c in df.columns
                  if pd.api.types.is_datetime64_any_dtype(df[c])]
            files[label] = {"csv": df.to_csv(index=False), "datetime": dt}
        images = {}
        for iid, arr in self._imageCache.items():
            if arr is None:
                continue
            buf = io.BytesIO()
            mpimg.imsave(buf, arr, format="png")
            images[str(iid)] = base64.b64encode(buf.getvalue()).decode("ascii")
        return {
            "app": "alekhyam", "format": 1, "version": __version__,
            "files": files,
            "series": self.seriesRows, "refLines": self.referenceLineRows,
            "fills": self.fillRows, "annotations": self.textAnnotationRows,
            "shapes": self.shapeRows, "comparisons": self.comparisonRows,
            "fits": self.fitRows, "images": images,
            "legendLoc": list(self._legendLoc) if self._legendLoc else None,
            "ui": self._templateDict(),
        }

    def _saveProject(self):
        if not self.dataFrames:
            self.statusBar().showMessage("Load data before saving a project", 4000)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project",
            os.path.join(self._settings.value("lastDir", ""), "project.plot"),
            "Alekhyam project (*.plot)")
        if not path:
            return
        if not path.lower().endswith(".plot"):
            path += ".plot"
        try:
            with open(path, "w") as fh:
                json.dump(self._projectDict(), fh)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._settings.setValue("lastDir", os.path.dirname(path))
        self.statusBar().showMessage(f"Project saved to {os.path.basename(path)}", 5000)

    def _openProject(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open project", self._settings.value("lastDir", ""),
                "Alekhyam project (*.plot);;All Files (*)")
        if not path:
            return
        try:
            with open(path) as fh:
                proj = json.load(fh)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        try:
            self._applyProjectDict(proj)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", f"Could not load project:\n{exc}")
            return
        self._settings.setValue("lastDir", os.path.dirname(path))
        self.statusBar().showMessage(f"Project opened: {os.path.basename(path)}", 5000)

    @staticmethod
    def _tuplify(entry, keys):
        for k in keys:
            if isinstance(entry.get(k), list):
                entry[k] = tuple(entry[k])

    def _applyProjectDict(self, proj):
        import base64
        import io
        import matplotlib.image as mpimg
        self.clearLoadedFiles()
        for label, fd in proj.get("files", {}).items():
            df = pd.read_csv(io.StringIO(fd["csv"]))
            for c in fd.get("datetime", []):
                if c in df.columns:
                    try:
                        df[c] = pd.to_datetime(df[c])
                    except Exception:
                        pass
            self.dataFrames[label] = df
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, label)
            self.filesList.addItem(item)
        for iid, b64 in proj.get("images", {}).items():
            try:
                self._imageCache[int(iid)] = mpimg.imread(
                    io.BytesIO(base64.b64decode(b64)), format="png")
            except Exception:
                pass
        self.seriesRows        = proj.get("series", [])
        self.referenceLineRows = proj.get("refLines", [])
        self.fillRows          = proj.get("fills", [])
        self.textAnnotationRows = proj.get("annotations", [])
        self.shapeRows         = proj.get("shapes", [])
        self.comparisonRows    = proj.get("comparisons", [])
        self.fitRows           = proj.get("fits", [])
        ll = proj.get("legendLoc")
        self._legendLoc = tuple(ll) if ll else None
        for e in self.seriesRows:
            self._tuplify(e, ("xData", "yData"))
        for e in self.comparisonRows:
            self._tuplify(e, ("refData", "cmpData"))
        for e in self.fitRows:
            self._tuplify(e, ("xData", "yData"))
        # New ids must not collide with restored ones.
        ids = [e.get("id", 0) for coll in (
            self.seriesRows, self.referenceLineRows, self.fillRows,
            self.textAnnotationRows, self.shapeRows, self.comparisonRows,
            self.fitRows) for e in coll]
        ids += list(self._imageCache.keys())
        self._idCounter = itertools.count(max(ids, default=0) + 1)
        self._rebuildSeriesTable()
        self._rebuildReferenceLineTable()
        self._rebuildFillTable()
        self._rebuildTextAnnotationTable()
        self._rebuildShapeTable()
        self._rebuildComparisonTable()
        self._rebuildFitTable()
        self._enableDataButtons(True)
        if self.filesList.count():
            self.filesList.setCurrentRow(0)
        if proj.get("ui"):
            self._applyTemplateDict(proj["ui"])
        else:
            self.drawPlot(_force=True)

    def _applyTemplateDict(self, t):
        self.titleEdit.setText(t.get("title", ""))
        self.xLabelEdit.setText(t.get("xLabel", ""))
        self.yLabelEdit.setText(t.get("yLabel", ""))
        self.xMinEdit.setText(t.get("xMin", ""))
        self.xMaxEdit.setText(t.get("xMax", ""))
        self.yMinEdit.setText(t.get("yMin", ""))
        self.yMaxEdit.setText(t.get("yMax", ""))
        self.xLogCheck.setChecked(t.get("xLog", False))
        self.yLogCheck.setChecked(t.get("yLog", False))
        self.reverseXCheck.setChecked(t.get("reverseX", False))
        self.reverseYCheck.setChecked(t.get("reverseY", False))
        self.equalAspectCheck.setChecked(t.get("equalAspect", False))
        def _num(value, default, cast):
            # Templates may be hand-edited — coerce to the widget's type and
            # fall back to the default on anything unparseable.
            try:
                return cast(value)
            except (TypeError, ValueError):
                return default

        self.boxAspectCheck.setChecked(t.get("boxAspect", False))
        self.boxAspectW.setValue(_num(t.get("boxAspectW", 4.0), 4.0, float))
        self.boxAspectH.setValue(_num(t.get("boxAspectH", 3.0), 3.0, float))
        self._setXTickSize(_num(t.get("xTickSize", 11), 11, int))
        self._setXTickCount(_num(t.get("xTickCount", 8), 8, int))
        self._setYTickSize(_num(t.get("yTickSize", 11), 11, int))
        self._setYTickCount(_num(t.get("yTickCount", 8), 8, int))
        family = t.get("fontFamily", "")
        if family:
            idx = self.fontFamilyCombo.findText(family)
            if idx >= 0:
                self.fontFamilyCombo.setCurrentIndex(idx)
            else:
                self.fontFamilyCombo.setEditText(family)
        self.showLegendCheck.setChecked(t.get("showLegend", True))
        idx = self.legendPosCombo.findText(t.get("legendPos", "best"))
        if idx >= 0:
            self.legendPosCombo.setCurrentIndex(idx)
        self.legendFrameCheck.setChecked(t.get("legendFrame", True))
        self.gridCheckBox.setChecked(t.get("showGrid", False))
        self.drawPlot(_force=True)

    # ------------------------------------------------------------------
    # Extended series data fetch (used by drawPlot)
    # ------------------------------------------------------------------

    def _buildSeriesData(self, entry):
        """Fetch and align x, y, and optional error/color columns for one series."""
        xFile, xCol = entry["xData"]
        yFile, yCol = entry["yData"]
        xDf = self.dataFrames.get(xFile)
        yDf = self.dataFrames.get(yFile)
        if xDf is None or yDf is None:
            return None
        if xCol not in xDf.columns or yCol not in yDf.columns:
            return None
        if len(xDf) != len(yDf):
            return None

        cols = {
            "x": xDf[xCol].reset_index(drop=True),
            "y": yDf[yCol].reset_index(drop=True),
        }

        errSpec = entry.get("errData")
        if errSpec:
            eFile, eCol = errSpec
            eDf = self.dataFrames.get(eFile)
            if eDf is not None and eCol in eDf.columns and len(eDf) == len(xDf):
                cols["e"] = eDf[eCol].reset_index(drop=True)

        cSpec = entry.get("colorByCol")
        if cSpec:
            cFile, cCol = cSpec
            cDf = self.dataFrames.get(cFile)
            if cDf is not None and cCol in cDf.columns and len(cDf) == len(xDf):
                cols["c"] = cDf[cCol].reset_index(drop=True)

        combined = pd.DataFrame(cols).dropna(subset=["x", "y"])
        if combined.empty:
            return None

        result = {"x": combined["x"], "y": combined["y"]}
        if "e" in combined.columns:
            result["e"] = combined["e"]
        if "c" in combined.columns:
            result["c"] = combined["c"]

        filterExpr = entry.get("filterExpr", "").strip()
        if filterExpr:
            try:
                df_f = pd.DataFrame(
                    {"x": result["x"].values, "y": result["y"].values}
                ).query(filterExpr)
                orig_idx = df_f.index
                result["x"] = pd.Series(df_f["x"].values)
                result["y"] = pd.Series(df_f["y"].values)
                for key in ("e", "c"):
                    if key in result:
                        result[key] = result[key].iloc[orig_idx].reset_index(drop=True)
            except Exception:
                pass

        return result

    def closeEvent(self, event):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter", self._splitter.saveState())
        self._settings.setValue("exportDpi", self.exportDpiSpin.value())
        self._settings.setValue("exportFormat", self.exportFormatCombo.currentText())
        self._settings.setValue("exportTransparent", self.exportTransparentCheck.isChecked())
        for name, visible in self._tabVisible.items():
            self._settings.setValue(f"tabVisible/{name}", visible)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Text annotations
    # ------------------------------------------------------------------

    def _newTextAnnotationEntry(self):
        return {
            "id":         next(self._idCounter),
            "show":       True,
            "text":       "",
            "coordType":  "axes",
            "x":          0.5,
            "y":          0.5,
            "fontSize":   12,
            "fontWeight": "normal",
            "color":      "#000000",
            "rotation":   0,
            "ha":         "center",
            "va":         "center",
        }

    def _findTextAnnotationById(self, rowId):
        return next((e for e in self.textAnnotationRows if e["id"] == rowId), None)

    def _onAnnotationDragged(self, annId, x, y):
        """User dragged a text annotation on the plot — persist its new spot."""
        entry = self._findTextAnnotationById(annId)
        if entry is None:
            return
        self._pushUndoState()
        entry["x"] = round(x, 4)
        entry["y"] = round(y, 4)
        self._rebuildTextAnnotationTable()
        self.drawPlot()

    def _onReferenceLineDragged(self, lineId, position):
        """User dragged a reference line on the plot — persist its new value."""
        entry = self._findReferenceLineById(lineId)
        if entry is None:
            return
        self._pushUndoState()
        entry["position"] = round(position, 4)
        self._rebuildReferenceLineTable()
        self.drawPlot()

    def _onMetricDragged(self, cmpId, key, x, y):
        """User dragged a comparison metric (RMSD/MAE/MSE) label on the plot.

        Not undoable — matching how metric placement is otherwise edited (the
        ⚙ details dialog), which also doesn't touch the undo stack."""
        entry = self._findComparisonById(cmpId)
        if entry is None:
            return
        settings = entry.get("metrics", {}).get(key, {}).get("settings")
        if settings is None:
            return
        settings["x"] = round(x, 4)
        settings["y"] = round(y, 4)
        self.drawPlot()

    def _onLegendDragged(self, x, y):
        """User dragged the legend — store a custom lower-left position. Not
        undoable, matching the Position dropdown (which also doesn't push undo)."""
        self._legendLoc = (round(x, 4), round(y, 4))
        self.drawPlot()

    def _addTextAnnotation(self):
        entry = self._newTextAnnotationEntry()
        dlg = TextAnnotationDialog(entry, self)
        if dlg.exec():
            entry.update(dlg.resultValues())
            if entry["text"].strip():
                self._pushUndoState()
                self.textAnnotationRows.append(entry)
                self._rebuildTextAnnotationTable()
                self.drawPlot()

    def _removeSelectedTextAnnotation(self):
        rows = sorted(
            {i.row() for i in self.textAnnotationTable.selectedIndexes()}, reverse=True
        )
        if not rows and self.textAnnotationTable.rowCount():
            rows = [self.textAnnotationTable.rowCount() - 1]
        ids = set()
        for r in rows:
            item = self.textAnnotationTable.item(r, 0)
            if item:
                ids.add(item.data(Qt.UserRole))
        if not ids:
            return
        self._pushUndoState()
        self.textAnnotationRows = [e for e in self.textAnnotationRows if e["id"] not in ids]
        self._rebuildTextAnnotationTable()
        self.drawPlot()

    def _rebuildTextAnnotationTable(self):
        self.textAnnotationTable.blockSignals(True)
        self.textAnnotationTable.setRowCount(0)
        for entry in self.textAnnotationRows:
            self._buildTextAnnotationTableRow(entry)
        self.textAnnotationTable.blockSignals(False)
        self._autoSizeTable(self.textAnnotationTable)

    def _buildTextAnnotationTableRow(self, entry):
        row   = self.textAnnotationTable.rowCount()
        self.textAnnotationTable.insertRow(row)
        rowId = entry["id"]

        showItem = QTableWidgetItem()
        showItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        showItem.setCheckState(Qt.Checked if entry.get("show", True) else Qt.Unchecked)
        showItem.setData(Qt.UserRole, rowId)
        self.textAnnotationTable.setItem(row, 0, showItem)

        textItem = QTableWidgetItem(entry.get("text", "")[:40])
        textItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.textAnnotationTable.setItem(row, 1, textItem)

        coord_label = "ax" if entry.get("coordType", "axes") == "axes" else "data"
        posItem = QTableWidgetItem(f"({entry['x']:.2f}, {entry['y']:.2f}) {coord_label}")
        posItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.textAnnotationTable.setItem(row, 2, posItem)

        editBtn = iconButton(gearIcon(self._iconColor), "Edit annotation…", diameter=self._btnDiameter())
        editBtn.clicked.connect(lambda _, rid=rowId: self._openTextAnnotationDialog(rid))
        cell = QWidget()
        cellL = QHBoxLayout(cell)
        cellL.setContentsMargins(2, 2, 2, 2)
        cellL.addWidget(editBtn, 0, Qt.AlignCenter)
        self.textAnnotationTable.setCellWidget(row, 3, cell)

        self.textAnnotationTable.setRowHeight(row, 32)

    def _openTextAnnotationDialog(self, rowId):
        entry = self._findTextAnnotationById(rowId)
        if not entry:
            return
        dlg = TextAnnotationDialog(entry, self)
        if dlg.exec():
            self._pushUndoState()
            entry.update(dlg.resultValues())
            self._rebuildTextAnnotationTable()
            self.drawPlot()

    def _onTextAnnotationShowToggle(self, item):
        if item.column() != 0:
            return
        entry = self._findTextAnnotationById(item.data(Qt.UserRole))
        if entry:
            entry["show"] = item.checkState() == Qt.Checked
            self.drawPlot()

    # ------------------------------------------------------------------
    # Icon size
    # ------------------------------------------------------------------

    def _btnDiameter(self):
        return max(20, self._uiIconSize + 4)

    def _setUiIconSize(self, size):
        self._uiIconSize = size
        qs = QSize(size, size)
        self.tabs.setIconSize(qs)
        self._rebuildSeriesTable()
        self._rebuildReferenceLineTable()
        self._rebuildFillTable()
        self._rebuildTextAnnotationTable()
        self._rebuildShapeTable()

    # ------------------------------------------------------------------
    # Tab visibility management
    # ------------------------------------------------------------------

    def _rebuildTabWidget(self):
        """Remove all tabs and re-add the currently visible ones (icon-only)."""
        current_name = self._currentTabName()
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for name, label, icon in self._tabDefs:
            if self._tabVisible.get(name, True):
                idx = self.tabs.addTab(self._tabWidgets[name], icon, "")
                self.tabs.setTabToolTip(idx, label)
        self.tabs.blockSignals(False)
        # Restore focus to the same tab if it is still visible
        if current_name and self._tabVisible.get(current_name, True):
            idx = self._tabIndex(current_name)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)

    def _currentTabName(self):
        idx = self.tabs.currentIndex()
        visible = [n for n, _, _ in self._tabDefs if self._tabVisible.get(n, True)]
        if 0 <= idx < len(visible):
            return visible[idx]
        return None

    def _tabIndex(self, name):
        visible = [n for n, _, _ in self._tabDefs if self._tabVisible.get(n, True)]
        try:
            return visible.index(name)
        except ValueError:
            return -1

    def _showTabVisibilityMenu(self):
        menu = QMenu(self)
        visible_count = sum(1 for n, _, _ in self._tabDefs if self._tabVisible.get(n, True))
        for name, label, _ in self._tabDefs:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self._tabVisible.get(name, True))
            # Prevent hiding the last visible tab
            if self._tabVisible.get(name, True) and visible_count <= 1:
                act.setEnabled(False)
            act.triggered.connect(lambda checked, n=name: self._setTabVisible(n, checked))
        btn = self.tabs.cornerWidget()
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _setTabVisible(self, name, visible):
        self._tabVisible[name] = visible
        self._rebuildTabWidget()

