"""Tests for the quality-of-life batch: keyboard/selection, arrange tools,
snapping, plot interaction, data export, project save/open, live reload."""
import os

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QListWidgetItem


def _load(window, df=None, label="d.csv"):
    df = df if df is not None else pd.DataFrame(
        {"time": np.arange(6.0), "a": np.arange(6.0),
         "b": np.arange(6.0) + 1, "c": np.arange(6.0) + 2})
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    window._postFileLoad()
    window._addAllColumns()
    return df


# --- keyboard & selection -------------------------------------------------

def test_series_multi_select(window):
    _load(window)
    assert window.seriesTable.selectionMode() == QAbstractItemView.ExtendedSelection


def test_series_delete_and_duplicate_signals(window):
    _load(window)
    n = len(window.seriesRows)
    window.seriesTable.selectRow(0)
    window.seriesTable.deleteRequested.emit()
    assert len(window.seriesRows) == n - 1
    window.seriesTable.selectRow(0)
    window.seriesTable.duplicateRequested.emit()
    assert len(window.seriesRows) == n


def test_solo_and_show_all(window):
    _load(window)
    window.seriesTable.selectRow(0)
    window._soloSelectedSeries()
    shows = [e["show"] for e in window.seriesRows]
    assert shows[0] is True and not any(shows[1:])
    window._showAllSeries()
    assert all(e["show"] for e in window.seriesRows)


def test_searchable_combo_keeps_item_data(window):
    _load(window)
    combo = window.seriesTable.cellWidget(0, 2)
    assert combo.isEditable()
    assert combo.currentData() is not None       # (file, column) tuple intact


def test_tab_shortcut_switches(window):
    _load(window)
    window._switchToVisibleTab(2)
    assert window.tabs.currentIndex() == 2
    window._switchToVisibleTab(99)               # out of range → no-op
    assert window.tabs.currentIndex() == 2


# --- shape arrange tools --------------------------------------------------

def _plotted_shape(window, kind="rect"):
    _load(window)
    window.show()
    window.drawPlot()
    window.canvas.canvas.draw()
    window._addShape(kind)
    return window.shapeRows[-1]["id"]


def test_shape_duplicate(window):
    sid = _plotted_shape(window)
    n = len(window.shapeRows)
    window._duplicateShape(sid)
    assert len(window.shapeRows) == n + 1
    assert window.canvas._selectedShapeId != sid   # the copy is selected


def test_shape_nudge_moves_and_clamps(window):
    sid = _plotted_shape(window)
    e = window._findShapeById(sid)
    x0 = e["x"]
    window._onShapeNudge(sid, 0.05, -0.03)
    assert e["x"] == pytest.approx(x0 + 0.05, abs=1e-6)
    e["x"] = 0.99
    window._onShapeNudge(sid, 0.2, 0.0)            # would exceed 1 - w → clamp
    assert e["x"] <= 1.0 - e["w"] + 1e-9


def test_shape_zorder(window):
    sid = _plotted_shape(window)
    window._addShape("ellipse")                    # now two shapes
    window._reorderShape(sid, "front")
    assert window.shapeRows[-1]["id"] == sid
    window._reorderShape(sid, "back")
    assert window.shapeRows[0]["id"] == sid


# --- data features --------------------------------------------------------

def test_apply_palette_recolours_all_series(window):
    _load(window)
    before = [e["color"] for e in window.seriesRows]
    window._applyPalette("Viridis")
    after = [e["color"] for e in window.seriesRows]
    assert after != before
    assert all(c.startswith("#") for c in after)


def test_increment_name():
    from alekhyam.mainWindow import MainWindow
    assert MainWindow._incrementName("plot") == "plot_1"
    assert MainWindow._incrementName("plot_1") == "plot_2"
    assert MainWindow._incrementName("chart3") == "chart4"


def test_export_plotted_data_csv(window, tmp_path):
    from unittest.mock import patch
    _load(window)
    out = tmp_path / "pd.csv"
    with patch("alekhyam.mainWindow.QFileDialog.getSaveFileName",
               return_value=(str(out), "")):
        window._exportData()
    back = pd.read_csv(out)
    assert len(back) == 6
    assert any("· x" in c for c in back.columns) and any("· y" in c for c in back.columns)


def test_column_stats_dialog_builds(window):
    from unittest.mock import patch
    _load(window)
    with patch("alekhyam.mainWindow.QDialog.exec", return_value=0):
        window._showColumnStats()          # should build + show without error


# --- live reload ----------------------------------------------------------

def test_live_reload_picks_up_file_changes(window, tmp_path):
    csv = tmp_path / "data.csv"
    pd.DataFrame({"x": range(5), "y": range(5)}).to_csv(csv, index=False)
    assert window._loadFile(str(csv))
    window._postFileLoad()
    assert str(csv.resolve()) in [str(p) for p in [os.path.abspath(str(csv))]]
    assert len(window.dataFrames["data.csv"]) == 5

    pd.DataFrame({"x": range(8), "y": range(8), "z": range(8)}).to_csv(csv, index=False)
    window._onFileChanged(os.path.abspath(str(csv)))
    window._flushReloads()
    df = window.dataFrames["data.csv"]
    assert len(df) == 8 and "z" in df.columns

    # toggle off → change ignored, manual reload still works
    pd.DataFrame({"x": range(3), "y": range(3)}).to_csv(csv, index=False)
    window._setLiveReload(False)
    window._onFileChanged(os.path.abspath(str(csv)))
    window._flushReloads()
    assert len(window.dataFrames["data.csv"]) == 8
    window.reloadAllFiles()
    assert len(window.dataFrames["data.csv"]) == 3


# --- project save / open --------------------------------------------------

def test_project_save_open_roundtrip(window, tmp_path):
    import matplotlib.image as mpimg
    from unittest.mock import patch
    from alekhyam.mainWindow import MainWindow

    _load(window)
    window.show()
    window.titleEdit.setText("My chart")
    window.gridCheckBox.setChecked(True)
    window._addShape("star")
    window.shapeRows[-1].update(angle=30.0, color="#8e44ad")
    window._addReferenceLine("horizontal")
    window.referenceLineRows[0]["position"] = 0.5
    # embed an image shape
    arr = np.zeros((20, 30, 3), dtype=np.uint8)
    arr[:, :, 2] = 200
    p = tmp_path / "i.png"
    mpimg.imsave(str(p), arr)
    e = window._newShapeEntry("image")
    e["imageId"] = e["id"]
    window._imageCache[e["id"]] = mpimg.imread(str(p))
    window.shapeRows.append(e)
    window.drawPlot()
    n_series, n_shapes = len(window.seriesRows), len(window.shapeRows)

    proj = tmp_path / "p.plot"
    with patch("alekhyam.mainWindow.QFileDialog.getSaveFileName", return_value=(str(proj), "")):
        window._saveProject()
    assert proj.exists()

    w2 = MainWindow()
    try:
        w2.show()
        w2._openProject(str(proj))
        assert list(w2.dataFrames) == ["d.csv"]
        assert len(w2.seriesRows) == n_series
        assert len(w2.shapeRows) == n_shapes
        assert w2.titleEdit.text() == "My chart"
        assert w2.gridCheckBox.isChecked()
        assert any(s.get("angle") == 30.0 for s in w2.shapeRows)
        assert isinstance(w2.seriesRows[0]["xData"], tuple)
        assert len(w2._imageCache) == 1
        assert w2.referenceLineRows[0]["position"] == 0.5
    finally:
        w2.close()


# --- plot interaction -----------------------------------------------------

def test_right_click_adds_shape_at_point(window):
    _plotted_shape(window, "rect")            # ensure a plot + one shape exists
    n = len(window.shapeRows)
    window._addShapeAt("ellipse", 0.6, 0.3)
    assert len(window.shapeRows) == n + 1
    e = window.shapeRows[-1]
    assert (e["x"] + e["w"] / 2) == pytest.approx(0.6, abs=0.01)
    assert (e["y"] + e["h"] / 2) == pytest.approx(0.3, abs=0.01)


def test_legend_click_toggles_series(window):
    from matplotlib.backend_bases import MouseEvent
    _load(window)
    window.showLegendCheck.setChecked(True)
    window.legendPosCombo.setCurrentText("upper right")
    window.show()
    window.drawPlot()
    window.canvas.canvas.draw()
    leg = next(d["artist"] for d in window.canvas._draggables if d["kind"] == "legend")
    txt = leg.get_texts()[0]
    sid = window.canvas._legendLabelToId[txt.get_text()]
    entry = window._findSeriesById(sid)
    assert entry["show"] is True
    be = txt.get_window_extent()
    cx, cy = (be.x0 + be.x1) / 2, (be.y0 + be.y1) / 2
    window.canvas._onDragPress(MouseEvent("button_press_event", window.canvas.canvas, cx, cy, button=1))
    window.canvas._onDragRelease(MouseEvent("button_release_event", window.canvas.canvas, cx, cy, button=1))
    assert entry["show"] is False


def test_hover_readout_finds_nearest_point(window):
    from matplotlib.backend_bases import MouseEvent
    df = pd.DataFrame({"x": np.linspace(0, 10, 40), "sine": np.sin(np.linspace(0, 10, 40))})
    _load(window, df)
    window.show()
    window.drawPlot()
    window.canvas.canvas.draw()
    assert len(window.canvas._hoverData) >= 1
    ax = window.canvas.axes
    xi, yi = df["x"].iloc[20], df["sine"].iloc[20]
    px, py = ax.transData.transform((xi, yi))
    window.canvas._onDragMotion(MouseEvent("motion_notify_event", window.canvas.canvas, px, py))
    assert window.canvas._hoverMarker.get_visible()
    assert f"{xi:.4g}" in window.canvas._hoverText.get_text()
    window.canvas._onDragMotion(MouseEvent("motion_notify_event", window.canvas.canvas, px, py + 250))
    assert not window.canvas._hoverMarker.get_visible()


def test_hover_ignores_nonfinite_points(window):
    """A NaN/inf transformed point (e.g. a value <= 0 on a log axis) must not
    starve argmin — a valid nearer point should still register."""
    from matplotlib.backend_bases import MouseEvent
    _load(window, pd.DataFrame({"x": np.arange(10.0), "y": np.arange(10.0)}))
    window.show()
    window.drawPlot()
    window.canvas.canvas.draw()
    xa = np.arange(10.0)
    ya = np.arange(10.0)
    ya[3] = np.nan                                   # a hole in the series
    window.canvas._hoverData = [(xa, ya, "#000000", "S", window.canvas.axes)]
    px, py = window.canvas.axes.transData.transform((7.0, 7.0))
    window.canvas._onDragMotion(MouseEvent("motion_notify_event", window.canvas.canvas, px, py))
    assert window.canvas._hoverMarker.get_visible()
    assert "x = 7" in window.canvas._hoverText.get_text()


def test_snap_aligns_to_center_with_guide(window):
    from matplotlib.backend_bases import MouseEvent
    sid = _plotted_shape(window)
    e = window._findShapeById(sid)
    e.update(x=0.1, y=0.1, w=0.2, h=0.2)
    window.drawPlot()
    window.canvas.selectShape(sid)
    window.canvas.canvas.draw()
    ax = window.canvas.axes

    def m(n, fr):
        p = ax.transAxes.transform(fr)
        return MouseEvent(n, window.canvas.canvas, p[0], p[1], button=1)

    window.canvas._onDragPress(m("button_press_event", (0.2, 0.2)))     # grab centre
    window.canvas._onDragMotion(m("motion_notify_event", (0.497, 0.6)))  # centre ≈ 0.5
    assert window.canvas._guideX is not None and window.canvas._guideX.get_visible()
    assert (window.canvas._shapeById(sid)["x"] + 0.1) == pytest.approx(0.5, abs=1e-6)
    window.canvas._onDragRelease(m("button_release_event", (0.497, 0.6)))
    assert window.canvas._guideX is None                                 # cleaned up


def test_alt_disables_snap(window):
    from unittest.mock import patch
    from matplotlib.backend_bases import MouseEvent
    sid = _plotted_shape(window)
    e = window._findShapeById(sid)
    e.update(x=0.1, y=0.1, w=0.2, h=0.2)
    window.drawPlot()
    window.canvas.selectShape(sid)
    window.canvas.canvas.draw()
    ax = window.canvas.axes
    p0 = ax.transAxes.transform((0.2, 0.2))
    window.canvas._onDragPress(MouseEvent("button_press_event", window.canvas.canvas, p0[0], p0[1], button=1))
    with patch("alekhyam.plotCanvas.QApplication.keyboardModifiers", return_value=Qt.AltModifier):
        p1 = ax.transAxes.transform((0.498, 0.5))
        window.canvas._onDragMotion(MouseEvent("motion_notify_event", window.canvas.canvas, p1[0], p1[1], button=1))
        assert not window.canvas._guideX.get_visible()
    window.canvas._onDragRelease(MouseEvent("button_release_event", window.canvas.canvas, p1[0], p1[1], button=1))


def test_shape_lock_blocks_plot_selection(window):
    from matplotlib.backend_bases import MouseEvent
    sid = _plotted_shape(window)
    e = window._findShapeById(sid)
    e.update(x=0.35, y=0.35, w=0.3, h=0.3)
    window._toggleShapeLock(sid)
    assert e["locked"] is True
    window.drawPlot()
    window.canvas.canvas.draw()
    window.canvas.clearShapeSelection()
    px, py = window.canvas.axes.transAxes.transform((0.5, 0.5))
    window.canvas._onDragPress(MouseEvent("button_press_event", window.canvas.canvas, px, py, button=1))
    assert window.canvas._selectedShapeId != sid
