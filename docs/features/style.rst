Series style
============

Click the **⚙** gear button on any series row to open its style dialog.
The dialog adapts to the series type.

Basic appearance
----------------

All types share these controls:

- **Legend label** — overrides the auto-generated ``y vs x`` label; leave blank for auto.
- **Color** — series color picker.
- **Opacity** — alpha value (0.05 – 1.0).

Line series
-----------

- **Line style** — Solid, Dashed, Dotted, Dash-dot.
- **Line width** — 0.5 – 6.0 pt.
- **Marker** — optional point marker (Circle, Square, Triangle, Diamond, Plus, Cross, Star, Point).
- **Marker edge** — draw or suppress the outline around markers.
- **Right Y axis** — plot against the secondary (right) axis.

Scatter series
--------------

- **Point size** — marker area in pt².
- **Marker** — shape of each point.
- **Marker edge** — draw or suppress the outline.
- **Right Y axis** — plot against the secondary (right) axis.

Histogram series
----------------

- **Bins** — number of histogram bins (2 – 500).

Error bars
----------

*Available for Line and Scatter.*

Check **Show error bars** and pick an **Error column** from any loaded file.
The column values are used as symmetric ±y error.  Bars are drawn as
cap-style error bars at 70 % opacity.

Rolling average overlay
-----------------------

*Available for Line series.*

Check **Show rolling average** and set a **Window** size in data points.
A dashed overlay is drawn using a center-aligned rolling mean with
``min_periods=1``.

.. note::

   Curve fitting has moved to its own :doc:`curvefit` tab, where you can fit
   an arbitrary model — not just a polynomial — to any column pair.

Color by column
---------------

*Available for Scatter series.*

Check **Map color to a column**, pick a numeric column, and Alekhyam maps its
values to the **viridis** colormap.  This overrides the series color setting.

Row filter
----------

Enter a pandas query expression to plot only matching rows.  Uses ``x`` and
``y`` to refer to the plotted columns regardless of their original names:

.. code-block:: none

   y > 0
   x >= 1.5 and y < 100
