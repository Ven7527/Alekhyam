Compare Series tab
==================

The **Compare Series** tab is hidden by default.  Enable it via the **⚙**
corner button on the tab bar.

It measures how closely two numeric columns agree, using RMSD, MAE, and MSE.
You can add as many comparisons as you like — one row each.

Adding a comparison
-------------------

Click **+** to add a comparison row, then choose a **Reference** column and a
**Compare** column from the inline drop-downs.  The columns can come from
different files, as long as they have the same number of rows.  NaN rows are
dropped before computing.

The row's **RMSD** value is shown at a glance in the table.

Metrics
-------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Metric
     - Formula
   * - RMSD
     - Root-mean-square deviation: :math:`\sqrt{\frac{1}{n}\sum(y_{cmp}-y_{ref})^2}`
   * - MAE
     - Mean absolute error: :math:`\frac{1}{n}\sum|y_{cmp}-y_{ref}|`
   * - MSE
     - Mean squared error: :math:`\frac{1}{n}\sum(y_{cmp}-y_{ref})^2`

Details and adding results to the plot
--------------------------------------

Click the **⚙** button on any comparison row to open its details dialog.  It
shows all three metric values and, for each one:

- an **On plot** checkbox that stamps the metric onto the figure as a text
  label, and
- a **Style…** button controlling that label's position, font size, weight,
  color, alignment, decimal places, and units.

Because each comparison is independent, you can, for example, put the RMSD of
one column pair and the MAE of another onto the same figure.
