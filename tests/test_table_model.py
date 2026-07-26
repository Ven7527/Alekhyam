"""Tests for DataFrameModel (Qt table model wrapping a pandas DataFrame)."""
import pandas as pd
import pytest
from PySide6.QtCore import Qt

from alekhyam.tableModel import DataFrameModel


@pytest.fixture
def model(qapp, sample_df):
    return DataFrameModel(sample_df)


def test_empty_model_row_count(qapp):
    m = DataFrameModel()
    assert m.rowCount() == 0


def test_empty_model_column_count(qapp):
    m = DataFrameModel()
    assert m.columnCount() == 0


def test_row_count(model, sample_df):
    assert model.rowCount() == len(sample_df)


def test_column_count(model, sample_df):
    assert model.columnCount() == len(sample_df.columns)


def test_data_display_role(model, sample_df):
    # First cell: time column, first row
    idx = model.index(0, 0)
    assert model.data(idx, Qt.DisplayRole) == str(sample_df.iat[0, 0])


def test_data_invalid_index_returns_none(model):
    assert model.data(model.index(-1, -1)) is None


def test_horizontal_header(model, sample_df):
    for i, col in enumerate(sample_df.columns):
        assert model.headerData(i, Qt.Horizontal) == col


def test_vertical_header(model, sample_df):
    for i, idx in enumerate(sample_df.index):
        assert model.headerData(i, Qt.Vertical) == str(idx)


def test_set_dataframe_updates_row_count(qapp, sample_df):
    m = DataFrameModel()
    assert m.rowCount() == 0
    m.setDataFrame(sample_df)
    assert m.rowCount() == len(sample_df)


def test_set_dataframe_to_none(qapp, sample_df):
    m = DataFrameModel(sample_df)
    m.setDataFrame(None)
    assert m.rowCount() == 0
    assert m.columnCount() == 0


def test_data_none_value_returns_empty_string(qapp):
    df = pd.DataFrame({"a": [None, 1]})
    m = DataFrameModel(df)
    assert m.data(m.index(0, 0), Qt.DisplayRole) == ""
