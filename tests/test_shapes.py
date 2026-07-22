"""Tests for interactive on-plot shapes (rectangles, ellipses) and images.

Covers the shape model + table, the persist-on-drop handlers, a full
press→motion→release move and resize on the canvas, Ctrl aspect-locking during
resize, delete/clear, show/hide, undo, and image placement.
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
from matplotlib.backend_bases import MouseEvent

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem


def _load(window, df=None, label="d.csv"):
    df = df if df is not None else pd.DataFrame({"x": np.arange(10),
                                                 "y": np.arange(10).astype(float)})
    window.dataFrames[label] = df
    item = QListWidgetItem(label)
    item.setData(Qt.UserRole, label)
    window.filesList.addItem(item)
    window._postFileLoad()
    window._addAllColumns()


def _plotted(window):
    window.show()
    window.drawPlot()
    window.canvas.canvas.draw()


def _mouse(window, name, xy_axesfrac, button=1):
    px, py = window.canvas.axes.transAxes.transform(xy_axesfrac)
    return MouseEvent(name, window.canvas.canvas, px, py, button=button)


@pytest.fixture
def shape_window(window):
    _load(window)
    _plotted(window)
    window._addShape("rect")
    window._addShape("ellipse")
    window.canvas.canvas.draw()
    return window


# ---------------------------------------------------------------------------

def test_add_shapes(shape_window):
    w = shape_window
    assert [e["kind"] for e in w.shapeRows] == ["rect", "ellipse"]
    assert [s["kind"] for s in w.canvas._shapes] == ["rect", "ellipse"]
    assert w.shapeTable.rowCount() == 2
    # last added is selected on the plot
    assert w.canvas._selectedShapeId == w.shapeRows[1]["id"]


def test_add_shape_requires_data(window):
    window.show()
    window._addShape("rect")
    assert window.shapeRows == []


def test_shape_move_persists_and_is_undoable(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    before = tuple(w.shapeRows[0][k] for k in ("x", "y", "w", "h"))
    w.canvas.shapeChanged.emit(sid, 0.1, 0.1, 0.5, 0.4)
    assert tuple(w._findShapeById(sid)[k] for k in ("x", "y", "w", "h")) == (0.1, 0.1, 0.5, 0.4)
    w.undo()
    assert tuple(w._findShapeById(sid)[k] for k in ("x", "y", "w", "h")) == before


def test_interactive_move(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    # park the rect in the empty bottom-left, clear of the (overlapping) ellipse
    w.shapeRows[0].update(x=0.05, y=0.05, w=0.25, h=0.25)
    w.drawPlot()
    w.canvas.selectShape(sid)
    w.canvas.canvas.draw()
    cx, cy = 0.175, 0.175                                  # rect centre
    w.canvas._onDragPress(_mouse(w, "button_press_event", (cx, cy)))
    assert w.canvas._shapeDrag["mode"] == "move"
    w.canvas._onDragMotion(_mouse(w, "motion_notify_event", (cx + 0.2, cy + 0.1)))
    w.canvas._onDragRelease(_mouse(w, "button_release_event", (cx + 0.2, cy + 0.1)))
    moved = w._findShapeById(sid)
    assert moved["x"] == pytest.approx(0.25, abs=0.03)
    assert moved["y"] == pytest.approx(0.15, abs=0.03)


def test_interactive_resize_se_handle(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    w.canvas.selectShape(sid)
    w.canvas.canvas.draw()
    hpos = w.canvas._handlePositions(w.canvas._shapeById(sid))["se"]
    w.canvas._onDragPress(_mouse(w, "button_press_event", hpos))
    assert w.canvas._shapeDrag["handle"] == "se"
    w.canvas._onDragMotion(_mouse(w, "motion_notify_event", (0.8, 0.05)))
    w.canvas._onDragRelease(_mouse(w, "button_release_event", (0.8, 0.05)))
    e = w._findShapeById(sid)
    assert e["w"] == pytest.approx(0.8 - e["x"], abs=0.03)


def _resize_via_handle(window, sid, target_axesfrac, modifier):
    """Drag the 'se' handle to target while holding `modifier`; return new (w, h)."""
    window.canvas.selectShape(sid)
    window.canvas.canvas.draw()
    hpos = window.canvas._handleDisp(window.canvas._shapeById(sid))["se"]
    window.canvas._onDragPress(MouseEvent("button_press_event", window.canvas.canvas,
                                          hpos[0], hpos[1], button=1))
    with patch("alekhyam.plotCanvas.QApplication.keyboardModifiers",
               return_value=modifier):
        window.canvas._onDragMotion(_mouse(window, "motion_notify_event", target_axesfrac))
        window.canvas._onDragRelease(_mouse(window, "button_release_event", target_axesfrac))
    e = window._findShapeById(sid)
    return e["w"], e["h"]


def test_ctrl_locks_aspect_ratio(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    # give it a clear, known non-square box (aspect w/h = 2)
    w.shapeRows[0].update(x=0.2, y=0.4, w=0.4, h=0.2)
    w.drawPlot()
    aspect0 = 0.4 / 0.2
    w_free, h_free = _resize_via_handle(w, sid, (0.85, 0.05), Qt.NoModifier)
    w.shapeRows[0].update(x=0.2, y=0.4, w=0.4, h=0.2)
    w.drawPlot()
    w_lock, h_lock = _resize_via_handle(w, sid, (0.85, 0.05), Qt.ControlModifier)
    assert (w_free / h_free) != pytest.approx(aspect0, abs=0.05)   # free: aspect drifts
    assert (w_lock / h_lock) == pytest.approx(aspect0, abs=0.05)   # locked: aspect held


def test_rotation_persists_and_is_undoable(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    assert w.shapeRows[0].get("angle", 0.0) == 0.0
    w.canvas.shapeRotated.emit(sid, 42.0)
    assert w._findShapeById(sid)["angle"] == 42.0
    w.undo()
    assert w._findShapeById(sid)["angle"] == 0.0


def test_rotation_handle_present_for_shapes_not_images(shape_window, tmp_path):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    w.canvas.selectShape(sid)
    assert "rot" in w.canvas._handleDisp(w.canvas._shapeById(sid))


def test_show_toggle_hides_shape(shape_window):
    w = shape_window
    w.shapeRows[0]["show"] = False
    w.drawPlot()
    assert [s["id"] for s in w.canvas._shapes] == [w.shapeRows[1]["id"]]


def test_delete_request_and_clear(shape_window):
    w = shape_window
    w.canvas.shapeDeleteRequested.emit(w.shapeRows[0]["id"])
    assert len(w.shapeRows) == 1
    w._clearShapes()
    assert w.shapeRows == []
    assert w.canvas._selectedShapeId is None


def test_shape_add_is_undoable(shape_window):
    w = shape_window
    assert len(w.shapeRows) == 2
    w.undo()                       # undo the ellipse add
    assert len(w.shapeRows) == 1


def test_handle_outside_axes_is_grabbable(shape_window):
    """The rotation grip sits above the shape and can fall outside the axes
    rectangle; pressing it must still start a rotate drag."""
    w = shape_window
    sid = w.shapeRows[0]["id"]
    w.shapeRows[0].update(x=0.4, y=0.82, w=0.2, h=0.15)   # push it against the top
    w.drawPlot()
    w.canvas.selectShape(sid)
    w.canvas.canvas.draw()
    gx, gy = w.canvas._handleDisp(w.canvas._shapeById(sid))["rot"]
    ev = MouseEvent("button_press_event", w.canvas.canvas, gx, gy, button=1)
    assert ev.inaxes is None                              # grip really is outside
    w.canvas._onDragPress(ev)
    assert w.canvas._shapeDrag is not None
    assert w.canvas._shapeDrag["mode"] == "rotate"


def test_stale_drag_is_reset_on_new_press(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    w.canvas.selectShape(sid)
    w.canvas.canvas.draw()
    s = w.canvas._shapeById(sid)
    cx, cy = s["x"] + s["w"] / 2, s["y"] + s["h"] / 2
    w.canvas._onDragPress(_mouse(w, "button_press_event", (cx, cy)))
    w.canvas._onDragMotion(_mouse(w, "motion_notify_event", (cx + 0.1, cy)))
    # ... release is "lost" (never delivered). A new press must clear the stale
    # drag and un-animate the artist so it doesn't vanish on the next redraw.
    w.canvas._onDragPress(_mouse(w, "button_press_event", (0.95, 0.95)))
    assert w.canvas._shapeDrag is None
    assert w.canvas._shapeById(sid)["artist"].get_animated() is False


def test_resize_past_opposite_edge_clamps_no_flip(shape_window):
    w = shape_window
    sid = w.shapeRows[0]["id"]
    w.shapeRows[0].update(x=0.4, y=0.4, w=0.3, h=0.3)
    w.drawPlot()
    w.canvas.selectShape(sid)
    w.canvas.canvas.draw()
    se = w.canvas._handleDisp(w.canvas._shapeById(sid))["se"]
    w.canvas._onDragPress(MouseEvent("button_press_event", w.canvas.canvas, se[0], se[1], button=1))
    w.canvas._onDragMotion(_mouse(w, "motion_notify_event", (0.1, 0.9)))   # drag past nw
    w.canvas._onDragRelease(_mouse(w, "motion_notify_event", (0.1, 0.9)))
    e = w._findShapeById(sid)
    assert e["w"] >= w.canvas._MIN_SHAPE - 1e-6
    assert e["h"] >= w.canvas._MIN_SHAPE - 1e-6


def test_image_render_and_resize(window, tmp_path):
    import matplotlib.image as mpimg
    arr = np.zeros((40, 80, 3), dtype=np.uint8)
    arr[:, :, 1] = 200
    p = tmp_path / "img.png"
    mpimg.imsave(str(p), arr)

    _load(window)
    _plotted(window)
    entry = window._newShapeEntry("image")
    entry["imageId"] = entry["id"]
    entry["path"] = str(p)
    entry["x"], entry["y"], entry["w"], entry["h"] = 0.3, 0.4, 0.35, 0.2
    window._imageCache[entry["id"]] = mpimg.imread(str(p))
    window.shapeRows.append(entry)
    window._rebuildShapeTable()
    window.drawPlot()
    window.canvas.canvas.draw()

    assert [s["kind"] for s in window.canvas._shapes] == ["image"]
    window.canvas.selectShape(entry["id"])
    window.canvas.canvas.draw()
    hpos = window.canvas._handlePositions(window.canvas._shapeById(entry["id"]))["se"]
    window.canvas._onDragPress(_mouse(window, "button_press_event", hpos))
    window.canvas._onDragMotion(_mouse(window, "motion_notify_event", (0.85, 0.1)))
    window.canvas._onDragRelease(_mouse(window, "button_release_event", (0.85, 0.1)))
    assert entry["w"] == pytest.approx(0.85 - entry["x"], abs=0.03)
