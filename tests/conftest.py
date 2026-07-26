import os
import sys

import pandas as pd
import pytest

# Must be set before any Qt import so tests work without a physical display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make the package importable when running pytest from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    return app


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "time":   [0.0, 0.5, 1.0, 1.5, 2.0],
        "sine":   [0.0, 0.48, 0.84, 0.997, 0.91],
        "cosine": [1.0, 0.88, 0.54, 0.07, -0.42],
        "linear": [0.1, 0.6, 1.1, 1.6, 2.1],
    })


@pytest.fixture
def csv_path(sample_df, tmp_path):
    path = tmp_path / "sample.csv"
    sample_df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def second_df():
    """Same length as sample_df — for cross-file series tests."""
    return pd.DataFrame({
        "t2":     [0, 1, 2, 3, 4],
        "signal": [5.0, 4.2, 3.1, 2.4, 1.8],
    })


@pytest.fixture
def second_csv(second_df, tmp_path):
    path = tmp_path / "second.csv"
    second_df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def window(qapp):
    from alekhyam.mainWindow import MainWindow
    win = MainWindow()
    yield win
    win.close()
