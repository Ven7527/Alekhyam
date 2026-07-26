"""Tests for the general curve-fit engine and the Curve Fit tab."""
import numpy as np
import pandas as pd
import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from alekhyam.curveFit import extractParameters, fitCurve
from alekhyam.fitDetailsDialog import FitDetailsDialog


def _register(window, label, df):
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    return label


@pytest.fixture
def exp_df():
    x = np.linspace(0, 4, 60)
    rng = np.random.default_rng(0)
    y = 3.0 * np.exp(-1.2 * x) + 0.5 + rng.normal(0, 0.01, x.size)
    return pd.DataFrame({"x": x, "y": y, "lin": 2.0 * x + 1.0})


# ---------------------------------------------------------------------------
# extractParameters
# ---------------------------------------------------------------------------

def test_extract_parameters_basic():
    assert extractParameters("a * exp(-b * x) + c") == ["a", "b", "c"]


def test_extract_parameters_excludes_functions_and_x():
    # sin, exp, pi are known; x is the variable — none are parameters
    assert extractParameters("sin(x) * exp(pi)") == []


def test_extract_parameters_sorted_unique():
    assert extractParameters("b + a + b + a * x") == ["a", "b"]


def test_extract_parameters_excludes_known_columns():
    # 'offset' is a data column, not a parameter
    assert extractParameters("a * x + b - offset", columns=["offset"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# fitCurve
# ---------------------------------------------------------------------------

def test_fit_linear_recovers_parameters():
    x = np.linspace(0, 10, 50)
    y = 2.5 * x + 1.3
    res = fitCurve(x, y, "a * x + b")
    assert res["popt"][0] == pytest.approx(2.5, rel=1e-4)
    assert res["popt"][1] == pytest.approx(1.3, abs=1e-4)
    assert res["r2"] == pytest.approx(1.0, abs=1e-6)


def test_fit_exponential_recovers_parameters():
    x = np.linspace(0, 4, 100)
    y = 3.0 * np.exp(-1.2 * x) + 0.5
    res = fitCurve(x, y, "a * exp(-b * x) + c", p0=[1, 1, 1])
    a, b, c = res["popt"]
    assert a == pytest.approx(3.0, rel=1e-3)
    assert b == pytest.approx(1.2, rel=1e-3)
    assert c == pytest.approx(0.5, abs=1e-3)


def test_fit_predict_callable():
    x = np.linspace(0, 5, 20)
    y = 4.0 * x - 2.0
    res = fitCurve(x, y, "a * x + b")
    assert res["predict"]([0.0, 1.0]) == pytest.approx([-2.0, 2.0], abs=1e-6)


def test_fit_equation_substitutes_parameters():
    x = np.linspace(0, 5, 20)
    y = 3.0 * x
    res = fitCurve(x, y, "a * x + b")
    assert "x" in res["equation"] and "a" not in res["equation"]


def test_fit_drops_nan():
    x = np.array([0.0, 1.0, 2.0, np.nan, 4.0])
    y = np.array([1.0, 3.0, 5.0, 7.0, 9.0])
    res = fitCurve(x, y, "a * x + b")   # should ignore the nan row
    assert res["popt"][0] == pytest.approx(2.0, rel=1e-4)


def test_fit_no_free_parameters_raises():
    x = np.linspace(0, 1, 10)
    with pytest.raises(ValueError):
        fitCurve(x, np.sin(x), "sin(x)")


def test_fit_too_few_points_raises():
    with pytest.raises(ValueError):
        fitCurve(np.array([1.0]), np.array([2.0]), "a * x + b")


def test_fit_wrong_number_of_guesses_raises():
    x = np.linspace(0, 5, 20)
    with pytest.raises(ValueError):
        fitCurve(x, 2 * x, "a * x + b", p0=[1.0])   # needs 2 guesses


def test_fit_with_extra_column_covariate():
    # y = 2.5x + 1.3 - offset : offset is fixed data, not a fitted parameter
    rng = np.random.default_rng(1)
    x = np.linspace(0, 10, 80)
    offset = rng.uniform(0, 3, x.size)
    y = 2.5 * x + 1.3 - offset
    res = fitCurve(x, y, "a * x + b - offset", extra={"offset": offset})
    assert res["paramNames"] == ["a", "b"]
    assert res["popt"][0] == pytest.approx(2.5, rel=1e-4)
    assert res["popt"][1] == pytest.approx(1.3, abs=1e-3)
    assert res["usesExtra"] is True
    assert "offset" in res["equation"]        # column stays symbolic


def test_fit_extra_column_nan_alignment():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    off = np.array([0.0, np.nan, 0.0, 0.0])   # row 1 dropped
    y = 2.0 * x - off
    res = fitCurve(x, y, "a * x - off", extra={"off": off})
    assert res["popt"][0] == pytest.approx(2.0, rel=1e-6)


def test_fit_covariate_column_with_space():
    rng = np.random.default_rng(3)
    x = np.linspace(0, 10, 60)
    off = rng.uniform(0, 2, x.size)
    y = 2.0 * x + 1.5 - off
    res = fitCurve(x, y, "a * x + b - `base offset`", extra={"base offset": off})
    assert res["paramNames"] == ["a", "b"]
    assert res["popt"][0] == pytest.approx(2.0, rel=1e-3)
    assert "`base offset`" in res["equation"]   # column stays symbolic in eqn


def test_extract_parameters_backtick_column_excluded():
    assert extractParameters("a * x + `flow rate`", columns=["flow rate"]) == ["a"]


def test_fit_degenerate_sets_warning():
    res = fitCurve(np.array([1.0, 1.0, 1.0, 1.0]),
                   np.array([2.0, 2.0, 2.0, 2.0]), "a * x + b")
    assert res["warning"] is not None


def test_fit_good_fit_no_warning():
    x = np.linspace(0, 10, 50)
    res = fitCurve(x, 2.5 * x + 1.0, "a * x + b")
    assert res["warning"] is None


# ---------------------------------------------------------------------------
# Curve Fit tab (MainWindow integration)
# ---------------------------------------------------------------------------

def test_add_fit_creates_row(window, exp_df):
    _register(window, "d.csv", exp_df)
    window._postFileLoad()
    window._addFit()
    assert len(window.fitRows) == 1
    assert window.fitTable.rowCount() == 1


def test_compute_fit_success(window, exp_df):
    _register(window, "d.csv", exp_df)
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    e["model"] = "a * exp(-b * x) + c"
    result, error = window._computeFit(e)
    assert error is None
    assert result["r2"] > 0.99


def test_compute_fit_missing_columns(window, exp_df):
    _register(window, "d.csv", exp_df)
    e = window._newFitEntry()
    e["model"] = "a * x + b"
    result, error = window._computeFit(e)
    assert result is None and "column" in error.lower()


def test_compute_fit_empty_model(window, exp_df):
    _register(window, "d.csv", exp_df)
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    result, error = window._computeFit(e)
    assert result is None and "model" in error.lower()


def test_compute_fit_uses_other_column(window):
    rng = np.random.default_rng(2)
    x = np.linspace(0, 10, 60)
    offset = rng.uniform(0, 2, x.size)
    df = pd.DataFrame({"x": x, "y": 3.0 * x + 0.5 - offset, "offset": offset})
    _register(window, "d.csv", df)
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    e["model"] = "a * x + b - offset"
    result, error = window._computeFit(e)
    assert error is None
    assert result["paramNames"] == ["a", "b"]      # offset is not fitted
    assert result["popt"][0] == pytest.approx(3.0, rel=1e-3)
    assert result["usesExtra"] is True


def test_fit_extra_columns_excludes_x_and_y(window):
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0],
                       "other": [4.0, 5.0, 6.0], "name": ["a", "b", "c"]})
    _register(window, "d.csv", df)
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    cols = window._fitExtraColumns(e)
    assert "other" in cols          # available covariate
    assert "x" not in cols          # already the variable
    assert "y" not in cols          # the response
    assert "name" not in cols       # non-numeric


def test_fit_overlay_appears_on_plot(window, exp_df):
    _register(window, "d.csv", exp_df)
    window._postFileLoad()
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    e["model"] = "a * exp(-b * x) + c"
    e["overlay"] = True
    e["showEq"] = True
    window.fitRows.append(e)
    window.drawPlot(_force=True)
    labels = [str(ln.get_label()) for ln in window.canvas.axes.get_lines()]
    assert any(lbl.startswith("fit:") for lbl in labels)


def test_fit_overlay_off_not_drawn(window, exp_df):
    _register(window, "d.csv", exp_df)
    window._postFileLoad()
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    e["model"] = "a * exp(-b * x) + c"
    e["overlay"] = False
    window.fitRows.append(e)
    window.drawPlot(_force=True)
    labels = [str(ln.get_label()) for ln in window.canvas.axes.get_lines()]
    assert not any(lbl.startswith("fit:") for lbl in labels)


def test_remove_fit(window, exp_df):
    _register(window, "d.csv", exp_df)
    window._postFileLoad()
    window._addFit()
    window._addFit()
    window._removeSelectedFit()          # removes last when none selected
    assert len(window.fitRows) == 1


def test_clear_resets_fits(window, exp_df):
    _register(window, "d.csv", exp_df)
    window._postFileLoad()
    window._addFit()
    window.clearLoadedFiles()
    assert window.fitRows == []
    assert window.fitTable.rowCount() == 0


def test_fit_details_dialog_writes_back(window, exp_df):
    _register(window, "d.csv", exp_df)
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    e["model"] = "a * exp(-b * x) + c"
    dlg = FitDetailsDialog(e, lambda: window._computeFit(e), parent=window)
    dlg._modelEdit.setText("a * x + b")
    dlg._overlayCheck.setChecked(False)
    dlg.accept()
    assert e["model"] == "a * x + b"
    assert e["overlay"] is False


def test_curve_fit_tab_present(window):
    # Curve fitting now lives on the merged "Advanced" tab.
    tooltips = [window.tabs.tabToolTip(i) for i in range(window.tabs.count())]
    assert "Advanced" in tooltips
    assert window.fitTable is not None


# ---------------------------------------------------------------------------
# Shared formula-builder interface in the fit editor
# ---------------------------------------------------------------------------

def _fit_dialog(window, exp_df, model=""):
    _register(window, "d.csv", exp_df)
    e = window._newFitEntry()
    e["xData"] = ("d.csv", "x")
    e["yData"] = ("d.csv", "y")
    e["model"] = model
    cols = window._fitExtraColumns(e)
    return FitDetailsDialog(e, lambda: window._computeFit(e), cols, window), e


def test_fit_dialog_insert_x_and_functions(window, exp_df):
    dlg, _ = _fit_dialog(window, exp_df)
    dlg._modelEdit.setText("")
    dlg._insert("x", 0)
    dlg._insert(" * ", 0)
    dlg._insert("exp()", 1)          # cursor lands inside the parens
    assert dlg._modelEdit.text() == "x * exp()"
    assert dlg._modelEdit.cursorPosition() == len("x * exp(")


def test_fit_dialog_live_parameter_detection(window, exp_df):
    dlg, _ = _fit_dialog(window, exp_df)
    dlg._modelEdit.setText("a * sin(b * x) + c")
    assert "a, b, c" in dlg._paramLabel.text()


def test_fit_dialog_syntax_error_feedback(window, exp_df):
    dlg, _ = _fit_dialog(window, exp_df)
    dlg._modelEdit.setText("a *@ x")
    assert "Syntax error" in dlg._paramLabel.text()


def test_fit_dialog_no_parameters_feedback(window, exp_df):
    dlg, _ = _fit_dialog(window, exp_df)
    dlg._modelEdit.setText("sin(x)")
    assert "No free parameters" in dlg._paramLabel.text()


def test_shared_palette_inserts_into_line_edit(qapp):
    from PySide6.QtWidgets import QLineEdit
    from alekhyam.computedColumnDialog import buildFunctionPalette, insertSnippet
    edit = QLineEdit()
    palette = buildFunctionPalette(lambda s, b: insertSnippet(edit, s, b))
    assert palette is not None                 # builds without error
    insertSnippet(edit, "sqrt()", 1)
    assert edit.text() == "sqrt()" and edit.cursorPosition() == len("sqrt(")
