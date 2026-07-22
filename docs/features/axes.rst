Axes & Labels tab
=================

Fine-grained control over labels, limits, ticks, and annotations lives in the
**Axes** tab (sliders icon).

Labels and title
----------------

- **Title** — plot title; leave blank for the filename (single file) or none
  (multiple files).  Type ``#none`` to explicitly suppress the title.
- **X label / Y label** — axis labels; blank = auto-derived from column names;
  ``#none`` = suppress.

Axis limits
-----------

Enter numeric values in the **X** and **Y** min/max boxes.  Leave either field
blank to let matplotlib choose that bound automatically.

Tick labels
-----------

- **X / Y label size** — font size of the tick labels (6 – 24 pt).
- **X / Y tick count** — hint for the number of major ticks (2 – 30).

Figure font
-----------

The **Family** drop-down lists every font installed on the system.  The plot
re-renders immediately when you change it.  The default is *DejaVu Serif* from
the SciencePlots style.

Legend
------

- **Show legend** — toggle the legend.
- **Show frame border** — draw a box around the legend.
- **Position** — best, upper right, upper left, lower left, lower right,
  center, upper center, lower center.

Text annotations
----------------

Place arbitrary text anywhere on the plot.  Each annotation can use either
**axes coordinates** (0 – 1, relative to the plot area) or **data
coordinates** (actual X/Y values).

Settings per annotation:

- Text content
- Position (x, y)
- Coordinate type (axes or data)
- Font size, weight, and color
- Rotation
- Horizontal and vertical alignment
