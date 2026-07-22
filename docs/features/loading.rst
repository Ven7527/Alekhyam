Loading data
============

Opening files
-------------

Use **File → Open…** (Ctrl+O) to pick one or more files at once, in any mix
of the supported formats:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Format
     - How it's read
   * - ``.csv`` / ``.txt``
     - Delimiter is auto-detected — comma, semicolon, tab, pipe, or any
       whitespace-separated format.
   * - ``.npy``
     - A single saved NumPy array. A 1D array becomes one column named
       ``value``; a 2D array becomes one column per array column
       (``col0``, ``col1``, …); a structured array uses its field names
       as column names.
   * - ``.npz``
     - A NumPy archive of several named arrays. Each array becomes its
       own column, named after the array key. Arrays of different
       lengths are aligned by row index and padded with ``NaN``.

You can also **drag files of any supported type from your file manager and
drop them directly onto the Alekhyam window**.

When the same base filename is loaded more than once, Alekhyam appends an
automatic ``(2)``, ``(3)``, … suffix so nothing is overwritten.

Preview
-------

Selecting a file in the *Loaded files* list shows up to 1 000 rows in
the inline preview table below it.

Recent files
------------

The last 8 opened files are remembered in **File → Recent files** for
one-click re-opening.  Missing files are automatically removed from the list.

New columns — the formula builder
----------------------------------

Click **New column…** above the file list to open a spreadsheet-style
formula builder.  Click a column name to insert it, tap a function or operator
button, and watch the **live preview** update as you type (it also blocks the
*Add column* button while the formula is invalid).

.. code-block:: none

   sqrt(x**2 + y**2)          # distance from origin
   exp(-time / tau)           # exponential decay
   sin(angle) + cos(angle)    # trigonometry
   pi * radius ** 2           # constants: pi, e
   log(signal) / log(2)       # log, log10, log2, abs, power, floor, ceil, …

Available functions include ``sin``, ``cos``, ``tan``, ``arcsin``, ``arccos``,
``arctan``, ``sinh``, ``cosh``, ``tanh``, ``exp``, ``log``, ``log10``,
``log2``, ``sqrt``, ``abs``, ``floor``, ``ceil``, ``round``, plus the
constants ``pi`` and ``e`` (use ``**`` for powers).  Formulas are evaluated in
a sandbox with no access to Python builtins, so they cannot run arbitrary code.

Column names with spaces, or names that clash with a function or a Python
keyword, must be wrapped in **backticks** so they are read as a single column,
e.g. ``` `flow rate` / time ```.  Clicking a column chip inserts the correct
form automatically.  The same rule applies to covariate columns in the
:doc:`Curve Fit <curvefit>` tab.

The result is appended to the dataframe immediately and appears in all series
pickers without saving or reloading the file.

DateTime axis
-------------

If an X column contains datetime-typed values (``pd.to_datetime``-compatible),
Alekhyam automatically switches the X axis to a date locator and formatter with
rotated labels.
