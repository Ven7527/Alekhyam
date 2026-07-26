import numpy as np
import pandas as pd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import scienceplots  # noqa: F401
from cycler import cycler
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.image import BboxImage
from matplotlib.ticker import MaxNLocator
from matplotlib.transforms import Affine2D, Bbox, TransformedBbox
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QStyle, QVBoxLayout, QWidget,
)

tabColors = [
    "tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple",
    "tab:brown", "tab:pink", "tab:gray", "tab:olive", "tab:cyan",
]

spineWidth      = 2.5
lineWidth       = 2.5
markerSize      = 8
scatterSize     = 60
markerEdgeWidth = 1.4

plt.style.use(["science", "notebook"])
plt.rcParams["axes.prop_cycle"]    = cycler(color=tabColors)
plt.rcParams["axes.grid"]          = False
plt.rcParams["font.family"]        = "DejaVu Serif"
plt.rcParams["axes.linewidth"]     = spineWidth
plt.rcParams["lines.linewidth"]    = lineWidth
plt.rcParams["figure.autolayout"] = False  # prevent conflict with constrained_layout

markerOptions = {
    "None":     None,
    "Circle":   "o",
    "Square":   "s",
    "Triangle": "^",
    "Diamond":  "D",
    "Plus":     "+",
    "Cross":    "x",
    "Star":     "*",
    "Point":    ".",
}


class PlotCanvas(QWidget):
    """Matplotlib figure + navigation toolbar embedded in Qt."""

    # Emitted when the user drags an on-plot element to a new position, so the
    # owning window can persist it (the figure is redrawn from state, so a raw
    # artist move would snap back on the next replot).
    annotationDragged    = Signal(int, float, float)         # id, x, y
    referenceLineDragged = Signal(int, float)                # id, position
    metricDragged        = Signal(int, str, float, float)    # cmpId, key, x, y
    legendDragged        = Signal(float, float)              # lower-left x, y (axes frac)
    shapeChanged         = Signal(int, float, float, float, float)  # id, x, y, w, h
    shapeRotated         = Signal(int, float)               # id, angle (deg)
    shapeSelected        = Signal(int)                       # id, or -1 for none
    shapeDeleteRequested = Signal(int)                       # id
    shapeDuplicateRequested = Signal(int)                   # id
    shapeNudgeRequested  = Signal(int, float, float)        # id, dx, dy (frac)
    shapeRaiseRequested  = Signal(int)                      # id -> bring to front
    shapeLowerRequested  = Signal(int)                      # id -> send to back
    plotRightClicked     = Signal(float, float)             # x, y (axes frac)
    legendItemPicked     = Signal(int)                      # series id

    _HANDLE_SIZE_PX = 8      # half-size of a resize handle, in pixels
    _MIN_SHAPE      = 0.03   # minimum shape width/height, axes fraction

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure  = Figure(figsize=(5, 4), constrained_layout=True)
        self.axes    = self.figure.add_subplot(111)
        self._ax2    = None   # secondary (right) Y axis — managed explicitly
        self.canvas  = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # Drag-to-move: annotations and reference lines can be repositioned by
        # hand. `_draggables` maps the live artists back to their entry ids.
        self._draggables    = []
        self._drag          = None
        self._dragBackground = None
        # Shapes / images: selectable, movable, resizable overlays.
        self._shapes          = []      # {artist, id, kind, x, y, w, h, angle}
        self._selectedShapeId = None
        self._handleArtists   = []      # handle markers for the selected shape
        self._shapeDrag       = None
        self._guideX = None             # snap alignment guide lines
        self._guideY = None
        self._legendLabelToId = {}      # legend label -> series id (click-toggle)
        self._hoverData = []            # [(x, y, color, label, ax)] for readout
        self._hoverMarker = None
        self._hoverText = None
        self._hoverBg = None
        self.canvas.mpl_connect("button_press_event",   self._onDragPress)
        self.canvas.mpl_connect("motion_notify_event",  self._onDragMotion)
        self.canvas.mpl_connect("button_release_event", self._onDragRelease)
        self.canvas.mpl_connect("key_press_event",      self._onKey)

        self._buildWarningBanner()
        self._drawPlaceholder()

    # ------------------------------------------------------------------
    # Warning banner overlay
    # ------------------------------------------------------------------

    def _buildWarningBanner(self):
        self.warningBanner = QWidget(self)
        self.warningBanner.setStyleSheet(
            "background-color: #fff3cd; border: 1px solid #ffe69c; border-radius: 6px;"
        )
        bannerLayout = QHBoxLayout(self.warningBanner)
        bannerLayout.setContentsMargins(8, 6, 10, 6)
        bannerLayout.setSpacing(6)

        iconLabel = QLabel()
        iconLabel.setPixmap(
            self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(18, 18)
        )
        bannerLayout.addWidget(iconLabel)

        self.warningTextLabel = QLabel()
        self.warningTextLabel.setWordWrap(True)
        self.warningTextLabel.setStyleSheet("color: #664d03;")
        bannerLayout.addWidget(self.warningTextLabel)

        self.warningBanner.setMaximumWidth(340)
        self.warningBanner.hide()

    def showWarning(self, text):
        self.warningTextLabel.setText(text)
        self.warningBanner.adjustSize()
        self._positionWarningBanner()
        self.warningBanner.show()
        self.warningBanner.raise_()

    def clearWarning(self):
        self.warningBanner.hide()

    def _positionWarningBanner(self):
        margin = 14
        x = self.width() - self.warningBanner.width() - margin
        y = self.toolbar.height() + margin
        self.warningBanner.move(max(margin, x), y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.warningBanner.isVisible():
            self._positionWarningBanner()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resetAxes(self):
        """Remove the secondary axis (if any) then clear the primary.

        Called at the start of every draw so no artists accumulate across
        redraws — the root cause of twin-Y bugs.
        """
        if self._ax2 is not None:
            self.figure.delaxes(self._ax2)
            self._ax2 = None
        self.axes.clear()

    def _applySpineWidth(self):
        for spine in self.axes.spines.values():
            spine.set_linewidth(spineWidth)
        if self._ax2 is not None:
            for spine in self._ax2.spines.values():
                spine.set_linewidth(spineWidth)

    # ------------------------------------------------------------------
    # Theme — keep the figure in step with the app's light/dark palette
    # ------------------------------------------------------------------

    def _themeColors(self):
        """The plot is always on a white background (publication convention),
        regardless of the app's light/dark theme."""
        return "#ffffff", "#1a1a1a", "#cccccc"

    def _applyTheme(self, transparent=False):
        """Recolour figure/axes text, spines and background for the theme."""
        bg, fg, _grid = self._themeColors()
        if not transparent:
            self.figure.set_facecolor(bg)
        axes = [self.axes] + ([self._ax2] if self._ax2 is not None else [])
        for ax in axes:
            if not transparent:
                ax.set_facecolor(bg)
            ax.title.set_color(fg)
            ax.xaxis.label.set_color(fg)
            ax.yaxis.label.set_color(fg)
            ax.tick_params(axis="both", which="both", colors=fg)
            for spine in ax.spines.values():
                spine.set_edgecolor(fg)
        leg = self.axes.get_legend()
        if leg is not None:
            frame = leg.get_frame()
            frame.set_facecolor(bg)
            frame.set_edgecolor(fg)
            for txt in leg.get_texts():
                txt.set_color(fg)

    def _drawPlaceholder(self, message="Open a CSV file to begin"):
        self._draggables = []
        self._resetAxes()
        self._applySpineWidth()
        bg, fg, _grid = self._themeColors()
        # A prior transparent-export plot leaves alpha at 0 — restore it so
        # the placeholder is not drawn on a see-through canvas.
        self.figure.set_facecolor(bg)
        self.axes.set_facecolor(bg)
        self.figure.patch.set_alpha(1.0)
        self.axes.patch.set_alpha(1.0)
        for spine in self.axes.spines.values():
            spine.set_edgecolor(fg)
        self.axes.text(
            0.5, 0.5, message,
            ha="center", va="center", transform=self.axes.transAxes,
            color=fg, alpha=0.55, fontsize=12,
        )
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Main draw pipeline
    # ------------------------------------------------------------------

    def plot(
        self, series, title=None, xLim=None, yLim=None,
        xLabel=None, yLabel=None,
        xTickSize=11, yTickSize=11, xTickCount=None, yTickCount=None,
        showGrid=False, transparentBackground=False,
        referenceLines=None, fillBands=None,
        showLegend=True, legendPos="best", legendFrame=True,
        textAnnotations=None, fontFamily=None,
        axisLabelSize=10, titleSize=12, legendSize=10,
        xScale="linear", yScale="linear", equalAspect=False, boxAspect=None,
        reverseX=False, reverseY=False, shapes=None,
    ):
        # ── 1. RESET ──────────────────────────────────────────────────
        # Remove old secondary axis from the figure before clearing so it
        # does not accumulate on repeated draws (the core twinx bug fix).
        self._resetAxes()
        self._draggables = []
        self._shapes = []
        self._handleArtists = []
        self._guideX = self._guideY = None
        self._hoverData = []
        self._hoverMarker = self._hoverText = None
        self._hoverBg = None

        if not series:
            self._drawPlaceholder()
            return

        self._legendLabelToId = {e["label"]: e["id"] for e in series
                                 if e.get("id") is not None and e.get("label")}

        if fontFamily:
            plt.rcParams["font.family"] = fontFamily

        # ── 2. SCALES ─────────────────────────────────────────────────
        self.axes.set_xscale(xScale)
        self.axes.set_yscale(yScale)

        # ── 3. TWIN Y AXIS ────────────────────────────────────────────
        needsTwin = any(e.get("useRightAxis") for e in series)
        if needsTwin:
            self._ax2 = self.axes.twinx()
            self._ax2.set_yscale(yScale)
            self._ax2.grid(False)   # grid lives on primary only

        # ── 4. FILLS (drawn first — behind all data) ──────────────────
        for band in fillBands or []:
            kw = dict(
                facecolor=band.get("color") or "#1f77b4",
                alpha=band.get("alpha", 0.2),
                zorder=band.get("zorder", 1),
            )
            lbl = band.get("legendLabel", "")
            if lbl:
                kw["label"] = lbl
            if band["orientation"] == "horizontal":
                self.axes.axhspan(band["start"], band["end"], **kw)
            else:
                self.axes.axvspan(band["start"], band["end"], **kw)

        # ── 5. REFERENCE LINES (behind data, above fills) ─────────────
        for line in referenceLines or []:
            kw = dict(
                color    = line.get("color") or "#888888",
                linestyle= line.get("linestyle", "--"),
                linewidth= line.get("linewidth", 1.5),
                alpha    = line.get("alpha", 0.8),
                zorder   = line.get("zorder", 2),
            )
            if line["orientation"] == "horizontal":
                artist = self.axes.axhline(line["position"], **kw)
            else:
                artist = self.axes.axvline(line["position"], **kw)
            if line.get("id") is not None:
                artist.set_picker(6)
                self._draggables.append({
                    "artist": artist, "kind": "refline",
                    "id": line["id"], "orient": line["orientation"],
                })

        # ── 6. DATA SERIES ────────────────────────────────────────────
        for i, entry in enumerate(series):
            ax       = self._ax2 if entry.get("useRightAxis") and self._ax2 else self.axes
            color    = entry.get("color") or tabColors[i % len(tabColors)]
            marker   = entry.get("marker")
            label    = entry["label"]
            width    = entry.get("linewidth", lineWidth)
            alpha    = entry.get("alpha", 0.9)
            lstyle   = entry.get("linestyle", "-")
            zo       = entry.get("zorder", 3)
            edge_col = "black" if entry.get("markerEdge", True) else "none"
            edge_w   = markerEdgeWidth if entry.get("markerEdge", True) else 0.0
            xVals    = entry["xValues"]
            yVals    = entry["yValues"]

            if entry["kind"] != "histogram":
                xa = xVals.values if hasattr(xVals, "values") else np.asarray(xVals)
                ya = yVals.values if hasattr(yVals, "values") else np.asarray(yVals)
                self._hoverData.append((xa, ya, color, label, ax))

            if entry["kind"] == "histogram":
                ax.hist(
                    yVals,
                    bins=entry.get("bins", 20),
                    label=label, color=color, alpha=alpha,
                    edgecolor=edge_col, linewidth=0.5, zorder=zo,
                )
                continue

            err_vals   = entry.get("errValues")
            color_vals = entry.get("colorValues")

            if entry["kind"] == "scatter":
                if color_vals is not None:
                    ax.scatter(
                        xVals, yVals,
                        label=label,
                        s=entry.get("scatterSize", scatterSize),
                        alpha=alpha,
                        c=color_vals, cmap="viridis",
                        marker=marker or "o",
                        linewidths=0, edgecolors="none", zorder=zo,
                    )
                else:
                    ax.scatter(
                        xVals, yVals,
                        label=label, s=entry.get("scatterSize", scatterSize),
                        alpha=alpha, color=color, marker=marker or "o",
                        linewidths=edge_w, edgecolors=edge_col, zorder=zo,
                    )
                if err_vals is not None:
                    ax.errorbar(
                        xVals, yVals, yerr=err_vals,
                        fmt="none", color=color, alpha=alpha * 0.7,
                        capsize=3, capthick=1.0, elinewidth=1.0, zorder=zo,
                    )
            else:  # line
                if err_vals is not None:
                    ax.errorbar(
                        xVals, yVals, yerr=err_vals,
                        label=label, linewidth=width, color=color,
                        linestyle=lstyle, marker=marker, alpha=alpha,
                        markersize=markerSize, capsize=3, capthick=1.0,
                        markeredgewidth=edge_w if marker else 0.0,
                        markeredgecolor=edge_col if marker else None,
                        zorder=zo,
                    )
                else:
                    ax.plot(
                        xVals, yVals,
                        label=label, linewidth=width, color=color,
                        linestyle=lstyle, marker=marker, alpha=alpha,
                        markersize=markerSize,
                        markeredgewidth=edge_w if marker else 0.0,
                        markeredgecolor=edge_col if marker else None,
                        zorder=zo,
                    )

                # Rolling average overlay
                if entry.get("smoothing"):
                    win = max(2, entry.get("smoothWindow", 10))
                    if len(yVals) >= win:
                        try:
                            y_arr = yVals.values if hasattr(yVals, "values") else np.asarray(yVals)
                            x_arr = xVals.values if hasattr(xVals, "values") else np.asarray(xVals)
                            smooth = pd.Series(y_arr).rolling(
                                window=win, center=True, min_periods=1
                            ).mean().values
                            ax.plot(
                                x_arr, smooth,
                                linewidth=max(1.5, width * 0.7), color=color,
                                linestyle="--", alpha=min(1.0, alpha + 0.15),
                                zorder=zo,
                            )
                        except Exception:
                            pass

        # ── 6b. DATETIME X-AXIS ───────────────────────────────────────
        _non_hist = [e for e in series if e["kind"] != "histogram"]
        xIsDatetime = bool(_non_hist) and any(
            pd.api.types.is_datetime64_any_dtype(
                e["xValues"] if hasattr(e["xValues"], "dtype") else []
            )
            for e in _non_hist
        )
        if xIsDatetime:
            from matplotlib.dates import AutoDateFormatter, AutoDateLocator
            _loc = AutoDateLocator()
            self.axes.xaxis.set_major_locator(_loc)
            self.axes.xaxis.set_major_formatter(AutoDateFormatter(_loc))
            self.figure.autofmt_xdate(rotation=30, ha="right")

        # ── 7. TEXT ANNOTATIONS (top layer, axes-coord or data-coord) ──
        for ann in textAnnotations or []:
            text = ann.get("text", "").strip()
            if not text:
                continue
            kw = dict(
                fontsize  = ann.get("fontSize", 12),
                fontweight= ann.get("fontWeight", "normal"),
                color     = ann.get("color", "#000000"),
                rotation  = ann.get("rotation", 0),
                ha        = ann.get("ha", "center"),
                va        = ann.get("va", "center"),
                zorder    = ann.get("zorder", 4),
            )
            coordType = ann.get("coordType", "axes")
            if coordType == "axes":
                kw["transform"] = self.axes.transAxes
            artist = self.axes.text(ann["x"], ann["y"], text, **kw)
            if ann.get("id") is not None:
                self._draggables.append({
                    "artist": artist, "kind": "annotation",
                    "id": ann["id"], "coordType": coordType,
                })
            elif ann.get("metricRef") is not None:
                self._draggables.append({
                    "artist": artist, "kind": "metric",
                    "ref": ann["metricRef"], "coordType": coordType,
                })

        # ── 8. AXIS LABELS & TITLE ────────────────────────────────────
        # None  → auto-derive from series column names
        # ""    → explicit suppress (user typed #none)
        # text  → use verbatim
        primarySeries = [e for e in series if not e.get("useRightAxis")]
        src = primarySeries or series
        xLabels = {e["xLabel"] for e in src}
        yLabels = {e["yLabel"] for e in src}
        self.axes.set_xlabel(
            xLabel if xLabel is not None else (xLabels.pop() if len(xLabels) == 1 else "X"),
            fontsize=axisLabelSize,
        )
        self.axes.set_ylabel(
            yLabel if yLabel is not None else (yLabels.pop() if len(yLabels) == 1 else "Y"),
            fontsize=axisLabelSize,
        )
        self.axes.set_title(title if title is not None else "", fontsize=titleSize)

        # ── 9. SPINES ─────────────────────────────────────────────────
        self._applySpineWidth()

        # ── 10. LIMITS ────────────────────────────────────────────────
        if xLim is not None:
            self.axes.set_xlim(xLim)
        if yLim is not None:
            self.axes.set_ylim(yLim)

        # ── 11. TICKS ─────────────────────────────────────────────────
        # Leave the x locator alone on a datetime axis — the AutoDateLocator
        # from step 6b must not be clobbered by MaxNLocator.
        if xTickCount and not xIsDatetime:
            self.axes.xaxis.set_major_locator(MaxNLocator(nbins=xTickCount))
        if yTickCount:
            self.axes.yaxis.set_major_locator(MaxNLocator(nbins=yTickCount))
        self.axes.tick_params(axis="x", labelsize=xTickSize)
        self.axes.tick_params(axis="y", labelsize=yTickSize)
        if self._ax2 is not None:
            self._ax2.tick_params(axis="y", labelsize=yTickSize)

        # ── 12. GRID (primary only; _ax2 grid was disabled in step 3) ──
        if showGrid:
            _, _, gridColor = self._themeColors()
            self.axes.grid(True, linestyle="--", alpha=0.5, color=gridColor)
        else:
            self.axes.grid(False)

        # ── 13. LEGEND ────────────────────────────────────────────────
        handles, labels_list = self.axes.get_legend_handles_labels()
        if self._ax2 is not None:
            h2, l2 = self._ax2.get_legend_handles_labels()
            handles    += h2
            labels_list += l2

        if showLegend and handles:
            leg = self.axes.legend(handles, labels_list, loc=legendPos,
                                   frameon=legendFrame, fontsize=legendSize)
            self._draggables.append({"artist": leg, "kind": "legend"})
        elif not showLegend:
            leg = self.axes.get_legend()
            if leg:
                leg.remove()

        # ── 14. ASPECT ────────────────────────────────────────────────
        # Set the state explicitly on every draw — clear() does not reset the
        # aspect, so unchecking the option must restore "auto" here or the
        # equal-aspect view sticks and can't be undone.
        if equalAspect:
            self.axes.set_aspect("equal", adjustable="datalim")
        else:
            self.axes.set_aspect("auto")
        self.axes.set_box_aspect(boxAspect)   # None restores the default

        # ── 14b. AXIS DIRECTION ───────────────────────────────────────
        # Applied last so it flips whatever limits ended up in effect. The
        # secondary axis shares the primary x-axis, so X follows along; its
        # Y axis is independent and must be inverted explicitly.
        if reverseX and self.axes.get_xlim()[0] < self.axes.get_xlim()[1]:
            self.axes.invert_xaxis()
        if reverseY:
            if self.axes.get_ylim()[0] < self.axes.get_ylim()[1]:
                self.axes.invert_yaxis()
            if self._ax2 is not None and self._ax2.get_ylim()[0] < self._ax2.get_ylim()[1]:
                self._ax2.invert_yaxis()

        # ── 15. THEME + TRANSPARENCY ──────────────────────────────────
        self._applyTheme(transparent=transparentBackground)
        self.figure.patch.set_alpha(0.0 if transparentBackground else 1.0)
        self.axes.patch.set_alpha(0.0 if transparentBackground else 1.0)

        # ── 15b. SHAPES & IMAGES (topmost, axes-fraction coords) ──────
        self._renderShapes(shapes or [])
        self._updateHandles()

        # ── 15c. HOVER READOUT artists (hidden until the cursor nears) ─
        (self._hoverMarker,) = self.axes.plot(
            [], [], marker="o", markersize=9, markerfacecolor="none",
            markeredgecolor="#e4572e", markeredgewidth=2.0, linestyle="none",
            zorder=55, animated=True, visible=False)
        self._hoverText = self.axes.annotate(
            "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
            fontsize=9, color="#1a1a1a", zorder=56, animated=True, visible=False,
            bbox=dict(boxstyle="round,pad=0.35", fc="#fffbe6", ec="#e4b400", alpha=0.96))

        # ── 16. FLUSH ─────────────────────────────────────────────────
        self.canvas.draw_idle()

    _POLYGON_SIDES = {"triangle": 3, "pentagon": 5, "hexagon": 6, "star": 5}

    def _shapeVerts(self, kind, x, y, w, h):
        """Vertices (axes-fraction) of a polygon shape inscribed in the bbox."""
        cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
        n = self._POLYGON_SIDES[kind]
        if kind == "star":
            verts = []
            for i in range(2 * n):
                r = 1.0 if i % 2 == 0 else 0.42
                a = np.pi / 2 + i * np.pi / n
                verts.append((cx + rx * r * np.cos(a), cy + ry * r * np.sin(a)))
            return verts
        return [(cx + rx * np.cos(np.pi / 2 + i * 2 * np.pi / n),
                 cy + ry * np.sin(np.pi / 2 + i * 2 * np.pi / n)) for i in range(n)]

    def _applyRotation(self, art, cxf, cyf, angle):
        """Rotate a patch about its centre in *display* space (aspect-correct)."""
        if angle:
            cx, cy = self.axes.transAxes.transform((cxf, cyf))
            art.set_transform(self.axes.transAxes
                              + Affine2D().rotate_deg_around(cx, cy, angle))
        else:
            art.set_transform(self.axes.transAxes)

    def _renderShapes(self, shapes):
        for sh in shapes:
            x, y, w, h = sh["x"], sh["y"], sh["w"], sh["h"]
            kind = sh["kind"]
            angle = sh.get("angle", 0.0)
            zo = sh.get("zorder", 5)
            if kind == "image":
                arr = sh.get("array")
                if arr is None:
                    continue
                bbox = TransformedBbox(Bbox.from_bounds(x, y, w, h),
                                       self.axes.transAxes)
                art = BboxImage(bbox, data=arr, zorder=zo,
                                alpha=sh.get("alpha", 1.0))
                art.set_data(arr)
                self.axes.add_artist(art)
            else:
                fill = sh.get("fill")
                kw = dict(
                    transform=self.axes.transAxes, zorder=zo,
                    facecolor=(fill if fill else "none"),
                    edgecolor=sh.get("color") or "#e4572e",
                    linewidth=sh.get("linewidth", 2.0),
                    alpha=sh.get("alpha", 1.0),
                )
                if kind == "ellipse":
                    art = mpatches.Ellipse((x + w / 2, y + h / 2), w, h, **kw)
                elif kind == "roundrect":
                    r = 0.25 * min(w, h)
                    art = mpatches.FancyBboxPatch(
                        (x + r, y + r), max(w - 2 * r, 1e-4), max(h - 2 * r, 1e-4),
                        boxstyle=f"round,pad={r},rounding_size={r}", **kw)
                elif kind in self._POLYGON_SIDES:
                    art = mpatches.Polygon(self._shapeVerts(kind, x, y, w, h),
                                           closed=True, **kw)
                else:  # rectangle
                    art = mpatches.Rectangle((x, y), w, h, **kw)
                self.axes.add_patch(art)
                self._applyRotation(art, x + w / 2, y + h / 2, angle)
            self._shapes.append({
                "artist": art, "id": sh["id"], "kind": kind,
                "x": x, "y": y, "w": w, "h": h, "angle": angle,
                "locked": sh.get("locked", False),
            })

    # ------------------------------------------------------------------
    # Shapes / images — select, move, resize
    # ------------------------------------------------------------------

    _HANDLE_CURSORS = {
        "n": Qt.SizeVerCursor,  "s": Qt.SizeVerCursor,
        "e": Qt.SizeHorCursor,  "w": Qt.SizeHorCursor,
        "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor,
        "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor,
    }

    def axesPixelAspect(self):
        """width / height of the plot area in pixels (1.0 if unavailable) — used
        so a freshly-inserted shape can default to a *visual* square/circle."""
        try:
            bb = self.axes.get_window_extent()
            if bb.height > 0:
                return bb.width / bb.height
        except Exception:
            pass
        return 1.0

    def _shapeById(self, sid):
        return next((s for s in self._shapes if s["id"] == sid), None)

    def _handlePositions(self, s):
        x, y, w, h = s["x"], s["y"], s["w"], s["h"]
        return {
            "sw": (x, y),          "s": (x + w / 2, y),      "se": (x + w, y),
            "w":  (x, y + h / 2),                            "e": (x + w, y + h / 2),
            "nw": (x, y + h),      "n": (x + w / 2, y + h),  "ne": (x + w, y + h),
        }

    _RESIZE_HANDLES = ("sw", "s", "se", "e", "ne", "n", "nw", "w")
    _OPP = {"nw": "se", "ne": "sw", "sw": "ne", "se": "nw",
            "n": "s", "s": "n", "e": "w", "w": "e"}
    _ODIR = {"se": (1, -1), "sw": (-1, -1), "ne": (1, 1), "nw": (-1, 1),
             "e": (1, 0), "w": (-1, 0), "n": (0, 1), "s": (0, -1)}

    def _handleDisp(self, s):
        """Handle positions in *display* (pixel) coords, honouring rotation.
        Includes 'rot' (rotation grip) for non-image shapes."""
        cxf, cyf = s["x"] + s["w"] / 2, s["y"] + s["h"] / 2
        centre = np.array(self.axes.transAxes.transform((cxf, cyf)))
        bb = self.axes.get_window_extent()
        hw, hh = s["w"] / 2 * bb.width, s["h"] / 2 * bb.height
        th = np.radians(s.get("angle", 0.0))
        rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        units = {"sw": (-1, -1), "s": (0, -1), "se": (1, -1), "e": (1, 0),
                 "ne": (1, 1), "n": (0, 1), "nw": (-1, 1), "w": (-1, 0)}
        out = {name: tuple(centre + rot.dot([ux * hw, uy * hh]))
               for name, (ux, uy) in units.items()}
        if s["kind"] != "image":
            out["rot"] = tuple(centre + rot.dot([0, hh + 26]))
        return out

    def _clearHandleArtists(self):
        for art in self._handleArtists:
            try:
                art.remove()
            except Exception:
                pass
        self._handleArtists = []

    def _updateHandles(self):
        self._clearHandleArtists()
        if self._selectedShapeId is None:
            return
        s = self._shapeById(self._selectedShapeId)
        if s is None or s.get("locked"):
            return
        inv = self.axes.transAxes.inverted()
        disp = self._handleDisp(s)
        sq = [inv.transform(disp[n]) for n in self._RESIZE_HANDLES]
        (squares,) = self.axes.plot(
            [p[0] for p in sq], [p[1] for p in sq],
            linestyle="none", marker="s", markersize=7,
            markerfacecolor="#ffffff", markeredgecolor="#2e73b8",
            markeredgewidth=1.4, transform=self.axes.transAxes,
            zorder=40, clip_on=False)
        self._handleArtists = [squares]
        if "rot" in disp:
            nf = inv.transform(disp["n"])
            rf = inv.transform(disp["rot"])
            (stem,) = self.axes.plot(
                [nf[0], rf[0]], [nf[1], rf[1]], linestyle="-",
                color="#2e73b8", linewidth=1.2, transform=self.axes.transAxes,
                zorder=40, clip_on=False)
            (grip,) = self.axes.plot(
                [rf[0]], [rf[1]], linestyle="none", marker="o", markersize=8,
                markerfacecolor="#2e73b8", markeredgecolor="#ffffff",
                markeredgewidth=1.4, transform=self.axes.transAxes,
                zorder=40, clip_on=False)
            self._handleArtists += [stem, grip]

    def _handleAt(self, event):
        if self._selectedShapeId is None:
            return None
        s = self._shapeById(self._selectedShapeId)
        if s is None or s.get("locked"):
            return None
        disp = self._handleDisp(s)
        for name, (px, py) in disp.items():
            if (abs(px - event.x) <= self._HANDLE_SIZE_PX
                    and abs(py - event.y) <= self._HANDLE_SIZE_PX):
                return name
        return None

    def _shapeAt(self, event):
        for s in reversed(self._shapes):
            if s.get("locked"):
                continue
            try:
                hit, _ = s["artist"].contains(event)
            except Exception:
                hit = False
            if hit:
                return s
        return None

    def _setShapeGeom(self, s, x, y, w, h):
        art, kind = s["artist"], s["kind"]
        if kind == "rect":
            art.set_bounds(x, y, w, h)
        elif kind == "ellipse":
            art.set_center((x + w / 2, y + h / 2))
            art.width, art.height = w, h
        elif kind == "roundrect":
            r = 0.25 * min(w, h)
            art.set_bounds(x + r, y + r, max(w - 2 * r, 1e-4), max(h - 2 * r, 1e-4))
            art.set_boxstyle("round", pad=r, rounding_size=r)
        elif kind in self._POLYGON_SIDES:
            art.set_xy(self._shapeVerts(kind, x, y, w, h))
        elif kind == "image":
            art.bbox = TransformedBbox(Bbox.from_bounds(x, y, w, h),
                                       self.axes.transAxes)
        s["x"], s["y"], s["w"], s["h"] = x, y, w, h
        if kind != "image":
            self._applyRotation(art, x + w / 2, y + h / 2, s.get("angle", 0.0))

    def _resizeRotated(self, d, event):
        """New (x, y, w, h) for a resize drag, with the opposite handle anchored
        in display space so it works for rotated shapes. Ctrl locks the aspect."""
        x0, y0, w0, h0 = d["box"]
        handle, angle = d["handle"], d["angle"]
        anchor = np.array(d["anchor"])
        bb = self.axes.get_window_extent()
        axw, axh = bb.width, bb.height
        th = np.radians(angle)
        rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        rinv = np.array([[np.cos(th), np.sin(th)], [-np.sin(th), np.cos(th)]])
        dl = rinv.dot(np.array([event.x, event.y]) - anchor)   # local offset from anchor
        odx, ody = self._ODIR[handle]
        mpx_x, mpx_y = self._MIN_SHAPE * axw, self._MIN_SHAPE * axh
        w0px, h0px = w0 * axw, h0 * axh
        wpx = max(dl[0] * odx, mpx_x) if odx else w0px
        hpx = max(dl[1] * ody, mpx_y) if ody else h0px
        ctrl = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        if ctrl and odx and ody and w0px > 0 and h0px > 0:
            aspect = w0px / h0px
            if wpx / w0px >= hpx / h0px:
                hpx = wpx / aspect
            else:
                wpx = hpx * aspect
        centre = anchor + rot.dot([odx * wpx / 2, ody * hpx / 2])
        cf = self.axes.transAxes.inverted().transform(centre)
        w, h = wpx / axw, hpx / axh
        return cf[0] - w / 2, cf[1] - h / 2, w, h

    def _refreshHandleArtists(self, s):
        if not self._handleArtists:
            return
        inv = self.axes.transAxes.inverted()
        disp = self._handleDisp(s)
        sq = [inv.transform(disp[n]) for n in self._RESIZE_HANDLES]
        self._handleArtists[0].set_data([p[0] for p in sq], [p[1] for p in sq])
        if len(self._handleArtists) >= 3 and "rot" in disp:
            nf, rf = inv.transform(disp["n"]), inv.transform(disp["rot"])
            self._handleArtists[1].set_data([nf[0], rf[0]], [nf[1], rf[1]])
            self._handleArtists[2].set_data([rf[0]], [rf[1]])

    # ---- Snapping & alignment guides ------------------------------------

    _SNAP_PX = 7

    def _snapTargets(self, exclude_id):
        xs, ys = {0.0, 0.5, 1.0}, {0.0, 0.5, 1.0}
        for s in self._shapes:
            if s["id"] == exclude_id or s.get("locked"):
                continue
            xs.update((s["x"], s["x"] + s["w"] / 2, s["x"] + s["w"]))
            ys.update((s["y"], s["y"] + s["h"] / 2, s["y"] + s["h"]))
        return xs, ys

    def _snap(self, xpts, ypts, exclude_id=None):
        """Return (dx, dy, guide_x, guide_y): the correction to align a moving
        object's snap-points to the nearest target, plus guide-line positions.
        Hold Alt to disable."""
        if bool(QApplication.keyboardModifiers() & Qt.AltModifier):
            return 0.0, 0.0, None, None
        bb = self.axes.get_window_extent()
        tx, ty = self._SNAP_PX / bb.width, self._SNAP_PX / bb.height
        xs, ys = self._snapTargets(exclude_id)
        dx, gx, bestx = 0.0, None, tx
        for p in xpts:
            for t in xs:
                if abs(t - p) < bestx:
                    bestx, dx, gx = abs(t - p), t - p, t
        dy, gy, besty = 0.0, None, ty
        for p in ypts:
            for t in ys:
                if abs(t - p) < besty:
                    besty, dy, gy = abs(t - p), t - p, t
        return dx, dy, gx, gy

    def _createGuides(self):
        style = dict(color="#e4572e", lw=1.0, ls=(0, (4, 3)), alpha=0.85,
                     zorder=40, transform=self.axes.transAxes,
                     clip_on=False, visible=False, animated=True)
        (self._guideX,) = self.axes.plot([0.5, 0.5], [0, 1], **style)
        (self._guideY,) = self.axes.plot([0, 1], [0.5, 0.5], **style)

    def _updateGuides(self, gx, gy):
        if self._guideX is not None:
            self._guideX.set_visible(gx is not None)
            if gx is not None:
                self._guideX.set_data([gx, gx], [0, 1])
        if self._guideY is not None:
            self._guideY.set_visible(gy is not None)
            if gy is not None:
                self._guideY.set_data([0, 1], [gy, gy])

    def _removeGuides(self):
        for g in (self._guideX, self._guideY):
            if g is not None:
                try:
                    g.remove()
                except Exception:
                    pass
        self._guideX = self._guideY = None

    # ---- Hover readout ---------------------------------------------------

    _HOVER_PX = 18

    def _hideHover(self):
        if (self._hoverBg is not None and self._hoverMarker is not None
                and self._hoverMarker.get_visible()):
            self._hoverMarker.set_visible(False)
            self._hoverText.set_visible(False)
            self.canvas.restore_region(self._hoverBg)
            self.canvas.blit(self.figure.bbox)

    def _hoverReadout(self, event):
        if (not self._hoverData or self._hoverMarker is None
                or event.inaxes is None or event.x is None):
            self._hideHover()
            return
        cx, cy = event.x, event.y
        best_disp, best_val, bestd = None, None, float(self._HOVER_PX ** 2)
        for xa, ya, color, label, ax in self._hoverData:
            try:
                pts = ax.transData.transform(np.column_stack([xa, ya]))
            except Exception:
                continue
            d2 = (pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2
            # Non-finite transforms (e.g. a value <= 0 on a log axis, or a NaN)
            # must never win argmin — mask them to +inf so a valid nearer point
            # is still found instead of the whole series being skipped.
            d2 = np.where(np.isfinite(pts).all(axis=1), d2, np.inf)
            if not np.isfinite(d2).any():
                continue
            i = int(np.argmin(d2))
            if d2[i] < bestd:
                bestd, best_disp, best_val = d2[i], pts[i], (xa[i], ya[i], color, label)
        if best_val is None:
            self._hideHover()
            return
        if self._hoverBg is None:
            self._hoverMarker.set_visible(False)
            self._hoverText.set_visible(False)
            self.canvas.draw()
            self._hoverBg = self.canvas.copy_from_bbox(self.figure.bbox)
        mx, my = self.axes.transData.inverted().transform(best_disp)
        xv, yv, color, label = best_val
        self._hoverMarker.set_data([mx], [my])
        self._hoverMarker.set_markeredgecolor(color)
        self._hoverMarker.set_visible(True)
        self._hoverText.xy = (mx, my)
        self._hoverText.set_text(f"{label}\nx = {xv:.4g}\ny = {yv:.4g}")
        self._hoverText.set_visible(True)
        self.canvas.restore_region(self._hoverBg)
        self.axes.draw_artist(self._hoverMarker)
        self.axes.draw_artist(self._hoverText)
        self.canvas.blit(self.figure.bbox)

    def _beginShapeBlit(self, s):
        s["artist"].set_animated(True)
        for art in self._handleArtists:
            art.set_animated(True)
        self.canvas.draw()
        self._dragBackground = self.canvas.copy_from_bbox(self.figure.bbox)
        self.axes.draw_artist(s["artist"])
        for art in self._handleArtists:
            self.axes.draw_artist(art)
        self.canvas.blit(self.figure.bbox)

    def _beginShapeInteraction(self, event):
        handle = self._handleAt(event)
        if handle is not None:
            s = self._shapeById(self._selectedShapeId)
            if handle == "rot":
                self._shapeDrag = {"id": s["id"], "mode": "rotate", "moved": False}
            else:
                self._shapeDrag = {
                    "id": s["id"], "mode": "resize", "handle": handle,
                    "box": (s["x"], s["y"], s["w"], s["h"]),
                    "angle": s.get("angle", 0.0),
                    "anchor": self._handleDisp(s)[self._OPP[handle]],
                    "moved": False}
            self._beginShapeBlit(s)
            return True
        s = self._shapeAt(event)
        if s is not None:
            if s["id"] != self._selectedShapeId:
                self._selectedShapeId = s["id"]
                self.shapeSelected.emit(s["id"])
                self._updateHandles()
            fx, fy = self.axes.transAxes.inverted().transform((event.x, event.y))
            self._shapeDrag = {"id": s["id"], "mode": "move",
                               "box": (s["x"], s["y"], s["w"], s["h"]),
                               "grab": (fx - s["x"], fy - s["y"]), "moved": False}
            self._createGuides()
            self._beginShapeBlit(s)
            return True
        if self._selectedShapeId is not None:
            self._selectedShapeId = None
            self.shapeSelected.emit(-1)
            self._updateHandles()
            self.canvas.draw_idle()
        return False

    def _applyShapeDrag(self, event):
        if event.x is None or event.y is None:
            return
        d = self._shapeDrag
        s = self._shapeById(d["id"])
        if s is None:
            return
        if d["mode"] == "move":
            fx, fy = self.axes.transAxes.inverted().transform((event.x, event.y))
            gx, gy = d["grab"]
            _, _, w0, h0 = d["box"]
            nx = min(max(0.0, fx - gx), max(0.0, 1.0 - w0))
            ny = min(max(0.0, fy - gy), max(0.0, 1.0 - h0))
            sdx, sdy, gux, guy = self._snap(
                [nx, nx + w0 / 2, nx + w0], [ny, ny + h0 / 2, ny + h0], s["id"])
            self._updateGuides(gux, guy)
            self._setShapeGeom(s, nx + sdx, ny + sdy, w0, h0)
        elif d["mode"] == "resize":
            self._setShapeGeom(s, *self._resizeRotated(d, event))
        else:  # rotate
            cxf, cyf = s["x"] + s["w"] / 2, s["y"] + s["h"] / 2
            centre = self.axes.transAxes.transform((cxf, cyf))
            ang = np.degrees(np.arctan2(event.y - centre[1],
                                        event.x - centre[0])) - 90.0
            if bool(QApplication.keyboardModifiers() & Qt.ControlModifier):
                ang = round(ang / 15.0) * 15.0
            s["angle"] = ang % 360.0
            self._applyRotation(s["artist"], cxf, cyf, s["angle"])
        self._refreshHandleArtists(s)
        d["moved"] = True

    def _onKey(self, event):
        sid = self._selectedShapeId
        if sid is None:
            return
        k = event.key
        if k in ("delete", "backspace"):
            self.shapeDeleteRequested.emit(sid)
        elif k == "ctrl+d":
            self.shapeDuplicateRequested.emit(sid)
        elif k in ("pageup", "]", "ctrl+]"):
            self.shapeRaiseRequested.emit(sid)
        elif k in ("pagedown", "[", "ctrl+["):
            self.shapeLowerRequested.emit(sid)
        else:
            step = 0.05 if (k or "").startswith("shift+") else 0.01
            base = (k or "").split("+")[-1]
            dx = {"left": -1, "right": 1}.get(base, 0) * step
            dy = {"up": 1, "down": -1}.get(base, 0) * step
            if dx or dy:
                self.shapeNudgeRequested.emit(sid, dx, dy)

    def clearShapeSelection(self):
        if self._selectedShapeId is not None:
            self._selectedShapeId = None
            self._updateHandles()
            self.canvas.draw_idle()

    def selectShape(self, sid):
        self._selectedShapeId = sid
        self._updateHandles()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Drag-to-move (annotations + reference lines)
    # ------------------------------------------------------------------

    def _draggableAt(self, event):
        """Topmost draggable artist under the cursor, or None."""
        for target in reversed(self._draggables):   # last drawn = on top
            try:
                hit, _ = target["artist"].contains(event)
            except Exception:
                hit = False
            if hit:
                return target
        return None

    def _updateHoverCursor(self, event):
        # Handles / rotation grip first — they can lie just outside the axes.
        handle = self._handleAt(event)
        if handle == "rot":
            self.canvas.setCursor(Qt.CrossCursor)
            return
        if handle is not None:
            self.canvas.setCursor(self._HANDLE_CURSORS.get(handle, Qt.SizeAllCursor))
            return
        if event.inaxes is None:
            self.canvas.setCursor(Qt.ArrowCursor)
            return
        if self._shapeAt(event) is not None:
            self.canvas.setCursor(Qt.SizeAllCursor)
            return
        over = self._draggableAt(event) is not None
        self.canvas.setCursor(Qt.OpenHandCursor if over else Qt.ArrowCursor)

    def _resetDragState(self):
        """Drop any drag left dangling (e.g. by a release delivered off-canvas)
        so a fresh press never continues a stale interaction."""
        if self._shapeDrag is not None:
            s = self._shapeById(self._shapeDrag.get("id"))
            if s is not None:
                s["artist"].set_animated(False)
            for art in self._handleArtists:
                art.set_animated(False)
            self._shapeDrag = None
        if self._drag is not None:
            art = self._drag.get("artist")
            if art is not None:
                try:
                    art.set_animated(False)
                except Exception:
                    pass
            self._drag = None
        self._removeGuides()
        self._dragBackground = None

    def _onDragPress(self, event):
        if getattr(self.toolbar, "mode", ""):
            return
        if event.button == 3 and event.inaxes is not None:
            fx, fy = self.axes.transAxes.inverted().transform((event.x, event.y))
            self.plotRightClicked.emit(float(fx), float(fy))
            return
        # Left button only for the drag interactions below.
        if event.button != 1:
            return
        self._resetDragState()
        # Shapes are handled first — their handles/rotation grip can sit outside
        # the axes rectangle, so this must run before the `inaxes` guard.
        if self._beginShapeInteraction(event):
            return
        if event.inaxes is None:
            return
        target = self._draggableAt(event)
        if target is None:
            return
        self._drag = dict(target, value=None)
        artist = target["artist"]
        if target["kind"] == "legend":
            # Remember where in the legend the user grabbed it, so it doesn't
            # jump — offset between the cursor and the legend's lower-left.
            inv = self.axes.transAxes.inverted()
            box = artist.get_window_extent()
            llx, lly = inv.transform((box.x0, box.y0))
            mx, my = inv.transform((event.x, event.y))
            self._drag["grab"] = (mx - llx, my - lly)
            # Which entry was pressed? A click (no drag) on it toggles the series.
            self._drag["legendLabel"] = None
            for txt in artist.get_texts():
                try:
                    if txt.contains(event)[0]:
                        self._drag["legendLabel"] = txt.get_text()
                        break
                except Exception:
                    pass
        if target["kind"] in ("annotation", "metric", "legend"):
            self._createGuides()
        artist.set_animated(True)
        self.canvas.setCursor(Qt.ClosedHandCursor)
        self.canvas.draw()
        self._dragBackground = self.canvas.copy_from_bbox(self.figure.bbox)
        self.axes.draw_artist(artist)
        self.canvas.blit(self.figure.bbox)

    def _applyDrag(self, event):
        if event.x is None or event.y is None:
            return
        d = self._drag
        artist = d["artist"]
        if d["kind"] in ("annotation", "metric"):
            if d["coordType"] == "axes":
                fx, fy = self.axes.transAxes.inverted().transform((event.x, event.y))
                fx = min(1.0, max(0.0, fx))
                fy = min(1.0, max(0.0, fy))
                sdx, sdy, gux, guy = self._snap([fx], [fy])
                fx, fy = fx + sdx, fy + sdy
                self._updateGuides(gux, guy)
                artist.set_position((fx, fy))
                d["value"] = (fx, fy)
            else:
                xd, yd = self.axes.transData.inverted().transform((event.x, event.y))
                artist.set_position((xd, yd))
                d["value"] = (xd, yd)
        elif d["kind"] == "legend":
            mx, my = self.axes.transAxes.inverted().transform((event.x, event.y))
            gx, gy = d["grab"]
            nx = min(1.0, max(0.0, mx - gx))
            ny = min(1.0, max(0.0, my - gy))
            sdx, sdy, gux, guy = self._snap([nx], [ny])
            nx, ny = nx + sdx, ny + sdy
            self._updateGuides(gux, guy)
            artist.set_loc((nx, ny))
            d["value"] = (nx, ny)
        else:  # reference line
            xd, yd = self.axes.transData.inverted().transform((event.x, event.y))
            if d["orient"] == "horizontal":
                artist.set_ydata([yd, yd])
                d["value"] = yd
            else:
                artist.set_xdata([xd, xd])
                d["value"] = xd

    def _onDragMotion(self, event):
        if self._shapeDrag is not None:
            if self._dragBackground is None:
                return
            self._applyShapeDrag(event)
            self.canvas.restore_region(self._dragBackground)
            s = self._shapeById(self._shapeDrag["id"])
            if s is not None:
                self.axes.draw_artist(s["artist"])
            for art in self._handleArtists:
                self.axes.draw_artist(art)
            for g in (self._guideX, self._guideY):
                if g is not None and g.get_visible():
                    self.axes.draw_artist(g)
            self.canvas.blit(self.figure.bbox)
            return
        if self._drag is None:
            self._updateHoverCursor(event)
            self._hoverReadout(event)
            return
        if self._dragBackground is None:
            return
        self._applyDrag(event)
        self.canvas.restore_region(self._dragBackground)
        self.axes.draw_artist(self._drag["artist"])
        for g in (self._guideX, self._guideY):
            if g is not None and g.get_visible():
                self.axes.draw_artist(g)
        self.canvas.blit(self.figure.bbox)

    def _onDragRelease(self, event):
        if self._shapeDrag is not None:
            d = self._shapeDrag
            s = self._shapeById(d["id"])
            self._shapeDrag = None
            self._dragBackground = None
            self._removeGuides()
            self.canvas.setCursor(Qt.ArrowCursor)
            if s is not None:
                s["artist"].set_animated(False)
                for art in self._handleArtists:
                    art.set_animated(False)
                if d["moved"] and d["mode"] == "rotate":
                    self.shapeRotated.emit(s["id"], float(s.get("angle", 0.0)))
                elif d["moved"]:
                    self.shapeChanged.emit(s["id"], float(s["x"]), float(s["y"]),
                                           float(s["w"]), float(s["h"]))
                else:
                    self.canvas.draw_idle()
            return
        if self._drag is None:
            return
        d = self._drag
        d["artist"].set_animated(False)
        self._drag = None
        self._dragBackground = None
        self._removeGuides()
        self.canvas.setCursor(Qt.ArrowCursor)
        value = d.get("value")
        if value is None:
            # A plain click (no drag). On a legend entry, toggle that series.
            if d["kind"] == "legend" and d.get("legendLabel"):
                sid = self._legendLabelToId.get(d["legendLabel"])
                if sid is not None:
                    self.legendItemPicked.emit(sid)
                    return
            self.canvas.draw_idle()
            return
        if d["kind"] == "annotation":
            self.annotationDragged.emit(d["id"], float(value[0]), float(value[1]))
        elif d["kind"] == "metric":
            ref = d["ref"]
            self.metricDragged.emit(ref["cmpId"], ref["key"],
                                    float(value[0]), float(value[1]))
        elif d["kind"] == "legend":
            self.legendDragged.emit(float(value[0]), float(value[1]))
        else:
            self.referenceLineDragged.emit(d["id"], float(value))

    def clear(self, message="Open a CSV file to begin"):
        self._drawPlaceholder(message)

    def copyToClipboard(self):
        """Render the current figure to PNG and place it on the system clipboard."""
        import io
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QApplication
        buf = io.BytesIO()
        try:
            self.figure.savefig(buf, format="png", dpi=300)
        except Exception:
            return False
        buf.seek(0)
        img = QImage.fromData(buf.read())
        if not img.isNull():
            QApplication.clipboard().setImage(img)
            return True
        return False
