import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DataFrameModel(QAbstractTableModel):
    """Read-only table model that exposes a pandas DataFrame to a QTableView."""

    def __init__(self, dataFrame=None, parent=None):
        super().__init__(parent)
        self._df = dataFrame

    def setDataFrame(self, dataFrame):
        self.beginResetModel()
        self._df = dataFrame
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid() or self._df is None:
            return 0
        return len(self._df.index)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid() or self._df is None:
            return 0
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            value = self._df.iat[index.row(), index.column()]
            return "" if pd.isna(value) else str(value)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or self._df is None:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(self._df.index[section])
