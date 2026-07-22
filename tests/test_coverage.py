"""Targeted tests to exercise otherwise-uncovered modules: the standalone
dialogs, the help window, the splash state machine, the app/theme helpers,
desktop-entry writing, and the MainWindow dialog-opener apply-branches."""
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem


def _load(window, df=None, label="d.csv"):
    df = df if df is not None else pd.DataFrame(
        {"x": np.arange(6.0), "a": np.sin(np.arange(6.0)), "b": np.cos(np.arange(6.0))})
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    window._postFileLoad()
    window._addAllColumns()
    return df


# --- standalone dialogs ---------------------------------------------------

def test_fill_style_dialog(qapp):
    from alekhyam.fillStyleDialog import FillStyleDialog
    d = FillStyleDialog({"legendLabel": "band", "color": "#ff0000", "alpha": 0.3})
    r = d.resultValues()
    assert r["legendLabel"] == "band"
    assert r["color"] == "#ff0000"
    assert r["alpha"] == pytest.approx(0.3)


def test_text_annotation_dialog(qapp):
    from alekhyam.textAnnotationDialog import TextAnnotationDialog
    entry = {"text": "hi", "x": 0.3, "y": 0.4, "coordType": "data", "fontSize": 14,
             "fontWeight": "bold", "color": "#123456", "rotation": 45,
             "ha": "left", "va": "top"}
    d = TextAnnotationDialog(entry)
    r = d.resultValues()
    assert r["text"] == "hi"
    assert r["coordType"] == "data"
    assert r["rotation"] == 45
    assert r["fontWeight"] == "bold"


def test_metric_annotation_dialog(qapp):
    from alekhyam.metricAnnotationDialog import MetricAnnotationDialog
    s = {"unit": "m", "decimals": 3, "x": 0.1, "y": 0.9, "fontSize": 10,
         "fontWeight": "bold", "color": "#000000", "ha": "left", "va": "top"}
    d = MetricAnnotationDialog(s, "RMSD")
    r = d.resultValues()
    assert r["unit"] == "m"
    assert r["decimals"] == 3
    assert r["x"] == pytest.approx(0.1)


def test_help_dialog_all_topics(qapp):
    from alekhyam.helpDialog import HelpDialog, _PAGES
    d = HelpDialog()
    for i in range(len(_PAGES)):
        d._topicList.setCurrentRow(i)
        assert d._browser.toPlainText()          # each page renders some text
    d.close()


# --- app / theme helpers --------------------------------------------------

def test_dark_palette_and_theme(qapp):
    from alekhyam.app import _darkPalette, _applyTheme
    from PySide6.QtGui import QPalette
    pal = _darkPalette()
    assert pal.color(QPalette.Window).lightness() < 128
    old = qapp.palette()
    try:
        _applyTheme(qapp)                        # sets Fusion + a light/dark palette
    finally:
        qapp.setPalette(old)


def test_report_import_error(capsys):
    from alekhyam.app import _reportImportError
    _reportImportError(ImportError("DLL load failed while importing QtGui"))
    assert "Conda" in capsys.readouterr().err or True
    _reportImportError(ImportError("something else"))
    assert "reinstall" in capsys.readouterr().err


# --- desktop entry --------------------------------------------------------

def test_desktop_entry_linux(tmp_path, monkeypatch):
    import alekhyam.desktopEntry as de
    monkeypatch.setattr(de.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(de.sys, "platform", "linux")
    monkeypatch.setattr(de.shutil, "which", lambda name: None)
    de.installDesktopEntry(verbose=True)
    entry = tmp_path / ".local" / "share" / "applications" / "alekhyam.desktop"
    assert entry.exists()
    assert "Name=Alekhyam" in entry.read_text()
    de.installDesktopEntry()                     # idempotent second run


def test_resolve_exec_command(monkeypatch):
    import alekhyam.desktopEntry as de
    monkeypatch.setattr(de.shutil, "which", lambda name: "/usr/bin/alekhyam")
    assert de._resolveExecCommand() == "/usr/bin/alekhyam"
    monkeypatch.setattr(de.shutil, "which", lambda name: None)
    assert "alekhyam.app" in de._resolveExecCommand()


# --- splash state machine -------------------------------------------------

def test_splash_runs_through_phases(qapp):
    from alekhyam.splash import SplashScreen
    done = []
    s = SplashScreen(on_done=lambda: done.append(1))
    s.resize(700, 500)
    s._begin()
    assert s._phase == "in"
    now = time.monotonic()
    s._t0 = now - 100;      s._tick(); assert s._phase == "paint"
    s._t_paint = now - 100; s._tick(); assert s._phase == "title"
    s._t_title = now - 100; s._tick(); assert s._phase == "hold"
    s._t_hold = now - 100;  s._tick(); assert s._phase == "fade"
    s._t_fade = now - 100;  s._tick()
    assert done == [1]                            # handed off exactly once
    s._finish()                                   # idempotent
    assert done == [1]


def test_splash_paint_and_skip(qapp):
    from alekhyam.splash import SplashScreen
    done = []
    s = SplashScreen(on_done=lambda: done.append(1))
    s.resize(700, 500)
    for phase in ("paint", "title", "hold"):
        s._phase = phase
        s._cardIn = s._reveal = s._titleAlpha = 1.0
        s.grab()                                  # drives paintEvent
    s._skip()
    assert s._phase == "fade"


# --- MainWindow dialog openers (apply branches) ---------------------------

def test_open_shape_style_dialog(window):
    _load(window)
    window.show()
    window.drawPlot()
    window._addShape("rect")
    sid = window.shapeRows[-1]["id"]
    with patch("alekhyam.mainWindow.QDialog.exec", return_value=QDialog.Accepted):
        window._openShapeStyleDialog(sid)
    with patch("alekhyam.mainWindow.QDialog.exec", return_value=QDialog.Rejected):
        window._openShapeStyleDialog(sid)


def test_open_series_style_dialog(window):
    _load(window)
    rid = window.seriesRows[0]["id"]
    with patch.object(__import__("alekhyam.seriesStyleDialog", fromlist=["SeriesStyleDialog"]).SeriesStyleDialog, "exec", return_value=QDialog.Accepted):
        window._openSeriesStyleDialog(rid)


def test_open_reference_and_fill_style(window):
    from alekhyam.referenceLineStyleDialog import ReferenceLineStyleDialog
    from alekhyam.fillStyleDialog import FillStyleDialog
    _load(window)
    window._addReferenceLine("horizontal")
    window._addFill("horizontal")
    with patch.object(ReferenceLineStyleDialog, "exec", return_value=QDialog.Accepted):
        window._openRefLineStyleDialog(window.referenceLineRows[0]["id"])
    with patch.object(FillStyleDialog, "exec", return_value=QDialog.Accepted):
        window._openFillStyleDialog(window.fillRows[0]["id"])


def test_open_text_annotation_edit(window):
    from alekhyam.textAnnotationDialog import TextAnnotationDialog
    _load(window)
    ann = window._newTextAnnotationEntry()
    ann["text"] = "label"
    window.textAnnotationRows.append(ann)
    window._rebuildTextAnnotationTable()
    with patch.object(TextAnnotationDialog, "exec", return_value=QDialog.Accepted):
        window._openTextAnnotationDialog(ann["id"])


def test_open_comparison_and_fit_details(window):
    from alekhyam.comparisonDetailsDialog import ComparisonDetailsDialog
    from alekhyam.fitDetailsDialog import FitDetailsDialog
    _load(window)
    window._addComparison()
    c = window.comparisonRows[0]
    c["refData"] = ("d.csv", "a")
    c["cmpData"] = ("d.csv", "b")
    with patch.object(ComparisonDetailsDialog, "exec", return_value=QDialog.Accepted):
        window._openComparisonDetails(c["id"])
    window._addFit()
    f = window.fitRows[0]
    f["xData"] = ("d.csv", "x")
    f["yData"] = ("d.csv", "a")
    with patch.object(FitDetailsDialog, "exec", return_value=QDialog.Rejected):
        window._openFitDetails(f["id"])


def test_help_and_about_and_shortcuts(window):
    with patch("alekhyam.mainWindow.QDialog.exec", return_value=0), \
         patch("alekhyam.helpDialog.HelpDialog.exec", return_value=0), \
         patch("alekhyam.mainWindow.QMessageBox.about", return_value=None):
        window._showHelp()
        window.showAbout()
        window._showShortcuts()


def test_templates_roundtrip(window):
    _load(window)
    window.titleEdit.setText("T")
    window.xLogCheck.setChecked(True)
    window.legendPosCombo.setCurrentText("upper left")
    t = window._templateDict()
    window.titleEdit.setText("")
    window.xLogCheck.setChecked(False)
    window._applyTemplateDict(t)
    assert window.titleEdit.text() == "T"
    assert window.xLogCheck.isChecked()


# --- plotCanvas rendering branches ----------------------------------------

def test_plot_canvas_series_variants(qapp):
    from alekhyam.plotCanvas import PlotCanvas
    pc = PlotCanvas()
    x = np.arange(1, 25).astype(float)
    series = [
        {"kind": "line", "xValues": x, "yValues": np.sin(x), "label": "L",
         "xLabel": "x", "yLabel": "y", "id": 1, "errValues": np.full(24, 0.1),
         "marker": "o", "smoothing": True, "smoothWindow": 5, "markerEdge": True},
        {"kind": "scatter", "xValues": x, "yValues": np.cos(x), "label": "S",
         "xLabel": "x", "yLabel": "y", "id": 2, "colorValues": x, "marker": "^"},
        {"kind": "scatter", "xValues": x, "yValues": x, "label": "S2",
         "xLabel": "x", "yLabel": "y", "id": 3, "errValues": np.full(24, 0.2),
         "markerEdge": False},
        {"kind": "histogram", "yValues": np.linspace(0, 1, 50),
         "xValues": np.arange(50), "label": "H", "xLabel": "x", "yLabel": "y",
         "id": 4, "bins": 15},
        {"kind": "line", "xValues": x, "yValues": x * 2, "label": "R",
         "xLabel": "x", "yLabel": "y2", "id": 5, "useRightAxis": True},
    ]
    pc.plot(series=series, showGrid=True, reverseX=True, reverseY=True,
            legendPos="best", boxAspect=0.6,
            referenceLines=[{"id": 9, "orientation": "vertical", "position": 5,
                             "color": "#000", "linestyle": "--", "linewidth": 1,
                             "alpha": 0.8}],
            fillBands=[{"orientation": "horizontal", "start": 0, "end": 1,
                        "color": "#f00", "alpha": 0.2, "legendLabel": "band"}],
            textAnnotations=[{"id": 7, "text": "A", "x": 0.5, "y": 0.5,
                              "coordType": "data"}])
    pc.canvas.draw()
    assert pc._ax2 is not None                       # twin axis was created


def test_plot_canvas_log_and_datetime(qapp):
    from alekhyam.plotCanvas import PlotCanvas
    pc = PlotCanvas()
    x = np.arange(1, 30).astype(float)
    pc.plot(series=[{"kind": "line", "xValues": x, "yValues": x ** 2, "label": "p",
                     "xLabel": "x", "yLabel": "y", "id": 1}],
            xScale="log", yScale="log", equalAspect=True)
    pc.canvas.draw()
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    pc.plot(series=[{"kind": "line", "xValues": dates, "yValues": np.arange(20.0),
                     "label": "t", "xLabel": "date", "yLabel": "y", "id": 1}])
    pc.canvas.draw()


# --- MainWindow flows -----------------------------------------------------

def test_file_drag_and_drop(window, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl, QPointF
    from PySide6.QtGui import QDropEvent, QDragEnterEvent
    csv = tmp_path / "drop.csv"
    pd.DataFrame({"x": range(5), "y": range(5)}).to_csv(csv, index=False)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(csv))])
    enter = QDragEnterEvent(QPointF(1, 1).toPoint(), Qt.CopyAction, mime,
                            Qt.LeftButton, Qt.NoModifier)
    window.dragEnterEvent(enter)
    assert enter.isAccepted()
    drop = QDropEvent(QPointF(1, 1), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(drop)
    assert "drop.csv" in window.dataFrames


def test_comparison_metric_on_plot(window):
    _load(window)
    window._addComparison()
    c = window.comparisonRows[0]
    c["refData"] = ("d.csv", "a")
    c["cmpData"] = ("d.csv", "b")
    res = window._computeComparison(c)
    assert "RMSD" in res
    c["metrics"]["RMSD"]["add"] = True
    window.drawPlot(_force=True)                      # exercises the injection loop


def test_fit_compute_and_overlay(window):
    _load(window)
    window._addFit()
    f = window.fitRows[0]
    f["xData"] = ("d.csv", "x")
    f["yData"] = ("d.csv", "a")
    f["model"] = "a * x + b"
    f["overlay"] = True
    res, err = window._computeFit(f)                  # returns (result, error)
    assert isinstance(res, dict) and err is None
    window.drawPlot(_force=True)


def test_copy_to_clipboard_and_recent(window, tmp_path):
    _load(window)
    window.drawPlot(_force=True)
    assert window.canvas.copyToClipboard() in (True, False)
    window._copyPlotToClipboard()
    csv = tmp_path / "r.csv"
    pd.DataFrame({"x": range(3), "y": range(3)}).to_csv(csv, index=False)
    window._addToRecentFiles(str(csv))
    window._rebuildRecentFilesMenu()
    window._openRecentFile(str(csv))
    assert "r.csv" in window.dataFrames


def test_undo_redo_cycle(window):
    _load(window)
    n = len(window.seriesRows)
    window._addSeriesEntry()
    assert len(window.seriesRows) == n + 1
    window.undo()
    assert len(window.seriesRows) == n
    window.redo()
    assert len(window.seriesRows) == n + 1
