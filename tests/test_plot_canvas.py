"""Tests for PlotCanvas and the markerOptions registry."""
import numpy as np
import pytest

from alekhyam.plotCanvas import PlotCanvas, markerOptions


# ---------------------------------------------------------------------------
# markerOptions (pure dict — no Qt needed)
# ---------------------------------------------------------------------------

def test_marker_options_has_none_entry():
    assert "None" in markerOptions
    assert markerOptions["None"] is None


def test_marker_options_standard_markers():
    for name in ("Circle", "Square", "Triangle", "Diamond"):
        assert name in markerOptions
        assert markerOptions[name] is not None


def test_all_marker_codes_are_strings_or_none():
    for name, code in markerOptions.items():
        assert code is None or isinstance(code, str), f"Bad code for {name!r}"


# ---------------------------------------------------------------------------
# PlotCanvas (needs QApplication)
# ---------------------------------------------------------------------------

@pytest.fixture
def canvas(qapp):
    c = PlotCanvas()
    yield c
    c.close()


def _make_series(n=10, kind="line"):
    x = np.linspace(0, 2 * np.pi, n)
    return [{
        "xLabel": "x", "xValues": x,
        "yLabel": "y", "yValues": np.sin(x),
        "kind": kind, "marker": None, "linestyle": "-",
        "label": "test", "color": None, "linewidth": 2.0, "alpha": 1.0,
    }]


def test_canvas_created(canvas):
    assert canvas is not None
    assert canvas.figure is not None
    assert canvas.axes is not None


def test_plot_line_does_not_raise(canvas):
    canvas.plot(_make_series(kind="line"))


def test_plot_scatter_does_not_raise(canvas):
    canvas.plot(_make_series(kind="scatter"))


def test_plot_with_custom_color(canvas):
    s = _make_series()
    s[0]["color"] = "#ff0000"
    canvas.plot(s)


def test_plot_with_dashed_linestyle(canvas):
    s = _make_series()
    s[0]["linestyle"] = "--"
    canvas.plot(s)


def test_plot_with_axis_limits(canvas):
    canvas.plot(_make_series(), xLim=(0, 3), yLim=(-1, 1))


def test_plot_with_axis_labels(canvas):
    canvas.plot(_make_series(), xLabel="Time (s)", yLabel="Amplitude")


def test_plot_with_reference_lines(canvas):
    canvas.plot(
        _make_series(),
        referenceLines=[
            {"orientation": "horizontal", "position": 0.5,
             "color": "#888", "linestyle": "--", "linewidth": 1, "alpha": 0.8},
            {"orientation": "vertical",   "position": 1.0,
             "color": "#888", "linestyle": ":",  "linewidth": 1, "alpha": 0.8},
        ],
    )


def test_plot_empty_series_shows_placeholder(canvas):
    canvas.plot([])
    # Axes should have no line artists after clearing
    assert len(canvas.axes.lines) == 0


def test_plot_with_legend_hidden(canvas):
    canvas.plot(_make_series(), showLegend=False)
    assert canvas.axes.get_legend() is None


def test_plot_with_legend_shown(canvas):
    canvas.plot(_make_series(), showLegend=True)
    assert canvas.axes.get_legend() is not None


def test_plot_legend_frame_on(canvas):
    canvas.plot(_make_series(), showLegend=True, legendFrame=True)
    assert canvas.axes.get_legend().get_frame_on()


def test_plot_legend_frame_off(canvas):
    canvas.plot(_make_series(), showLegend=True, legendFrame=False)
    assert not canvas.axes.get_legend().get_frame_on()


def test_clear_resets_axes(canvas):
    canvas.plot(_make_series())
    canvas.clear()
    assert len(canvas.axes.lines) == 0


def test_show_warning_makes_banner_visible(canvas):
    # isVisible() is False for unshown parents; use isHidden() on the widget itself.
    canvas.showWarning("test warning")
    assert not canvas.warningBanner.isHidden()


def test_clear_warning_hides_banner(canvas):
    canvas.showWarning("test warning")
    canvas.clearWarning()
    assert not canvas.warningBanner.isVisible()


def test_transparent_background(canvas):
    canvas.plot(_make_series(), transparentBackground=True)
    assert canvas.figure.patch.get_alpha() == 0.0


def test_opaque_background(canvas):
    canvas.plot(_make_series(), transparentBackground=False)
    assert canvas.figure.patch.get_alpha() == 1.0
