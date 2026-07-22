Curve Fit tab
=============

The **Curve Fit** tab fits an arbitrary function to a pair of columns and
overlays the result.  Unlike a fixed polynomial fit, you write the model
yourself, so you can fit exponentials, sinusoids, logistic curves — anything
expressible as a formula in ``x`` and a set of free parameters.

Fitting a model
---------------

1. Click **+** to add a fit row, then choose an **X** and **Y** column.
2. Click the **⚙** button to open the fit editor.  It uses the same
   formula-builder interface as :doc:`New column <loading>` — an ``x`` chip,
   the function / operator palette, and a live readout of the parameters it
   has detected.
3. Enter a **model** in terms of ``x`` and free parameters (any letters that
   are not functions or constants become parameters), for example:

   .. code-block:: none

      a * x + b                    # line
      a * x**2 + b * x + c         # parabola
      a * exp(-b * x) + c          # exponential decay
      a * sin(b * x + c)           # sinusoid
      a / (1 + exp(-b * (x - c)))  # logistic / sigmoid

4. Press **Run fit**.

Using other columns in the model
--------------------------------

A model may reference **other columns** of the data by name — those are used
as fixed values (extra independent variables), not fitted parameters.  For
example, with a column called ``offset``::

   a * x + b - offset

fits ``a`` and ``b`` while subtracting the measured ``offset`` at each row.
The available columns appear as clickable chips beside ``x`` in the editor,
and the live readout separates *parameters to fit* from *columns used*.

When a model uses other columns it no longer describes a single smooth curve
of ``x`` alone, so the overlay is drawn through the model's predictions at the
actual data points (ordered by ``x``) rather than as a dense curve.

Results
-------

After a successful fit you see, for each parameter, its fitted value and 1σ
uncertainty, along with the coefficient of determination **R²** and the fitted
equation with the parameters substituted in.  The row's **R²** is also shown
in the table for a quick overview.

Initial guesses
---------------

Nonlinear fits sometimes need a starting point.  Enter comma-separated
**initial guesses** (one per parameter, in the order they appear in the model)
to help the fit converge.  Left blank, every parameter starts at 1.

Overlaying the fit
------------------

Tick **Overlay the fitted curve on the plot** to draw the fit as a dashed
line.  With **Show the fitted equation in the legend** enabled, the legend
entry contains the equation with fitted values.  You can also set the curve's
color.

Available functions
-------------------

The model may use ``sin``, ``cos``, ``tan``, ``arcsin``, ``arccos``,
``arctan``, ``sinh``, ``cosh``, ``tanh``, ``exp``, ``log``, ``log10``,
``log2``, ``sqrt``, ``abs``, the ``**`` power operator, and the constants
``pi`` and ``e``.  Fitting is performed with
:func:`scipy.optimize.curve_fit`.
