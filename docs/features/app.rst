App-wide features
=================

Undo / Redo
-----------

**Ctrl+Z** and **Ctrl+Y** step through a 20-level history covering all
changes to series, reference lines, fill bands, and annotations.

Tab visibility
--------------

Click the **⚙** corner button on the tab bar to show or hide individual tabs.
Your choices persist across sessions.  At least one tab is always kept visible.

Plot templates
--------------

**File → Save template…** serialises all current axis and style settings to a
JSON file:

- Axis labels and title
- X / Y limits and scale (linear / log)
- Equal aspect and custom box aspect ratio
- Tick label sizes and counts
- Figure font family
- Legend position, frame, and visibility
- Grid

**File → Load template…** applies a saved template in one click.  Useful for
enforcing a house style across different datasets.

Session persistence
-------------------

The following settings survive between sessions:

- Window size and position
- Panel splitter position
- Export format, DPI, and transparency
- Tab visibility choices

Reset view
----------

The **↺** button on the plot toolbar redraws the figure from the current
settings, discarding any zoom or pan applied with the matplotlib toolbar.
