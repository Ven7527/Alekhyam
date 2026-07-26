"""Comprehensive tests for v1.1–1.2 features and multi-operation edge cases.

Covers: extended series data (error/color/filter), style-dialog round-trips,
the full drawPlot pipeline for every plot type and overlay, computed columns,
plot templates, and state consistency across interleaved
undo / redo / reorder / clear operations. Includes regression tests for the
datetime + curve-fit crash and the render-error safety net.
"""
import json

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from alekhyam.seriesStyleDialog import SeriesStyleDialog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(window, label, df, select=False):
    """Add a dataframe to the window exactly as the loader would."""
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    if select:
        window.filesList.setCurrentItem(item)
    return label


def _series(window, xcol, ycol, label, **overrides):
    """Create, register, and return a series entry referencing (label, col)."""
    entry = window._newSeriesEntry(
        xDefault=(label, xcol), yDefault=(label, ycol),
        kind=overrides.pop("kind", "line"),
    )
    entry.update(overrides)
    window.seriesRows.append(entry)
    return entry


@pytest.fixture
def rich_df():
    return pd.DataFrame({
        "x":   [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "y":   [1.0, 4.0, 9.0, 16.0, 25.0, 36.0],
        "err": [0.1, 0.2, 0.15, 0.3, 0.25, 0.2],
        "c":   [10, 20, 30, 40, 50, 60],
        "neg": [-1.0, -2.0, 3.0, -4.0, 5.0, -6.0],
    })


# ---------------------------------------------------------------------------
# _buildSeriesData — error / color / filter alignment
# ---------------------------------------------------------------------------

def test_build_series_data_basic(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv")
    data = window._buildSeriesData(e)
    assert data is not None
    assert list(data["x"]) == [1, 2, 3, 4, 5, 6]
    assert "e" not in data and "c" not in data


def test_build_series_data_with_error_column(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", errData=("a.csv", "err"))
    data = window._buildSeriesData(e)
    assert "e" in data
    assert len(data["e"]) == len(data["y"])


def test_build_series_data_error_column_wrong_length_ignored(window, rich_df):
    _register(window, "a.csv", rich_df)
    _register(window, "b.csv", rich_df.head(3))
    e = _series(window, "x", "y", "a.csv", errData=("b.csv", "err"))
    data = window._buildSeriesData(e)
    assert "e" not in data   # mismatched length → silently dropped


def test_build_series_data_with_color_column(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", kind="scatter", colorByCol=("a.csv", "c"))
    data = window._buildSeriesData(e)
    assert "c" in data
    assert list(data["c"]) == [10, 20, 30, 40, 50, 60]


def test_build_series_data_filter(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", filterExpr="y > 10")
    data = window._buildSeriesData(e)
    # y = 16, 25, 36 survive (x = 4, 5, 6)
    assert list(data["x"]) == [4, 5, 6]
    assert list(data["y"]) == [16, 25, 36]


def test_build_series_data_filter_keeps_error_alignment(window, rich_df):
    """The error column must stay row-aligned after a filter drops rows."""
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv",
                errData=("a.csv", "err"), filterExpr="x >= 4")
    data = window._buildSeriesData(e)
    assert list(data["x"]) == [4, 5, 6]
    # err values for x=4,5,6 are the 4th,5th,6th entries
    assert list(data["e"]) == pytest.approx([0.3, 0.25, 0.2])


def test_build_series_data_filter_keeps_color_alignment(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", kind="scatter",
                colorByCol=("a.csv", "c"), filterExpr="x <= 2")
    data = window._buildSeriesData(e)
    assert list(data["x"]) == [1, 2]
    assert list(data["c"]) == [10, 20]


def test_build_series_data_filter_removing_all_rows(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", filterExpr="x > 999")
    data = window._buildSeriesData(e)
    assert data is not None            # does not crash
    assert len(data["x"]) == 0


def test_build_series_data_invalid_filter_ignored(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", filterExpr="nonexistent > 5")
    data = window._buildSeriesData(e)
    # invalid query is swallowed → unfiltered data returned
    assert len(data["x"]) == 6


def test_build_series_data_drops_nan(window):
    df = pd.DataFrame({"x": [1, 2, np.nan, 4], "y": [10, np.nan, 30, 40]})
    _register(window, "n.csv", df)
    e = _series(window, "x", "y", "n.csv")
    data = window._buildSeriesData(e)
    assert len(data["x"]) == 2


def test_build_series_data_length_mismatch(window, rich_df):
    _register(window, "a.csv", rich_df)
    _register(window, "b.csv", rich_df.head(3))
    e = window._newSeriesEntry(xDefault=("a.csv", "x"), yDefault=("b.csv", "y"))
    assert window._buildSeriesData(e) is None


# ---------------------------------------------------------------------------
# SeriesStyleDialog — round-trips per kind
# ---------------------------------------------------------------------------

def test_style_dialog_line_roundtrip(qapp, rich_df):
    dfs = {"a.csv": rich_df}
    entry = {
        "kind": "line", "color": "#ff0000", "alpha": 0.5, "linestyle": "--",
        "linewidth": 3.0, "marker": None, "markerEdge": True, "useRightAxis": False,
        "legendLabel": "L1", "errData": ("a.csv", "err"), "smoothing": True,
        "smoothWindow": 7, "filterExpr": "y > 1",
    }
    rv = SeriesStyleDialog(entry, None, dataFrames=dfs).resultValues()
    assert rv["errData"] == ("a.csv", "err")
    assert rv["smoothing"] is True and rv["smoothWindow"] == 7
    assert rv["filterExpr"] == "y > 1"
    assert rv["linestyle"] == "--" and rv["linewidth"] == 3.0


def test_style_dialog_scatter_colorby_roundtrip(qapp, rich_df):
    dfs = {"a.csv": rich_df}
    entry = {
        "kind": "scatter", "color": "#00ff00", "alpha": 0.8, "marker": "o",
        "scatterSize": 80, "markerEdge": False, "useRightAxis": True,
        "legendLabel": "", "colorByCol": ("a.csv", "c"), "errData": None,
        "filterExpr": "",
    }
    rv = SeriesStyleDialog(entry, None, dataFrames=dfs).resultValues()
    assert rv["colorByCol"] == ("a.csv", "c")
    assert rv["scatterSize"] == 80
    assert rv["useRightAxis"] is True


def test_style_dialog_histogram_roundtrip(qapp, rich_df):
    dfs = {"a.csv": rich_df}
    entry = {"kind": "histogram", "color": "#0000ff", "alpha": 0.7,
             "bins": 42, "legendLabel": "H", "filterExpr": "y < 4"}
    rv = SeriesStyleDialog(entry, None, dataFrames=dfs).resultValues()
    assert rv["bins"] == 42
    assert "marker" not in rv          # histograms have no marker
    assert rv["filterExpr"] == "y < 4"


def test_style_dialog_error_disabled_returns_none(qapp, rich_df):
    dfs = {"a.csv": rich_df}
    entry = {"kind": "line", "errData": None, "color": None, "alpha": 0.9,
             "linestyle": "-", "linewidth": 2.5, "marker": None,
             "markerEdge": True, "useRightAxis": False, "legendLabel": ""}
    dlg = SeriesStyleDialog(entry, None, dataFrames=dfs)
    assert dlg._errCheck.isChecked() is False
    assert dlg.resultValues()["errData"] is None


# ---------------------------------------------------------------------------
# drawPlot pipeline — every plot type / overlay renders without error
# ---------------------------------------------------------------------------

def _artist_count(window):
    ax = window.canvas.axes
    return len(ax.get_lines()) + len(ax.collections) + len(ax.patches)


def test_drawplot_line(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    window.drawPlot(_force=True)
    assert len(window.canvas.axes.get_lines()) >= 1


def test_drawplot_scatter(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv", kind="scatter")
    window.drawPlot(_force=True)
    assert len(window.canvas.axes.collections) >= 1


def test_drawplot_histogram(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv", kind="histogram", bins=5)
    window.drawPlot(_force=True)
    assert len(window.canvas.axes.patches) >= 1


def test_drawplot_error_bars(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv", errData=("a.csv", "err"))
    window.drawPlot(_force=True)
    assert window.canvas.axes.has_data()


def test_drawplot_smoothing_adds_overlay(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv", smoothing=True, smoothWindow=3)
    window.drawPlot(_force=True)
    # base line + dashed rolling-average overlay
    assert len(window.canvas.axes.get_lines()) >= 2


def test_drawplot_colorby_scatter(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv", kind="scatter", colorByCol=("a.csv", "c"))
    window.drawPlot(_force=True)
    assert len(window.canvas.axes.collections) >= 1


def test_drawplot_right_axis_creates_twin(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    _series(window, "x", "c", "a.csv", useRightAxis=True)
    window.drawPlot(_force=True)
    assert window.canvas._ax2 is not None


def test_drawplot_twin_axis_no_accumulation(window, rich_df):
    """Repeated redraws must not stack extra twin axes on the figure."""
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    _series(window, "x", "c", "a.csv", useRightAxis=True)
    for _ in range(15):
        window.drawPlot(_force=True)
    assert len(window.canvas.figure.axes) == 2


def test_reverse_x_axis(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    window.drawPlot(_force=True)
    lo, hi = window.canvas.axes.get_xlim()
    assert lo < hi                              # ascending by default
    window.reverseXCheck.setChecked(True)       # triggers a redraw
    lo, hi = window.canvas.axes.get_xlim()
    assert lo > hi                              # now descending


def test_reverse_axis_stable_across_redraws(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    window.reverseXCheck.setChecked(True)
    for _ in range(5):
        window.drawPlot(_force=True)            # must not flip back and forth
    lo, hi = window.canvas.axes.get_xlim()
    assert lo > hi


def test_reverse_y_axis(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    window.reverseYCheck.setChecked(True)
    lo, hi = window.canvas.axes.get_ylim()
    assert lo > hi


def test_reverse_y_also_flips_twin_axis(window, rich_df):
    """Reversing Y must flip the right-hand (twin) Y axis too, not just primary."""
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    _series(window, "x", "c", "a.csv", useRightAxis=True)
    window.reverseYCheck.setChecked(True)
    lo1, hi1 = window.canvas.axes.get_ylim()
    lo2, hi2 = window.canvas._ax2.get_ylim()
    assert lo1 > hi1        # primary reversed
    assert lo2 > hi2        # twin reversed too


def test_equal_aspect_toggle_restores_auto(window, rich_df):
    """Unchecking equal aspect must return the axes to 'auto' (was sticky)."""
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    window.drawPlot(_force=True)
    assert window.canvas.axes.get_aspect() == "auto"
    window.equalAspectCheck.setChecked(True)
    assert window.canvas.axes.get_aspect() == 1.0
    window.equalAspectCheck.setChecked(False)
    assert window.canvas.axes.get_aspect() == "auto"


def test_box_aspect_toggle_restores_default(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    window.boxAspectCheck.setChecked(True)
    assert window.canvas.axes.get_box_aspect() is not None
    window.boxAspectCheck.setChecked(False)
    assert window.canvas.axes.get_box_aspect() is None


# ---------------------------------------------------------------------------
# Datetime axis
# ---------------------------------------------------------------------------

@pytest.fixture
def datetime_df():
    return pd.DataFrame({
        "t": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03",
                             "2020-01-04", "2020-01-05"]),
        "v": [1.0, 2.0, 3.0, 4.5, 5.0],
    })


def test_drawplot_datetime_axis(window, datetime_df):
    _register(window, "d.csv", datetime_df)
    _series(window, "t", "v", "d.csv")
    window.drawPlot(_force=True)
    assert window.canvas.axes.has_data()


def test_datetime_axis_uses_date_locator(window, datetime_df):
    """The tick-count MaxNLocator must not clobber the datetime locator."""
    import matplotlib.dates as mdates
    _register(window, "d.csv", datetime_df)
    _series(window, "t", "v", "d.csv")
    window.drawPlot(_force=True)
    loc = window.canvas.axes.xaxis.get_major_locator()
    assert isinstance(loc, mdates.DateLocator)


def test_datetime_locator_not_sticky(window, datetime_df):
    """Switching a datetime x-axis back to numeric restores the normal locator."""
    from matplotlib.ticker import MaxNLocator
    _register(window, "d.csv", datetime_df)
    other = pd.DataFrame({"n": [1.0, 2.0, 3.0], "m": [4.0, 5.0, 6.0]})
    _register(window, "n.csv", other)
    e = _series(window, "t", "v", "d.csv")
    window.drawPlot(_force=True)
    e["xData"], e["yData"] = ("n.csv", "n"), ("n.csv", "m")
    window.drawPlot(_force=True)
    assert isinstance(window.canvas.axes.xaxis.get_major_locator(), MaxNLocator)


def test_drawplot_datetime_with_smoothing_no_crash(window, datetime_df):
    _register(window, "d.csv", datetime_df)
    _series(window, "t", "v", "d.csv", smoothing=True, smoothWindow=2)
    window.drawPlot(_force=True)
    assert len(window.canvas.axes.get_lines()) >= 2


# ---------------------------------------------------------------------------
# Render-error safety net
# ---------------------------------------------------------------------------

def test_drawplot_swallows_render_errors(window, rich_df):
    _register(window, "a.csv", rich_df)
    _series(window, "x", "y", "a.csv")
    with patch.object(window.canvas, "plot", side_effect=RuntimeError("boom")):
        window.drawPlot(_force=True)      # must not propagate
    # a render failure leaves the save button disabled (nothing valid drawn)
    assert window.saveButton.isEnabled() is False


# ---------------------------------------------------------------------------
# Computed columns
# ---------------------------------------------------------------------------

def test_computed_column_valid_expression(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    with patch("alekhyam.mainWindow.ComputedColumnDialog") as MockDlg:
        inst = MockDlg.return_value
        inst.exec.return_value = True
        inst.values.return_value = ("a.csv", "ratio", "y / x")
        window._addComputedColumn()
    assert "ratio" in window.dataFrames["a.csv"].columns
    assert window.dataFrames["a.csv"]["ratio"].tolist() == pytest.approx(
        [1, 2, 3, 4, 5, 6])


def test_computed_column_numpy_function(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    with patch("alekhyam.mainWindow.ComputedColumnDialog") as MockDlg:
        inst = MockDlg.return_value
        inst.exec.return_value = True
        inst.values.return_value = ("a.csv", "sqrt_y", "sqrt(y)")
        window._addComputedColumn()
    assert window.dataFrames["a.csv"]["sqrt_y"].tolist() == pytest.approx(
        [1, 2, 3, 4, 5, 6])


def test_computed_column_invalid_expression_shows_error(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    with patch("alekhyam.mainWindow.ComputedColumnDialog") as MockDlg, \
         patch("alekhyam.mainWindow.QMessageBox.critical") as mock_crit:
        inst = MockDlg.return_value
        inst.exec.return_value = True
        inst.values.return_value = ("a.csv", "bad", "y @@ x")
        window._addComputedColumn()
    mock_crit.assert_called_once()
    assert "bad" not in window.dataFrames["a.csv"].columns


def test_computed_column_empty_name_rejected(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    with patch("alekhyam.mainWindow.ComputedColumnDialog") as MockDlg, \
         patch("alekhyam.mainWindow.QMessageBox.warning") as mock_warn:
        inst = MockDlg.return_value
        inst.exec.return_value = True
        inst.values.return_value = ("a.csv", "", "y / x")
        window._addComputedColumn()
    mock_warn.assert_called_once()


def test_computed_column_overwrite_declined_keeps_original(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    original = window.dataFrames["a.csv"]["y"].tolist()
    with patch("alekhyam.mainWindow.ComputedColumnDialog") as MockDlg, \
         patch("alekhyam.mainWindow.QMessageBox.question",
               return_value=QMessageBox.No):
        inst = MockDlg.return_value
        inst.exec.return_value = True
        inst.values.return_value = ("a.csv", "y", "x * 100")
        window._addComputedColumn()
    assert window.dataFrames["a.csv"]["y"].tolist() == original


def test_computed_column_overwrite_accepted_replaces(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    with patch("alekhyam.mainWindow.ComputedColumnDialog") as MockDlg, \
         patch("alekhyam.mainWindow.QMessageBox.question",
               return_value=QMessageBox.Yes):
        inst = MockDlg.return_value
        inst.exec.return_value = True
        inst.values.return_value = ("a.csv", "y", "x * 100")
        window._addComputedColumn()
    assert window.dataFrames["a.csv"]["y"].tolist() == [100, 200, 300, 400, 500, 600]


# ---------------------------------------------------------------------------
# Plot templates
# ---------------------------------------------------------------------------

def test_template_save_and_load_roundtrip(window, tmp_path):
    window.titleEdit.setText("My Title")
    window.xLabelEdit.setText("Time")
    window.xLogCheck.setChecked(True)
    window.gridCheckBox.setChecked(True)
    window.legendPosCombo.setCurrentText("upper left")

    path = str(tmp_path / "t.json")
    with patch("alekhyam.mainWindow.QFileDialog.getSaveFileName",
               return_value=(path, "")):
        window._saveTemplate()

    # Mutate everything, then load the template back
    window.titleEdit.setText("changed")
    window.xLabelEdit.setText("changed")
    window.xLogCheck.setChecked(False)
    window.gridCheckBox.setChecked(False)
    window.legendPosCombo.setCurrentText("best")

    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileName",
               return_value=(path, "")):
        window._loadTemplate()

    assert window.titleEdit.text() == "My Title"
    assert window.xLabelEdit.text() == "Time"
    assert window.xLogCheck.isChecked() is True
    assert window.gridCheckBox.isChecked() is True
    assert window.legendPosCombo.currentText() == "upper left"


def test_template_load_partial_uses_defaults(window, tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"title": "OnlyTitle"}))
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileName",
               return_value=(str(path), "")):
        window._loadTemplate()
    assert window.titleEdit.text() == "OnlyTitle"
    # missing keys fall back to defaults without raising
    assert window.xLogCheck.isChecked() is False


def test_template_load_coerces_numeric_types(window, tmp_path):
    """Hand-edited templates with float/str tick values must not crash."""
    path = tmp_path / "nums.json"
    path.write_text(json.dumps({
        "xTickSize": 14.0,      # float where an int spin is expected
        "yTickCount": "6",      # string that parses
        "xTickCount": "bad",    # unparseable → falls back to default
    }))
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileName",
               return_value=(str(path), "")):
        window._loadTemplate()          # must not raise
    assert window._getXTickSize() == 14
    assert window._getYTickCount() == 6


def test_template_load_malformed_json_shows_error(window, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileName",
               return_value=(str(path), "")), \
         patch("alekhyam.mainWindow.QMessageBox.critical") as mock_crit:
        window._loadTemplate()
    mock_crit.assert_called_once()


def test_template_save_records_current_version(window, tmp_path):
    from alekhyam import __version__
    path = str(tmp_path / "v.json")
    with patch("alekhyam.mainWindow.QFileDialog.getSaveFileName",
               return_value=(path, "")):
        window._saveTemplate()
    with open(path) as fh:
        assert json.load(fh)["version"] == __version__


# ---------------------------------------------------------------------------
# Multi-operation state consistency
# ---------------------------------------------------------------------------

def test_reorder_then_undo_restores_order(window, rich_df):
    _register(window, "a.csv", rich_df)
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "y"))
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "c"))
    before = [e["id"] for e in window.seriesRows]
    window._onSeriesRowsReordered(0, 1)
    assert [e["id"] for e in window.seriesRows] == list(reversed(before))
    window.undo()
    assert [e["id"] for e in window.seriesRows] == before


def test_reorder_undo_redo_cycle(window, rich_df):
    _register(window, "a.csv", rich_df)
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "y"))
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "c"))
    before = [e["id"] for e in window.seriesRows]
    window._onSeriesRowsReordered(0, 1)
    window.undo()
    window.redo()
    assert [e["id"] for e in window.seriesRows] == list(reversed(before))


def test_duplicate_series_gets_unique_id(window, rich_df):
    _register(window, "a.csv", rich_df)
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "y"))
    window.seriesTable.selectRow(0)
    window._duplicateSeries()
    ids = [e["id"] for e in window.seriesRows]
    assert len(ids) == len(set(ids)) == 2


def test_type_switch_preserves_advanced_fields(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv", smoothing=True, smoothWindow=9)
    window._onSeriesTypeChanged(e["id"], "Histogram")
    assert e["kind"] == "histogram"
    window._onSeriesTypeChanged(e["id"], "Line (R)")
    assert e["kind"] == "line" and e["useRightAxis"] is True
    # advanced line-only settings are retained across the round-trip
    assert e["smoothing"] is True and e["smoothWindow"] == 9


def test_clear_resets_all_state_and_stacks(window, rich_df):
    _register(window, "a.csv", rich_df, select=True)
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "y"))
    window._addReferenceLine("horizontal")
    window.drawPlot(_force=True)
    assert window._undoStack           # something to undo
    window.clearLoadedFiles()
    assert window.dataFrames == {}
    assert window.seriesRows == []
    assert window.referenceLineRows == []
    assert window._undoStack == []     # stale states referencing dropped files gone
    assert window._redoStack == []


def test_undo_after_clear_is_noop(window, rich_df):
    _register(window, "a.csv", rich_df)
    window._addSeriesEntry(xDefault=("a.csv", "x"), yDefault=("a.csv", "y"))
    window.clearLoadedFiles()
    window.undo()                      # must not raise or resurrect data
    assert window.dataFrames == {}
    assert window.seriesRows == []


def test_series_referencing_missing_column_is_skipped(window, rich_df):
    _register(window, "a.csv", rich_df)
    e = _series(window, "x", "y", "a.csv")
    e["yData"] = ("a.csv", "column_that_does_not_exist")
    window.drawPlot(_force=True)        # skipped with a warning, no crash
    assert window.canvas.warningBanner is not None
