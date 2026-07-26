"""Tests for dragging on-plot elements (text annotations + reference lines).

The figure is redrawn from state on every change, so a hand-drag must write the
new position back into the owning entry. These tests cover the artist→id capture
in PlotCanvas, the persist-on-drop handlers in MainWindow, a full synthetic
press→motion→release cycle, undo support, and that non-persistable (id-less)
annotations are not draggable.
"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.backend_bases import MouseEvent

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem


def _load(window, df, label="d.csv"):
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    window._postFileLoad()
    window._addAllColumns()


def _plotted(window):
    """Draw and force a real render so axes transforms are valid."""
    window.drawPlot()
    window.canvas.canvas.draw()


@pytest.fixture
def dragged_window(window):
    _load(window, pd.DataFrame({"x": np.arange(20),
                                "y": np.linspace(-1.0, 1.0, 20)}))
    window._addReferenceLine("horizontal")           # position 0.0
    ann = window._newTextAnnotationEntry()
    ann.update(text="note", x=0.3, y=0.4, coordType="axes")
    window.textAnnotationRows.append(ann)
    window._rebuildTextAnnotationTable()
    _plotted(window)
    return window, ann


def _mouse(window, name, x, y, button=1):
    return MouseEvent(name, window.canvas.canvas, x, y, button=button)


# ---------------------------------------------------------------------------

def test_draggables_captured(dragged_window):
    window, ann = dragged_window
    ided = {(d["kind"], d["id"]) for d in window.canvas._draggables if "id" in d}
    assert ("refline", window.referenceLineRows[0]["id"]) in ided
    assert ("annotation", ann["id"]) in ided
    # the legend is draggable too (it has no entry id)
    assert any(d["kind"] == "legend" for d in window.canvas._draggables)


def test_annotation_drag_persists(dragged_window):
    window, ann = dragged_window
    window.canvas.annotationDragged.emit(ann["id"], 0.62, 0.18)
    assert ann["x"] == pytest.approx(0.62)
    assert ann["y"] == pytest.approx(0.18)


def test_reference_line_drag_persists(dragged_window):
    window, _ = dragged_window
    rid = window.referenceLineRows[0]["id"]
    window.canvas.referenceLineDragged.emit(rid, 0.75)
    assert window.referenceLineRows[0]["position"] == pytest.approx(0.75)


def test_interactive_reference_line_drag(dragged_window):
    window, _ = dragged_window
    ax = window.canvas.axes
    xmid = 10
    px, py = ax.transData.transform((xmid, 0.0))         # on the line at y=0
    window.canvas._onDragPress(_mouse(window, "button_press_event", px, py))
    assert window.canvas._drag is not None
    px2, py2 = ax.transData.transform((xmid, 0.6))
    window.canvas._onDragMotion(_mouse(window, "motion_notify_event", px2, py2))
    window.canvas._onDragRelease(_mouse(window, "button_release_event", px2, py2))
    assert window.canvas._drag is None
    assert window.referenceLineRows[0]["position"] == pytest.approx(0.6, abs=0.02)


def test_drag_is_undoable(dragged_window):
    window, _ = dragged_window
    rid = window.referenceLineRows[0]["id"]
    window.canvas.referenceLineDragged.emit(rid, 0.9)
    assert window.referenceLineRows[0]["position"] == pytest.approx(0.9)
    window.undo()
    assert window.referenceLineRows[0]["position"] == pytest.approx(0.0)


def test_plain_click_does_not_move_or_snapshot(dragged_window):
    window, _ = dragged_window
    ax = window.canvas.axes
    before = window.referenceLineRows[0]["position"]
    undo_depth = len(window._undoStack) if hasattr(window, "_undoStack") else None
    px, py = ax.transData.transform((10, 0.0))
    window.canvas._onDragPress(_mouse(window, "button_press_event", px, py))
    # release without moving
    window.canvas._onDragRelease(_mouse(window, "button_release_event", px, py))
    assert window.referenceLineRows[0]["position"] == pytest.approx(before)
    if undo_depth is not None:
        assert len(window._undoStack) == undo_depth


def test_idless_annotation_not_draggable(window):
    """Annotations passed without an id (e.g. injected comparison metrics) are
    rendered but cannot be dragged."""
    series = [{"kind": "line", "xValues": np.arange(5), "yValues": np.arange(5),
               "label": "a", "xLabel": "x", "yLabel": "y"}]
    window.canvas.plot(
        series=series,
        textAnnotations=[
            {"text": "real", "x": 0.2, "y": 0.2, "coordType": "axes", "id": 99},
            {"text": "injected", "x": 0.8, "y": 0.8, "coordType": "axes"},  # no id
        ],
        referenceLines=[],
    )
    ids = [d["id"] for d in window.canvas._draggables if d["kind"] == "annotation"]
    assert ids == [99]


def test_no_draggables_without_plot(window):
    window.canvas.clear()
    assert window.canvas._draggables == []
    ev = MouseEvent("motion_notify_event", window.canvas.canvas, 5, 5)
    assert window.canvas._draggableAt(ev) is None


# ---------------------------------------------------------------------------
# Legend + comparison-metric dragging
# ---------------------------------------------------------------------------

@pytest.fixture
def metric_window(window):
    _load(window, pd.DataFrame({"a": np.arange(20).astype(float),
                                "b": (np.arange(20) * 1.1).astype(float)}))
    window._addComparison()
    c = window.comparisonRows[0]
    c["refData"] = ("d.csv", "a")
    c["cmpData"] = ("d.csv", "b")
    c["metrics"]["RMSD"]["add"] = True
    _plotted(window)
    return window, c


def test_legend_is_draggable_and_persists(metric_window):
    window, _ = metric_window
    assert window._legendLoc is None
    window.canvas.legendDragged.emit(0.42, 0.05)
    assert window._legendLoc == (0.42, 0.05)


def test_interactive_legend_drag(metric_window):
    window, _ = metric_window
    leg = next(d["artist"] for d in window.canvas._draggables if d["kind"] == "legend")
    box = leg.get_window_extent()
    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    window.canvas._onDragPress(_mouse(window, "button_press_event", cx, cy))
    assert window.canvas._drag["kind"] == "legend"
    tx, ty = window.canvas.axes.transAxes.transform((0.15, 0.15))
    window.canvas._onDragMotion(_mouse(window, "motion_notify_event", tx, ty))
    window.canvas._onDragRelease(_mouse(window, "button_release_event", tx, ty))
    assert window._legendLoc is not None
    assert 0.0 <= window._legendLoc[0] <= 1.0


def test_picking_named_position_clears_dragged_legend(metric_window):
    window, _ = metric_window
    window._legendLoc = (0.3, 0.3)
    window.legendPosCombo.setCurrentText("upper left")
    window.legendPosCombo.activated.emit(window.legendPosCombo.currentIndex())
    assert window._legendLoc is None


def test_metric_label_is_draggable_and_persists(metric_window):
    window, c = metric_window
    metrics = [d for d in window.canvas._draggables if d["kind"] == "metric"]
    assert len(metrics) == 1
    assert metrics[0]["ref"] == {"cmpId": c["id"], "key": "RMSD"}
    window.canvas.metricDragged.emit(c["id"], "RMSD", 0.6, 0.3)
    s = c["metrics"]["RMSD"]["settings"]
    assert (s["x"], s["y"]) == (0.6, 0.3)
