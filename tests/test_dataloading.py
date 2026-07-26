"""Tests for the multi-format data loader (_readDataFile / _arrayToFrame)."""
import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from alekhyam.mainWindow import _arrayToFrame, _readDataFile


# ---------------------------------------------------------------------------
# _arrayToFrame
# ---------------------------------------------------------------------------

def test_array_to_frame_1d_default_name():
    df = _arrayToFrame(np.array([1.0, 2.0, 3.0]))
    assert list(df.columns) == ["value"]
    assert len(df) == 3


def test_array_to_frame_1d_with_prefix():
    df = _arrayToFrame(np.array([1.0, 2.0]), prefix="x")
    assert list(df.columns) == ["x"]


def test_array_to_frame_2d_default_names():
    df = _arrayToFrame(np.array([[1, 2], [3, 4], [5, 6]]))
    assert list(df.columns) == ["col0", "col1"]
    assert len(df) == 3


def test_array_to_frame_2d_with_prefix():
    df = _arrayToFrame(np.array([[1, 2], [3, 4]]), prefix="arr")
    assert list(df.columns) == ["arr_0", "arr_1"]


def test_array_to_frame_structured_array_uses_field_names():
    arr = np.array([(1, 2.5), (3, 4.5)], dtype=[("id", "i4"), ("val", "f8")])
    df = _arrayToFrame(arr)
    assert list(df.columns) == ["id", "val"]
    assert df["id"].tolist() == [1, 3]


def test_array_to_frame_rejects_3d():
    with pytest.raises(ValueError):
        _arrayToFrame(np.zeros((2, 2, 2)))


# ---------------------------------------------------------------------------
# _readDataFile — .npy
# ---------------------------------------------------------------------------

def test_read_npy_1d(tmp_path):
    path = tmp_path / "a.npy"
    np.save(path, np.array([1.0, 2.0, 3.0, 4.0]))
    df = _readDataFile(str(path))
    assert list(df.columns) == ["value"]
    assert len(df) == 4


def test_read_npy_2d(tmp_path):
    path = tmp_path / "b.npy"
    np.save(path, np.array([[1, 2], [3, 4], [5, 6]]))
    df = _readDataFile(str(path))
    assert list(df.columns) == ["col0", "col1"]
    assert len(df) == 3


# ---------------------------------------------------------------------------
# _readDataFile — .npz
# ---------------------------------------------------------------------------

def test_read_npz_equal_length_arrays(tmp_path):
    path = tmp_path / "c.npz"
    np.savez(path, x=np.array([1, 2, 3]), y=np.array([10, 20, 30]))
    df = _readDataFile(str(path))
    assert set(df.columns) == {"x", "y"}
    assert len(df) == 3
    assert df["y"].tolist() == [10, 20, 30]


def test_read_npz_mismatched_length_pads_with_nan(tmp_path):
    path = tmp_path / "d.npz"
    np.savez(path, x=np.array([1, 2, 3, 4]), y=np.array([10, 20]))
    df = _readDataFile(str(path))
    assert len(df) == 4
    assert df["y"].isna().sum() == 2
    assert df["x"].isna().sum() == 0


def test_read_npz_2d_array_gets_prefixed_columns(tmp_path):
    path = tmp_path / "e.npz"
    np.savez(path, grid=np.array([[1, 2], [3, 4]]))
    df = _readDataFile(str(path))
    assert list(df.columns) == ["grid_0", "grid_1"]


# ---------------------------------------------------------------------------
# _readDataFile — .txt
# ---------------------------------------------------------------------------

def test_read_txt_comma_delimited(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("a,b,c\n1,2,3\n4,5,6\n")
    df = _readDataFile(str(path))
    assert list(df.columns) == ["a", "b", "c"]
    assert len(df) == 2


def test_read_txt_whitespace_delimited(tmp_path):
    path = tmp_path / "g.txt"
    path.write_text("a b c\n1 2 3\n4 5 6\n")
    df = _readDataFile(str(path))
    assert list(df.columns) == ["a", "b", "c"]
    assert len(df) == 2


# ---------------------------------------------------------------------------
# _readDataFile — unsupported extension
# ---------------------------------------------------------------------------

def test_read_unsupported_extension_raises(tmp_path):
    path = tmp_path / "h.json"
    path.write_text("{}")
    with pytest.raises(ValueError):
        _readDataFile(str(path))


# ---------------------------------------------------------------------------
# End-to-end via openCsv / _loadFile (MainWindow integration)
# ---------------------------------------------------------------------------

def test_open_npy_file_via_dialog(window, tmp_path):
    path = tmp_path / "data.npy"
    np.save(path, np.array([1.0, 2.0, 3.0]))
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([str(path)], "")):
        window.openCsv()
    assert len(window.dataFrames) == 1
    label = next(iter(window.dataFrames))
    assert label == "data.npy"
    assert list(window.dataFrames[label].columns) == ["value"]


def test_open_npz_file_via_dialog(window, tmp_path):
    path = tmp_path / "data.npz"
    np.savez(path, x=np.array([1, 2, 3]), y=np.array([4, 5, 6]))
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([str(path)], "")):
        window.openCsv()
    assert len(window.dataFrames) == 1
    label = next(iter(window.dataFrames))
    assert set(window.dataFrames[label].columns) == {"x", "y"}


def test_open_txt_file_via_dialog(window, tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("x,y\n1,2\n3,4\n")
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([str(path)], "")):
        window.openCsv()
    assert len(window.dataFrames) == 1
    label = next(iter(window.dataFrames))
    assert list(window.dataFrames[label].columns) == ["x", "y"]


def test_open_malformed_npy_shows_error(window, tmp_path):
    path = tmp_path / "bad.npy"
    path.write_text("not a numpy file")
    with patch("alekhyam.mainWindow.QFileDialog.getOpenFileNames",
               return_value=([str(path)], "")):
        with patch("alekhyam.mainWindow.QMessageBox.critical") as mock_critical:
            window.openCsv()
    mock_critical.assert_called_once()
    assert len(window.dataFrames) == 0
