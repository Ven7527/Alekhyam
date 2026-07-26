<div align="center">

<img src="alekhyam/resources/alekhyam.svg" width="96" alt="Alekhyam icon"/>

# Alekhyam: A Simple Python Plotter

**Turn a data file into a chart in seconds — no coding required.**

[![Version](https://img.shields.io/badge/version-0.0.1-2196F3.svg)](pyproject.toml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-2196F3.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2196F3.svg)](LICENSE)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41cd52.svg)](https://doc.qt.io/qtforpython/)

</div>

Alekhyam is a desktop app for plotting data from CSV, TXT, NPY, or NPZ files. Open a file, pick which columns go on which axis, and you get a chart — no writing Python, no Jupyter notebook. You can load several files at once, style each line or set of points on its own, add trend lines, check basic statistics, and save the final chart as an image. Works on Linux, Windows, and macOS.

---

## Install

```bash
pip install alekhyam
```

Then start it from anywhere by typing:

```bash
alekhyam
```

**Linux** — Alekhyam adds itself to your applications menu automatically the first time you run it.

**Windows** — after installing, run this once to add a shortcut to your Start Menu (it also happens automatically the first time you launch Alekhyam):

```bash
alekhyam-register
```

---

## Quick start

1. **File → Open…** (or just drag a file onto the window) to load your data.
2. Go to the **Data & Series** tab. Each row here is one line or set of points on the chart. Pick a column for X, a column for Y, choose Line, Scatter, or Histogram, and click **Plot**.
3. Use the **Axes & Labels** tab to set the title, axis labels, limits, fonts, and legend; use the **Plot Style** tab for the grid, log scales, reference lines, and text annotations.
4. Go to the **Export** tab to save your chart as a PNG, PDF, or SVG file.

The tabs are icon-only to keep things tidy — hover over any tab to see its name. The workflow runs left to right: **Data & Series → Axes & Labels → Plot Style → Advanced → Export**.

---

## What it can do

### Loading files
- Open **several files at once**, in any mix of formats:
  - **CSV / TXT** — Alekhyam figures out the delimiter on its own (comma, semicolon, tab, etc.) so you don't need to tell it.
  - **NPY** — a single saved NumPy array. 1D arrays become one column; 2D arrays become one column per array column.
  - **NPZ** — a NumPy archive holding several named arrays; each array becomes its own column, named after the array.
- **Drag and drop** files of any supported type straight onto the window.
- See a **preview** of each file's data (up to 1,000 rows) before you plot anything.
- **Recent files** menu remembers your last 8 files so you can reopen them in one click.
- If you load two files with the same name, Alekhyam automatically renames the second one so nothing gets overwritten.
- **Dates on the X axis** are detected automatically and formatted nicely (rotated labels, sensible spacing).

### New columns — a spreadsheet-style formula builder
Click **New column…** to build a new column from a formula, the way you would in Excel. Click a column name to insert it, tap a function or operator button, and watch the **live preview** update as you type. It supports the common math functions:

```text
sqrt(x**2 + y**2)          # distance from origin
exp(-time / tau)           # exponential decay
sin(angle) + cos(angle)    # trig
pi * radius ** 2           # constants: pi, e
log(signal) / log(2)       # log, log10, log2, abs, power, floor, ceil, …
```

The new column appears instantly in every picker — no need to edit or re-save your file.

### Series (the lines and points on your chart)
- Pick **X and Y columns from any loaded file** — you can even mix columns from two different files as long as they have the same number of rows.
- Choose **Line, Scatter, or Histogram** for each series. There's also an option to plot against a second Y axis on the right side of the chart.
- **Drag rows up or down** to change the order things are drawn and listed in the legend.
- **Add all columns** — one click adds a series for every numeric column in your file.
- **Duplicate** a series to quickly make a similar one.
- **Show or hide** any series without deleting it.
- Click the little color square next to a series to change its color instantly.
- **Filter rows** — only plot the rows that match a simple condition, like `y > 0`.

### Styling each series
- Color, line style (solid, dashed, dotted), line thickness, and transparency.
- Choose a marker shape for data points — circle, square, triangle, diamond, plus, cross, star, or none.
- Turn marker outlines on or off.
- Set the size of scatter points.
- **Error bars** — show a margin of error above and below each point, using values from another column.
- **Rolling average** — smooth out noisy data with a moving average line drawn on top of your series.
- **Color by column** — for scatter plots, color each point based on the value of a third column (useful for showing an extra dimension of data).
- **Histogram bins** — control how many bars a histogram is split into.

*(Curve fitting lives on the **Advanced** tab — see below.)*

### Axes & Labels tab
- Set your own title and axis labels, or let Alekhyam pick sensible defaults. Type `#none` if you don't want a title or label at all.
- Manually set the minimum and maximum values for either axis, or leave them blank for automatic.
- Adjust the size and number of tick labels on each axis.
- Pick any font installed on your system for the chart text.
- Control the legend's position, whether it has a border, and whether it's shown at all — or just **drag the legend** to place it anywhere on the plot by hand.

### Plot Style tab
- Compact **toggle buttons** (hover any of them for the full description) turn the grid on or off, switch either axis to a logarithmic scale, **reverse** either axis, or lock the X and Y axes to the same aspect ratio.
- Set a custom width-to-height ratio for the plot area.
- **Reference lines** — draw a horizontal or vertical line at a specific value, styled however you like. **Drag it on the plot** to reposition it by hand.
- **Fill bands** — shade a region of the chart (like a tolerance range) with a color of your choice.
- **Text annotations** — add your own text anywhere on the chart, then **drag it into place** directly on the plot (the cursor turns into a hand over anything draggable).
- **Shapes & images** — drop a **rectangle, rounded rectangle, circle/ellipse, triangle, pentagon, hexagon, or star** — or an **imported image** — onto the chart. New shapes come in as a regular (equal-sided) version. Click one to select it, then **drag to move**, pull the **handles to resize** (hold **Ctrl** to lock its aspect ratio), or grab the top **grip to rotate** (hold **Ctrl** to snap to 15°). Press **Delete** to remove the selected one. Each shape has its own line colour, fill, width, opacity, and rotation angle.

### Advanced tab
Two power features share this tab: **Curve fit** and **Compare series**.

**Curve fit** — fit **any function** to your data, not just polynomials. Write a model in terms of `x` and any free parameters (any letters), and Alekhyam finds the best-fit parameter values.

1. Add a fit row and pick the **X** and **Y** columns.
2. Open the **⚙** to type a model, e.g.:

```text
a * x + b                    # line
a * x**2 + b * x + c         # parabola
a * exp(-b * x) + c          # exponential decay
a * sin(b * x + c)           # sinusoid
a / (1 + exp(-b * (x - c)))  # logistic / sigmoid
```

3. Press **Run fit**. You get each parameter's fitted value and ±1σ uncertainty, the **R²**, and the fitted equation.
4. Tick **Overlay** to draw the fitted curve on the plot (with the equation in the legend). Optionally give it initial guesses to help tricky fits converge.

Your model can also **reference other columns** by name — they're used as fixed data, not fitted. For example `a * x + b - offset` fits `a` and `b` while subtracting the `offset` column at each row (clickable chips for `x` and your columns are right there in the editor). Fitting uses `scipy.optimize.curve_fit`, and the same math functions as the formula builder are available (`sin`, `exp`, `log`, `sqrt`, `pi`, …).

**Compare series** — measure how close any two numeric columns are.
- Add a row per comparison; each one reports RMSD, MAE, and MSE.
- Works across files, as long as the two columns have the same number of rows.
- Click the **⚙ details** on any row to see all three metrics, and tick **On plot** to stamp any of them onto the chart as a label (with full control over position and formatting) — then **drag the label** wherever you want it.

### Export
- Save your chart as a **PNG, PDF, or SVG** file.
- Control the resolution (DPI) for image exports — the default is a print-ready **300 dpi**.
- Export with a transparent background if you want to drop it into a slide or document.

### Everything else
- **Light & dark theme** — the whole interface follows your system's light or dark mode. The chart itself always stays on a clean white background (the publishing convention), so it looks right the moment you drop it into a paper, slide, or report.
- **Save / open a project** — save *everything* (your data, series, styles, labels, limits, shapes, fits) to a single **`.plot`** file with **Ctrl+S**, and reopen it later with **Ctrl+Shift+O**. Projects are self-contained — the data is embedded.
- **Live reload** — Alekhyam watches your loaded files; edit a CSV in Excel or re-run a script and the chart updates itself. Toggle it (or reload manually with **Ctrl+R**) from the View menu.
- **Interactive chart** — hover a line to read the nearest point, click a legend entry to hide/show that series, and right-click for Copy / Save / Reset / add-a-shape.
- **Undo / Redo** — up to 20 steps of history for anything you change.
- **Handy shortcuts** — **Ctrl+1…5** switch tabs, **Delete** / **Ctrl+D** remove or duplicate the selected series or shape, arrow keys nudge a shape, and **?** shows the full shortcuts sheet. Right-click a series for **Solo**; type in an X/Y dropdown to filter columns.
- **Palettes & stats** — apply a colour palette to all series at once, see per-column min/max/mean/count (**Stats**), and **export the plotted data** back to CSV.
- **Clear-all buttons** — every list (data files, series, reference lines, fill bands, annotations, shapes, fits, comparisons) has a trash button to wipe it in one click.
- **Show or hide tabs** you don't use, from the small gear icon in the corner of the tab bar.
- Alekhyam remembers your window size, panel layout, and export settings between sessions.
- **Reset view** button — instantly undo any zooming or panning you did on the chart.
- **Copy to clipboard** — copy the current chart as an image and paste it directly into another app.
- **Templates** — save your favorite chart settings (fonts, labels, scale, legend, etc.) to a file and reload them later, so you don't have to set everything up again for a new dataset.
- **Built-in help** — press **F1** or go to **Help → User guide** for an explanation of every feature, right inside the app.

---

## Keyboard shortcuts

| Action | Shortcut |
|---|---|
| Open file(s) | Ctrl+O |
| Copy chart to clipboard | Ctrl+Shift+C |
| Undo | Ctrl+Z |
| Redo | Ctrl+Y |
| Open the user guide | F1 |
| Quit | Ctrl+Q |

---

## Requirements

- Python 3.9 or newer
- PySide6 ≥ 6.5
- pandas ≥ 2.0
- numpy ≥ 1.24
- scipy ≥ 1.10
- matplotlib ≥ 3.7
- scienceplots ≥ 2.1
- qtawesome ≥ 1.3

---

## Troubleshooting

### Windows: `ImportError: DLL load failed while importing QtGui`

This usually happens if you installed Alekhyam into Anaconda's **base**
environment. Anaconda's base environment often already comes with its own
copy of Qt (through packages like `pyqt`, or tools like Jupyter and Spyder),
and that clashes with the Qt version Alekhyam needs.

**Fix** — create a separate, clean environment for Alekhyam instead of using
the base one:

```bash
conda create -n alekhyam python=3.11
conda activate alekhyam
pip install alekhyam
alekhyam
```

If you'd rather keep using your current environment, remove the conflicting
Qt packages and reinstall PySide6:

```bash
conda remove pyqt qt qt-main --force
pip install --force-reinstall pyside6
```

---

## License

[MIT](LICENSE)
