Series
======

Each row in the **Series** tab is one independent series on the plot.

Adding series
-------------

- Click **+** to add a blank series and choose columns from the drop-downs.
- Click **Add all** to create one series per numeric column in one click,
  all sharing the first column as X.
- Click the **duplicate** button (copy icon) to clone the selected row,
  including its style and data selection.

X and Y columns
---------------

The **X** and **Y** drop-downs list every column from every loaded file in
the format ``column name: filename``.  Cross-file pairings are supported as
long as both files have the same number of rows.

Plot types
----------

Choose from the **Type** combo on each row:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Type
     - Description
   * - Line
     - Connected line plot; supports error bars, rolling average, and curve fit
   * - Scatter
     - Unconnected markers; supports error bars and color-by-column
   * - Histogram
     - Frequency histogram of the Y column; X column is ignored
   * - Line (R)
     - Line series plotted against the **right** Y axis
   * - Scatter (R)
     - Scatter series plotted against the **right** Y axis

Reordering
----------

Drag any row up or down to change the draw order and legend order.

Show / hide
-----------

The checkbox in the leftmost column toggles a series on and off without
deleting it.

Color swatch
------------

Click the color swatch (second column) to change a series color without
opening the full style dialog.

Row filter
----------

Open the style dialog (⚙ button) and enter a **pandas query** expression in
the *Row filter* field.  Only rows satisfying the query are plotted:

.. code-block:: none

   y > 0
   x >= 1.5
   y > 0 and x < 10
