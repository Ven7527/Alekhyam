"""Tests for the Excel-style formula builder and the multi-series Compare tab."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from alekhyam.computedColumnDialog import evaluateFormula, ComputedColumnDialog
from alekhyam.comparisonDetailsDialog import ComparisonDetailsDialog


def _register(window, label, df, select=False):
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    if select:
        window.filesList.setCurrentItem(item)
    return label


@pytest.fixture
def cmp_df():
    return pd.DataFrame({
        "measured":  [1.0, 2.0, 3.0, 4.0, 5.0],
        "predicted": [1.1, 2.1, 2.8, 4.2, 4.9],
        "x":         [1, 2, 3, 4, 5],
    })


# ---------------------------------------------------------------------------
# evaluateFormula — functions, constants, powers, safety
# ---------------------------------------------------------------------------

def test_formula_arithmetic():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0]})
    assert evaluateFormula(df, "b / a").tolist() == [2.0, 2.0, 2.0]


def test_formula_power():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    assert evaluateFormula(df, "x ** 2").tolist() == [1.0, 4.0, 9.0]


def test_formula_sqrt_function():
    df = pd.DataFrame({"x": [1.0, 4.0, 9.0]})
    assert evaluateFormula(df, "sqrt(x)").tolist() == [1.0, 2.0, 3.0]


def test_formula_trig_functions():
    df = pd.DataFrame({"x": [0.0, np.pi / 2]})
    out = evaluateFormula(df, "sin(x)")
    assert out == pytest.approx([0.0, 1.0])


def test_formula_pi_constant():
    df = pd.DataFrame({"x": [1.0, 2.0]})
    assert evaluateFormula(df, "pi * x") == pytest.approx([np.pi, 2 * np.pi])


def test_formula_exp_and_log():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    assert evaluateFormula(df, "log(exp(x))") == pytest.approx([1.0, 2.0, 3.0])


def test_formula_scalar_broadcasts_to_length():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    out = evaluateFormula(df, "pi")
    assert len(out) == 4 and out == pytest.approx([np.pi] * 4)


def test_formula_blocks_builtins():
    df = pd.DataFrame({"x": [1.0]})
    with pytest.raises(Exception):
        evaluateFormula(df, "__import__('os').system('echo hi')")


def test_formula_syntax_error_raises():
    df = pd.DataFrame({"x": [1.0]})
    with pytest.raises(Exception):
        evaluateFormula(df, "x @@ 2")


def test_formula_column_with_space_via_backtick():
    df = pd.DataFrame({"flow rate": [2.0, 4.0, 6.0], "time": [1.0, 2.0, 3.0]})
    assert evaluateFormula(df, "`flow rate` / time").tolist() == [2.0, 2.0, 2.0]


def test_formula_column_named_like_keyword():
    df = pd.DataFrame({"class": [1.0, 2.0, 3.0], "y": [10.0, 20.0, 30.0]})
    assert evaluateFormula(df, "`class` + y").tolist() == [11.0, 22.0, 33.0]


def test_formula_column_shadowing_function_uses_backtick():
    df = pd.DataFrame({"sin": [1.0, 2.0, 3.0], "x": [0.0, 1.0, 2.0]})
    # backtick → the column
    assert evaluateFormula(df, "`sin` + 10").tolist() == [11.0, 12.0, 13.0]
    # bare sin(...) → the function still works
    assert evaluateFormula(df, "sin(x)")[0] == pytest.approx(0.0)


def test_formula_unknown_backtick_column_errors():
    df = pd.DataFrame({"a": [1.0]})
    with pytest.raises(ValueError):
        evaluateFormula(df, "`nope` + 1")


def test_column_ref_helper():
    from alekhyam.computedColumnDialog import columnRef
    assert columnRef("time") == "time"
    assert columnRef("flow rate") == "`flow rate`"
    assert columnRef("class") == "`class`"      # keyword
    assert columnRef("sin") == "`sin`"          # function name
    assert columnRef("2col") == "`2col`"        # starts with a digit


# ---------------------------------------------------------------------------
# ComputedColumnDialog — live preview / OK gating
# ---------------------------------------------------------------------------

def test_dialog_preview_valid_enables_ok(qapp, cmp_df):
    dlg = ComputedColumnDialog({"a.csv": cmp_df})
    dlg.exprEdit.setText("sqrt(x)")
    ok = dlg._buttonBox.button(dlg._buttonBox.StandardButton.Ok)
    assert ok.isEnabled()
    assert "Result" in dlg.previewLabel.text()


def test_dialog_preview_invalid_disables_ok(qapp, cmp_df):
    dlg = ComputedColumnDialog({"a.csv": cmp_df})
    dlg.exprEdit.setText("x @@ 2")
    ok = dlg._buttonBox.button(dlg._buttonBox.StandardButton.Ok)
    assert not ok.isEnabled()


def test_dialog_insert_appends_to_formula(qapp, cmp_df):
    dlg = ComputedColumnDialog({"a.csv": cmp_df})
    dlg._insert("sqrt()", 1)
    assert dlg.exprEdit.text() == "sqrt()"
    # cursor sits inside the parens
    assert dlg.exprEdit.cursorPosition() == len("sqrt(")


# ---------------------------------------------------------------------------
# Compare tab — add / compute / inject / remove
# ---------------------------------------------------------------------------

def test_add_comparison_creates_row(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    window._postFileLoad()
    window._addComparison()
    assert len(window.comparisonRows) == 1
    assert window.comparisonTable.rowCount() == 1


def test_compute_comparison_metrics(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    e = window._newComparisonEntry()
    e["refData"] = ("a.csv", "measured")
    e["cmpData"] = ("a.csv", "predicted")
    res = window._computeComparison(e)
    diff = cmp_df["predicted"] - cmp_df["measured"]
    assert res["MSE"] == pytest.approx(float((diff ** 2).mean()))
    assert res["RMSD"] == pytest.approx(float((diff ** 2).mean()) ** 0.5)
    assert res["MAE"] == pytest.approx(float(diff.abs().mean()))
    assert res["n"] == 5


def test_compute_comparison_unset_returns_none(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    e = window._newComparisonEntry()
    assert window._computeComparison(e) is None


def test_compute_comparison_length_mismatch_returns_none(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    _register(window, "b.csv", cmp_df.head(3))
    e = window._newComparisonEntry()
    e["refData"] = ("a.csv", "measured")
    e["cmpData"] = ("b.csv", "predicted")
    assert window._computeComparison(e) is None


def test_compute_comparison_drops_nan(window):
    df = pd.DataFrame({"a": [1.0, 2.0, np.nan, 4.0], "b": [1.0, np.nan, 3.0, 4.0]})
    _register(window, "n.csv", df)
    e = window._newComparisonEntry()
    e["refData"] = ("n.csv", "a")
    e["cmpData"] = ("n.csv", "b")
    res = window._computeComparison(e)
    assert res["n"] == 2       # rows 0 and 3 survive


def test_comparison_metric_injected_as_annotation(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    window._postFileLoad()
    e = window._newComparisonEntry()
    e["refData"] = ("a.csv", "measured")
    e["cmpData"] = ("a.csv", "predicted")
    e["metrics"]["RMSD"]["add"] = True
    window.comparisonRows.append(e)
    window.drawPlot(_force=True)
    texts = [t.get_text() for t in window.canvas.axes.texts]
    assert any(t.startswith("RMSD:") for t in texts)


def test_comparison_multiple_rows_independent(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    window._postFileLoad()
    window._addComparison()
    window._addComparison()
    window.comparisonRows[0]["refData"] = ("a.csv", "measured")
    window.comparisonRows[0]["cmpData"] = ("a.csv", "predicted")
    window.comparisonRows[1]["refData"] = ("a.csv", "x")
    window.comparisonRows[1]["cmpData"] = ("a.csv", "measured")
    r0 = window._computeComparison(window.comparisonRows[0])
    r1 = window._computeComparison(window.comparisonRows[1])
    assert r0["RMSD"] != r1["RMSD"]


def test_remove_comparison(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    window._postFileLoad()
    window._addComparison()
    window._addComparison()
    window._removeSelectedComparison()      # removes last when none selected
    assert len(window.comparisonRows) == 1
    assert window.comparisonTable.rowCount() == 1


def test_clear_resets_comparisons(window, cmp_df):
    _register(window, "a.csv", cmp_df, select=True)
    window._postFileLoad()
    window._addComparison()
    window.clearLoadedFiles()
    assert window.comparisonRows == []
    assert window.comparisonTable.rowCount() == 0


def test_comparison_details_dialog_writes_back_add_flags(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    e = window._newComparisonEntry()
    e["refData"] = ("a.csv", "measured")
    e["cmpData"] = ("a.csv", "predicted")
    res = window._computeComparison(e)
    dlg = ComparisonDetailsDialog(e, res, window)
    dlg._addChecks["MAE"].setChecked(True)
    dlg.accept()
    assert e["metrics"]["MAE"]["add"] is True
    assert e["metrics"]["RMSD"]["add"] is False


def test_comparison_new_entries_stagger_default_positions(window, cmp_df):
    _register(window, "a.csv", cmp_df)
    window._postFileLoad()
    window._addComparison()
    window._addComparison()
    y0 = window.comparisonRows[0]["metrics"]["RMSD"]["settings"]["y"]
    y1 = window.comparisonRows[1]["metrics"]["RMSD"]["settings"]["y"]
    assert y1 < y0     # second comparison starts lower so labels don't overlap


# ---------------------------------------------------------------------------
# DPI default  (with no persisted user preference, the default must be 300)
# ---------------------------------------------------------------------------

def test_default_export_dpi_is_300(qapp):
    from alekhyam.mainWindow import MainWindow
    with patch("alekhyam.mainWindow.QSettings") as MockQS:
        # value(key, default, ...) returns the default → simulates a clean install
        MockQS.return_value.value.side_effect = \
            lambda key, default=None, **kw: default
        win = MainWindow()
        try:
            assert win.exportDpiSpin.value() == 300
        finally:
            win.close()
