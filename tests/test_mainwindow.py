"""Tests for MainWindow — file loading, series management, plot logic."""
import os
from unittest.mock import patch

import pandas as pd
import pytest

from alekhyam.mainWindow import MainWindow


# ---------------------------------------------------------------------------
# _makeFileLabel  (duplicate-name collision handling)
# ---------------------------------------------------------------------------

def test_make_file_label_unique(window):
    window.dataFrames["data.csv"] = pd.DataFrame()
    # A completely different name should come back unchanged
    assert window._makeFileLabel("/path/to/other.csv") == "other.csv"


def test_make_file_label_no_collision(window):
    label = window._makeFileLabel("/some/path/data.csv")
    assert label == "data.csv"


def test_make_file_label_collision_adds_counter(window):
    window.dataFrames["data.csv"] = pd.DataFrame()
    label = window._makeFileLabel("/other/path/data.csv")
    assert label == "data.csv (2)"


def test_make_file_label_multiple_collisions(window):
    window.dataFrames["data.csv"] = pd.DataFrame()
    window.dataFrames["data.csv (2)"] = pd.DataFrame()
    label = window._makeFileLabel("/other/data.csv")
    assert label == "data.csv (3)"


# ---------------------------------------------------------------------------
# _parseLimit  (axis min/max parsing)
# ---------------------------------------------------------------------------

def test_parse_limit_valid(window):
    window.xMinEdit.setText("0.5")
    window.xMaxEdit.setText("10.5")
    assert window._parseLimit(window.xMinEdit, window.xMaxEdit) == (0.5, 10.5)


def test_parse_limit_empty_min_returns_none(window):
    window.xMinEdit.setText("")
    window.xMaxEdit.setText("10")
    assert window._parseLimit(window.xMinEdit, window.xMaxEdit) is None


def test_parse_limit_empty_max_returns_none(window):
    window.xMinEdit.setText("0")
    window.xMaxEdit.setText("")
    assert window._parseLimit(window.xMinEdit, window.xMaxEdit) is None


def test_parse_limit_both_empty_returns_none(window):
    window.xMinEdit.setText("")
    window.xMaxEdit.setText("")
    assert window._parseLimit(window.xMinEdit, window.xMaxEdit) is None


def test_parse_limit_invalid_text_returns_none(window):
    window.xMinEdit.setText("abc")
    window.xMaxEdit.setText("10")
    assert window._parseLimit(window.xMinEdit, window.xMaxEdit) is None


def test_parse_limit_negative_values(window):
    window.yMinEdit.setText("-5.0")
    window.yMaxEdit.setText("5.0")
    assert window._parseLimit(window.yMinEdit, window.yMaxEdit) == (-5.0, 5.0)


# ---------------------------------------------------------------------------
# _getSeriesArrays  (cross-file series data extraction)
# ---------------------------------------------------------------------------

@pytest.fixture
def window_with_data(window, sample_df, second_df):
    window.dataFrames["a.csv"] = sample_df
    window.dataFrames["b.csv"] = second_df
    return window


def test_get_arrays_same_file(window_with_data):
    result = window_with_data._getSeriesArrays("a.csv", "time", "a.csv", "sine")
    assert result is not None
    x, y = result
    assert len(x) == len(y) == 5


def test_get_arrays_cross_file_same_length(window_with_data):
    result = window_with_data._getSeriesArrays("a.csv", "time", "b.csv", "signal")
    assert result is not None


def test_get_arrays_missing_file_returns_none(window_with_data):
    assert window_with_data._getSeriesArrays("missing.csv", "time", "a.csv", "sine") is None


def test_get_arrays_missing_column_returns_none(window_with_data):
    assert window_with_data._getSeriesArrays("a.csv", "nope", "a.csv", "sine") is None


def test_get_arrays_length_mismatch_returns_none(window, sample_df):
    window.dataFrames["short.csv"] = sample_df.head(3)
    window.dataFrames["long.csv"]  = sample_df
    assert window._getSeriesArrays("short.csv", "time", "long.csv", "sine") is None


def test_get_arrays_drops_nan_rows(window):
    import numpy as np
    df = pd.DataFrame({"x": [1, 2, np.nan, 4], "y": [10, np.nan, 30, 40]})
    window.dataFrames["nan.csv"] = df
    x, y = window._getSeriesArrays("nan.csv", "x", "nan.csv", "y")
    assert len(x) == 2   # rows 0 and 3 survive (both non-NaN)


# ---------------------------------------------------------------------------
# Series entry helpers
# ---------------------------------------------------------------------------

def test_new_series_entry_defaults(window):
    entry = window._newSeriesEntry()
    assert entry["show"] is True
    assert entry["kind"] == "line"
    assert entry["linestyle"] == "-"
    assert entry["alpha"] == pytest.approx(0.9)
    assert "id" in entry


def test_new_series_entry_ids_are_unique(window):
    ids = [window._newSeriesEntry()["id"] for _ in range(10)]
    assert len(set(ids)) == 10


def test_find_series_by_id_found(window):
    e = window._newSeriesEntry()
    window.seriesRows.append(e)
    assert window._findSeriesById(e["id"]) is e


def test_find_series_by_id_not_found(window):
    assert window._findSeriesById(999999) is None


# ---------------------------------------------------------------------------
# File loading via openCsv (mocked dialog)
# ---------------------------------------------------------------------------

def test_open_csv_loads_dataframe(window, csv_path):
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([csv_path], "")):
        window.openCsv()

    assert len(window.dataFrames) == 1
    label = next(iter(window.dataFrames))
    assert label == os.path.basename(csv_path)
    assert len(window.dataFrames[label]) == 5


def test_open_csv_enables_plot_button(window, csv_path):
    assert not window.plotButton.isEnabled()
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([csv_path], "")):
        window.openCsv()
    assert window.plotButton.isEnabled()


def test_open_csv_creates_default_series(window, csv_path):
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([csv_path], "")):
        window.openCsv()
    assert len(window.seriesRows) == 1


def test_open_csv_second_file_keeps_existing_series(window, csv_path, second_csv):
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([csv_path], "")):
        window.openCsv()

    n = len(window.seriesRows)
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([second_csv], "")):
        window.openCsv()

    assert len(window.seriesRows) == n   # no extra series auto-added
    assert len(window.dataFrames) == 2


def test_open_csv_no_selection_does_nothing(window):
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([], "")):
        window.openCsv()
    assert len(window.dataFrames) == 0


def test_open_csv_nonexistent_file_shows_no_data(window, tmp_path):
    bad = str(tmp_path / "nope.csv")
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([bad], "")):
        with patch("alekhyam.mainWindow.QMessageBox.critical"):
            window.openCsv()
    assert len(window.dataFrames) == 0


def test_open_csv_empty_file_skipped(window, tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("col1,col2\n")   # header only, no rows → df.empty is True
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([str(path)], "")):
        with patch("alekhyam.mainWindow.QMessageBox.warning"):
            window.openCsv()
    assert len(window.dataFrames) == 0


# ---------------------------------------------------------------------------
# Series add / remove
# ---------------------------------------------------------------------------

def _load(window, csv_path):
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([csv_path], "")):
        window.openCsv()


def test_add_series_entry_increments_count(window, csv_path):
    _load(window, csv_path)
    before = len(window.seriesRows)
    window._addSeriesEntry()
    assert len(window.seriesRows) == before + 1


def test_remove_last_series(window, csv_path):
    _load(window, csv_path)
    window._addSeriesEntry()
    before = len(window.seriesRows)
    window._removeSelectedSeries()
    assert len(window.seriesRows) == before - 1


def test_series_row_reorder(window, csv_path):
    _load(window, csv_path)
    window._addSeriesEntry()
    window._addSeriesEntry()
    ids_before = [e["id"] for e in window.seriesRows]
    window._onSeriesRowsReordered(0, 2)
    ids_after = [e["id"] for e in window.seriesRows]
    assert ids_after[2] == ids_before[0]


def test_series_reorder_noop_same_row(window, csv_path):
    _load(window, csv_path)
    ids_before = [e["id"] for e in window.seriesRows]
    window._onSeriesRowsReordered(0, 0)
    assert [e["id"] for e in window.seriesRows] == ids_before


# ---------------------------------------------------------------------------
# Reference lines
# ---------------------------------------------------------------------------

def test_add_horizontal_reference_line(window):
    window._addReferenceLine("horizontal")
    assert len(window.referenceLineRows) == 1
    assert window.referenceLineRows[0]["orientation"] == "horizontal"


def test_add_vertical_reference_line(window):
    window._addReferenceLine("vertical")
    assert window.referenceLineRows[0]["orientation"] == "vertical"


def test_remove_reference_line(window):
    window._addReferenceLine()
    window._addReferenceLine()
    before = len(window.referenceLineRows)
    window._removeSelectedReferenceLine()
    assert len(window.referenceLineRows) == before - 1


def test_reference_line_field_change(window):
    window._addReferenceLine("horizontal")
    rid = window.referenceLineRows[0]["id"]
    window._onReferenceLineFieldChanged(rid, "position", 3.14)
    assert window.referenceLineRows[0]["position"] == pytest.approx(3.14)


# ---------------------------------------------------------------------------
# drawPlot integration
# ---------------------------------------------------------------------------

def test_draw_plot_with_valid_data(window, csv_path):
    _load(window, csv_path)
    window.drawPlot()   # must not raise


def test_draw_plot_enables_save_button(window, csv_path):
    _load(window, csv_path)
    window.drawPlot()
    assert window.saveButton.isEnabled()


def test_draw_plot_with_axis_labels(window, csv_path):
    _load(window, csv_path)
    window.xLabelEdit.setText("Time")
    window.yLabelEdit.setText("Value")
    window.drawPlot()
    assert window.canvas.axes.get_xlabel() == "Time"
    assert window.canvas.axes.get_ylabel() == "Value"


def test_draw_plot_with_axis_limits(window, csv_path):
    _load(window, csv_path)
    window.xMinEdit.setText("0.0")
    window.xMaxEdit.setText("1.0")
    window.drawPlot()
    xlim = window.canvas.axes.get_xlim()
    assert xlim[0] == pytest.approx(0.0)
    assert xlim[1] == pytest.approx(1.0)


def test_draw_plot_with_reference_line(window, csv_path):
    _load(window, csv_path)
    window._addReferenceLine("horizontal")
    window.referenceLineRows[0]["position"] = 0.5
    window.drawPlot()   # must not raise


def test_draw_plot_hidden_series_not_plotted(window, csv_path):
    _load(window, csv_path)
    window.seriesRows[0]["show"] = False
    window.drawPlot()
    assert not window.saveButton.isEnabled()


# ---------------------------------------------------------------------------
# clearLoadedFiles
# ---------------------------------------------------------------------------

def test_clear_resets_state(window, csv_path):
    _load(window, csv_path)
    window.clearLoadedFiles()
    assert len(window.dataFrames) == 0
    assert len(window.seriesRows) == 0
    assert not window.plotButton.isEnabled()
    assert not window.saveButton.isEnabled()
    assert not window.clearFilesAction.isEnabled()


def test_clear_resets_decorations_and_undo(window, csv_path):
    _load(window, csv_path)
    window._addReferenceLine("horizontal")
    window._addFill("vertical")
    window.textAnnotationRows.append(window._newTextAnnotationEntry())
    window._rebuildTextAnnotationTable()
    window.clearLoadedFiles()
    assert window.referenceLineRows == []
    assert window.fillRows == []
    assert window.textAnnotationRows == []
    assert window.referenceLineTable.rowCount() == 0
    assert window.textAnnotationTable.rowCount() == 0
    # Undo history references dropped dataframes — must be gone too
    assert window._undoStack == []
    assert window._redoStack == []
    assert not window.undoAction.isEnabled()
    assert not window.redoAction.isEnabled()


# ---------------------------------------------------------------------------
# Recent files (QSettings list/str normalisation)
# ---------------------------------------------------------------------------

class _FakeSettings:
    """Stand-in for QSettings so tests never touch the user's real config."""

    def __init__(self, store=None):
        self._store = store or {}

    def value(self, key, default=None, type=None):  # noqa: A002
        return self._store.get(key, default)

    def setValue(self, key, value):
        self._store[key] = value


def test_recent_files_single_string_not_split(window):
    # Some QSettings backends return a one-element list as a plain string;
    # it must come back as one path, not a list of characters.
    window._settings = _FakeSettings({"recentFiles": "/tmp/one.csv"})
    assert window._recentFilesList() == ["/tmp/one.csv"]


def test_recent_files_none_and_empty(window):
    window._settings = _FakeSettings({})
    assert window._recentFilesList() == []
    window._settings = _FakeSettings({"recentFiles": ""})
    assert window._recentFilesList() == []


def test_recent_files_list_passthrough(window):
    window._settings = _FakeSettings({"recentFiles": ["/a.csv", "/b.csv"]})
    assert window._recentFilesList() == ["/a.csv", "/b.csv"]


# ---------------------------------------------------------------------------
# File preview (label stored as item data, not parsed from display text)
# ---------------------------------------------------------------------------

def test_preview_with_parens_in_filename(window, sample_df, tmp_path):
    path = tmp_path / "weird  (name).csv"
    sample_df.to_csv(path, index=False)
    assert window._loadFile(str(path))
    window.filesList.setCurrentRow(0)
    assert window.previewTable.model().rowCount() == len(sample_df)
