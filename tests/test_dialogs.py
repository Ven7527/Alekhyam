"""Tests for SeriesStyleDialog and ReferenceLineStyleDialog."""
import pytest

from alekhyam.seriesStyleDialog import SeriesStyleDialog, lineStyleOptions
from alekhyam.referenceLineStyleDialog import (
    ReferenceLineStyleDialog,
    lineStyleOptions as refLineStyleOptions,
)


# ---------------------------------------------------------------------------
# lineStyleOptions sanity
# ---------------------------------------------------------------------------

def test_series_linestyle_options_have_solid():
    assert "Solid" in lineStyleOptions
    assert lineStyleOptions["Solid"] == "-"


def test_series_linestyle_options_have_dashed():
    assert "Dashed" in lineStyleOptions
    assert lineStyleOptions["Dashed"] == "--"


def test_ref_linestyle_options_match_series():
    # Both dialogs must expose the same matplotlib codes.
    assert set(lineStyleOptions.values()) == set(refLineStyleOptions.values())


# ---------------------------------------------------------------------------
# SeriesStyleDialog
# ---------------------------------------------------------------------------

SERIES_ENTRY = {
    "legendLabel": "my series",
    "color": "#ff0000",
    "linestyle": "--",
    "linewidth": 3.0,
    "marker": "o",
    "alpha": 0.75,
}


@pytest.fixture
def series_dialog(qapp):
    dlg = SeriesStyleDialog(SERIES_ENTRY)
    yield dlg
    dlg.close()


def test_series_dialog_loads_legend_label(series_dialog):
    assert series_dialog.legendEdit.text() == "my series"


def test_series_dialog_loads_linestyle(series_dialog):
    assert series_dialog.lineStyleCombo.currentText() == "Dashed"


def test_series_dialog_loads_marker(series_dialog):
    assert series_dialog.markerCombo.currentText() == "Circle"


def test_series_dialog_result_has_required_keys(series_dialog):
    result = series_dialog.resultValues()
    for key in ("legendLabel", "color", "linestyle", "linewidth", "marker", "alpha"):
        assert key in result, f"Missing key: {key}"


def test_series_dialog_result_linestyle_is_code(series_dialog):
    result = series_dialog.resultValues()
    assert result["linestyle"] in lineStyleOptions.values()


def test_series_dialog_result_alpha_in_range(series_dialog):
    alpha = series_dialog.resultValues()["alpha"]
    assert 0.0 <= alpha <= 1.0


def test_series_dialog_result_linewidth_positive(series_dialog):
    lw = series_dialog.resultValues()["linewidth"]
    assert lw > 0


def test_series_dialog_defaults_for_empty_entry(qapp):
    dlg = SeriesStyleDialog({})
    result = dlg.resultValues()
    assert result["linestyle"] == "-"       # solid default
    assert result["legendLabel"] == ""
    assert result["color"] is None
    dlg.close()


# ---------------------------------------------------------------------------
# ReferenceLineStyleDialog
# ---------------------------------------------------------------------------

REF_ENTRY = {
    "color": "#0000ff",
    "linestyle": ":",
    "linewidth": 1.5,
    "alpha": 0.8,
}


@pytest.fixture
def ref_dialog(qapp):
    dlg = ReferenceLineStyleDialog(REF_ENTRY)
    yield dlg
    dlg.close()


def test_ref_dialog_loads_linestyle(ref_dialog):
    assert ref_dialog.styleCombo.currentText() == "Dotted"


def test_ref_dialog_result_has_required_keys(ref_dialog):
    result = ref_dialog.resultValues()
    for key in ("color", "linestyle", "linewidth", "alpha"):
        assert key in result


def test_ref_dialog_result_linestyle_is_code(ref_dialog):
    result = ref_dialog.resultValues()
    assert result["linestyle"] in refLineStyleOptions.values()


def test_ref_dialog_result_alpha_in_range(ref_dialog):
    alpha = ref_dialog.resultValues()["alpha"]
    assert 0.0 <= alpha <= 1.0
