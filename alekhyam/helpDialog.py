from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QSplitter, QTextBrowser, QVBoxLayout,
    QListWidget, QListWidgetItem,
)

_STYLE = """
body        { font-family: sans-serif; font-size: 13px; margin: 12px 16px; color: #1a1a1a; }
h2          { font-size: 15px; font-weight: 600; margin: 20px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
h3          { font-size: 13px; font-weight: 600; margin: 14px 0 4px; }
p           { margin: 4px 0 8px; line-height: 1.5; }
ul          { margin: 4px 0 8px 18px; padding: 0; }
li          { margin-bottom: 3px; line-height: 1.45; }
code        { font-family: monospace; background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
table       { border-collapse: collapse; width: 100%; margin: 6px 0 10px; }
th          { background: #f5f5f5; font-weight: 600; text-align: left; padding: 5px 8px; border: 1px solid #ddd; }
td          { padding: 4px 8px; border: 1px solid #e0e0e0; vertical-align: top; }
"""

_PAGES = [
    ("Quick start", """
<h2>Quick start</h2>
<ol>
<li>Open files with <b>File → Open CSV…</b> (Ctrl+O) or drag-and-drop CSV files directly onto the window.</li>
<li>In the <b>Series</b> tab, pick X and Y columns from the drop-downs. Each row is one independent series.</li>
<li>Choose <b>Line</b>, <b>Scatter</b>, or <b>Histogram</b> from the Type combo, then hit <b>Plot</b>.</li>
<li>Use the <b>Appearance</b> and <b>Axes</b> tabs to adjust grid, scale, fonts, and annotations.</li>
<li>Save the figure from the <b>Export</b> tab as PNG, PDF, or SVG.</li>
</ol>
"""),

    ("Loading data", """
<h2>Loading data</h2>

<h3>Opening files</h3>
<p>Use <b>File → Open…</b> (Ctrl+O) or drag files onto the window. Supported formats:</p>
<table>
<tr><th>Format</th><th>How it's read</th></tr>
<tr><td>.csv / .txt</td><td>Delimiter auto-detected — comma, semicolon, tab, pipe, etc.</td></tr>
<tr><td>.npy</td><td>A saved NumPy array. 1D → one column named <code>value</code>; 2D → one column per array column; structured arrays use their field names.</td></tr>
<tr><td>.npz</td><td>A NumPy archive of named arrays. Each array becomes its own column, named after the array key. Mismatched lengths are padded with NaN.</td></tr>
</table>
<p>Duplicate filenames are assigned automatic suffixes: <code>file.csv (2)</code>, <code>file.csv (3)</code>, …</p>

<h3>Preview</h3>
<p>Selecting a file in the <i>Loaded files</i> list shows up to 1 000 rows in the preview table below it.</p>

<h3>Recent files</h3>
<p>The last 8 opened files appear in <b>File → Recent files</b>. Missing files are removed automatically.</p>

<h3>New columns — the formula builder</h3>
<p>Click <b>New column…</b> above the file list for a spreadsheet-style builder.
Click a column name to insert it, tap a function or operator button, and watch the
<b>live preview</b> update as you type. Example formulas:</p>
<ul>
<li><code>sqrt(x**2 + y**2)</code></li>
<li><code>exp(-time / tau)</code></li>
<li><code>sin(angle) + cos(angle)</code></li>
<li><code>pi * radius ** 2</code></li>
</ul>
<p>Available functions: <code>sin cos tan arcsin arccos arctan exp log log10
log2 sqrt abs mean floor ceil</code> and more, plus constants <code>pi</code>
and <code>e</code> (use <code>**</code> for powers). The new column appears
immediately in every picker.</p>
<p><b>Column names with spaces</b>, or names that clash with a function or a
keyword, must be wrapped in backticks — e.g. <code>`flow rate` / time</code>.
Clicking a column chip inserts the correct form automatically.</p>

<h3>DateTime axis</h3>
<p>If an X column contains datetime-typed values, the X axis automatically switches to a date locator with rotated labels.</p>
"""),

    ("Data & Series", """
<h2>Data &amp; Series</h2>

<h3>Adding series</h3>
<ul>
<li><b>+</b> — add a blank series.</li>
<li><b>Add all</b> — create one series per numeric column, all sharing the first column as X.</li>
<li><b>Duplicate</b> (copy icon) — clone the selected row including its style.</li>
</ul>

<h3>Plot types</h3>
<table>
<tr><th>Type</th><th>Description</th></tr>
<tr><td>Line</td><td>Connected line; supports error bars and rolling average</td></tr>
<tr><td>Scatter</td><td>Unconnected markers; supports error bars and color-by-column</td></tr>
<tr><td>Histogram</td><td>Frequency histogram of the Y column</td></tr>
<tr><td>Line (R)</td><td>Line on the right Y axis</td></tr>
<tr><td>Scatter (R)</td><td>Scatter on the right Y axis</td></tr>
</table>

<h3>Reordering</h3>
<p>Drag rows to change draw order and legend order.</p>

<h3>Show / hide</h3>
<p>The checkbox in the first column toggles a series without deleting it.</p>

<h3>Color swatch</h3>
<p>Click the color swatch (second column) to change a series color without opening the style dialog.</p>

<h3>Row filter</h3>
<p>Open the ⚙ style dialog and enter a pandas query in the <i>Row filter</i> field.
Only matching rows are plotted. Use <code>x</code> and <code>y</code> to refer to the plotted columns:</p>
<ul>
<li><code>y > 0</code></li>
<li><code>x >= 1.5 and y &lt; 100</code></li>
</ul>
"""),

    ("Style dialog", """
<h2>Series style dialog</h2>
<p>Click the <b>⚙</b> gear button on any series row to open its style dialog.</p>

<h3>Basic appearance</h3>
<ul>
<li><b>Legend label</b> — overrides auto-generated label; blank = auto.</li>
<li><b>Color</b>, <b>Opacity</b></li>
<li><b>Line style</b>, <b>Line width</b>, <b>Marker</b> (line series)</li>
<li><b>Point size</b>, <b>Marker</b> (scatter series)</li>
<li><b>Bins</b> (histogram series)</li>
</ul>

<h3>Error bars</h3>
<p>Check <b>Show error bars</b> and pick an error column.
Values are used as symmetric ± y error drawn as cap-style bars at 70 % opacity.</p>

<h3>Rolling average overlay</h3>
<p>Check <b>Show rolling average</b> and set a window size.
A center-aligned rolling mean is drawn as a dashed overlay on line series.</p>
<p><i>Curve fitting now has its own tab — see “Curve Fit tab”.</i></p>

<h3>Color by column</h3>
<p>For scatter series: check <b>Map color to a column</b> to map a numeric column to the viridis colormap.
Overrides the series color.</p>
"""),

    ("Plot Style tab", """
<h2>Plot Style tab</h2>

<h3>Display options</h3>
<ul>
<li><b>Show grid</b> — dashed grid lines at tick positions.</li>
<li><b>X / Y log scale</b></li>
<li><b>Reverse X / Y axis</b> — flip the axis direction (high → low)</li>
<li><b>Equal aspect ratio</b> — 1 data unit X = 1 data unit Y.</li>
<li><b>Custom W : H ratio</b> — control the plot box shape (e.g. 16 : 9).</li>
</ul>

<h3>Reference lines</h3>
<p>Add horizontal or vertical marker lines. Each line has its own color, style, width, and opacity.
Toggle visibility with the checkbox; remove with <b>−</b>.
You can also <b>drag a line directly on the plot</b> to reposition it — the value updates
automatically (and is undoable).</p>

<h3>Fill bands</h3>
<p>Shade a region between two axis values. Useful for tolerance bands or highlighted time ranges.
Each band has its own color, opacity, and optional legend label.</p>
"""),

    ("Axes & Labels tab", """
<h2>Axes & Labels tab</h2>

<h3>Labels</h3>
<ul>
<li><b>Title</b> — blank = auto (filename); <code>#none</code> = suppress.</li>
<li><b>X / Y label</b> — blank = auto (column name); <code>#none</code> = suppress.</li>
</ul>

<h3>Limits</h3>
<p>Enter min/max values for X and Y. Leave blank for automatic bounds.</p>

<h3>Tick labels</h3>
<ul>
<li><b>Label size</b> — 6 – 24 pt, per axis.</li>
<li><b>Tick count</b> — hint for the number of major ticks (2 – 30).</li>
</ul>

<h3>Figure font</h3>
<p>Pick any system font from the drop-down. The plot re-renders immediately.</p>

<h3>Legend</h3>
<ul>
<li>Show / hide, frame border, position.</li>
<li>Or just <b>drag the legend</b> anywhere on the plot to place it by hand; pick a named
position from the dropdown again to snap it back.</li>
</ul>

<h3>Text annotations</h3>
<p>Place text anywhere on the plot using <b>axes coordinates</b> (0–1 relative to the plot area)
or <b>data coordinates</b> (actual X/Y values). Each annotation has its own font size, weight, color, rotation, and alignment.</p>
<p>Once on the plot, just <b>drag an annotation with the mouse</b> to move it where you want —
the position is saved automatically (and is undoable). The cursor turns into a hand when you
hover over anything you can drag.</p>

<h3>Shapes &amp; images</h3>
<p>Add a <b>rectangle, rounded rectangle, circle/ellipse, triangle, pentagon, hexagon,</b>
or <b>star</b> from the shape menu — or an <b>imported image</b> — as a free-floating overlay.
A new shape appears as its regular (equal-sided) form. Click one to select it, then:</p>
<ul>
<li><b>Drag the body</b> to move it, or <b>drag a square handle</b> to resize.</li>
<li>Hold <b>Ctrl</b> while dragging a corner handle to <b>lock the aspect ratio</b>.</li>
<li>Grab the round <b>grip above the shape to rotate</b> it; hold <b>Ctrl</b> to snap to 15°.</li>
<li>Press <b>Delete</b> (or the <b>−</b> button) to remove the selected shape.</li>
<li>The <b>⚙</b> sets each shape's line colour, fill, width, opacity, and exact angle.</li>
</ul>
"""),

    ("Curve Fit tab", """
<h2>Curve Fit tab</h2>
<p>Fit <b>any function</b> to your data — not just polynomials.</p>
<ol>
<li>Click <b>+</b> to add a fit, then pick the <b>X</b> and <b>Y</b> columns.</li>
<li>Click the <b>⚙</b> to open the fit editor — the same builder as
<b>New column</b>, with chips for <b>x</b> and your columns, the
function/operator palette, and a live list of detected parameters. Type a
model in <b>x</b> with free parameters (any letters), e.g.
<code>a * exp(-b * x) + c</code>.</li>
<li><b>Other columns</b> can appear in the model too — they are used as fixed
data, not fitted. e.g. <code>a * x + b - offset</code> fits <code>a</code> and
<code>b</code> using the <code>offset</code> column.</li>
<li>Press <b>Run fit</b> to see each parameter's value ± 1σ, the <b>R²</b>,
and the fitted equation.</li>
<li>Tick <b>Overlay</b> to draw the fitted curve (with its equation in the
legend). Add optional <b>initial guesses</b> to help tricky fits converge.</li>
</ol>
<p>Example models:</p>
<ul>
<li><code>a * x + b</code> — line</li>
<li><code>a * x**2 + b * x + c</code> — parabola</li>
<li><code>a * exp(-b * x) + c</code> — exponential decay</li>
<li><code>a * sin(b * x + c)</code> — sinusoid</li>
<li><code>a / (1 + exp(-b * (x - c)))</code> — logistic</li>
</ul>
<p>Fitting uses <code>scipy.optimize.curve_fit</code>.</p>
"""),

    ("Compare Series tab", """
<h2>Compare Series tab</h2>
<p>Hidden by default — enable via the <b>⚙</b> corner button on the tab bar.</p>
<p>Measure how closely two numeric columns agree. Click <b>+</b> to add a
comparison row, then pick a <b>Reference</b> and a <b>Compare</b> column (from any
files, same row count). Add as many comparison rows as you need.</p>

<table>
<tr><th>Metric</th><th>Meaning</th></tr>
<tr><td>RMSD</td><td>Root-mean-square deviation — typical error size, in data units</td></tr>
<tr><td>MAE</td><td>Mean absolute error — average size of the differences</td></tr>
<tr><td>MSE</td><td>Mean squared error — penalises large errors more</td></tr>
</table>

<p>The table shows RMSD at a glance. Click the <b>⚙</b> on a row to open the
details: every metric with its value, an <b>On plot</b> tick to stamp it onto the
figure as a label, and a <b>Style…</b> button for position, font, color, decimals,
and units. Once a metric is on the plot you can also <b>drag its label</b> straight
to where you want it.</p>
"""),

    ("Export", """
<h2>Export</h2>

<h3>Save image</h3>
<ul>
<li><b>PNG</b> — raster; resolution set by DPI (72 – 600).</li>
<li><b>PDF</b> — vector; DPI ignored for image content.</li>
<li><b>SVG</b> — vector; editable in Inkscape or Illustrator.</li>
</ul>
<p>Check <b>Transparent background</b> to omit the white fill — useful for slides.</p>
<p>All export settings persist between sessions.</p>

<h3>Copy to clipboard</h3>
<p>Press <b>Ctrl+Shift+C</b> or click the clipboard button in the toolbar to copy the current
plot as a 300 dpi PNG to the system clipboard.</p>
"""),

    ("Templates & shortcuts", """
<h2>Plot templates</h2>
<p><b>File → Save template…</b> saves all axis and style settings to a JSON file
(labels, limits, scale, font, legend, grid, tick sizes, aspect ratio).</p>
<p><b>File → Load template…</b> applies a saved template in one click.</p>

<h2>Undo / Redo</h2>
<p>Ctrl+Z / Ctrl+Y — 20-level history for series, reference lines, fill bands, and annotations.</p>

<h2>Keyboard shortcuts</h2>
<table>
<tr><th>Action</th><th>Shortcut</th></tr>
<tr><td>Open CSV</td><td>Ctrl+O</td></tr>
<tr><td>Copy plot to clipboard</td><td>Ctrl+Shift+C</td></tr>
<tr><td>Undo</td><td>Ctrl+Z</td></tr>
<tr><td>Redo</td><td>Ctrl+Y</td></tr>
<tr><td>Quit</td><td>Ctrl+Q</td></tr>
</table>
"""),
]


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alekhyam — User guide")
        self.resize(820, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # Left: topic list
        self._topicList = QListWidget()
        self._topicList.setFixedWidth(155)
        self._topicList.setFrameShape(self._topicList.frameShape().NoFrame)
        for title, _ in _PAGES:
            item = QListWidgetItem(title)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._topicList.addItem(item)
        self._topicList.currentRowChanged.connect(self._onTopicChanged)
        splitter.addWidget(self._topicList)

        # Right: content browser
        self._browser = QTextBrowser()
        self._browser.setFrameShape(self._browser.frameShape().NoFrame)
        self._browser.setOpenExternalLinks(True)
        splitter.addWidget(self._browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)

        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.setContentsMargins(12, 0, 12, 0)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._topicList.setCurrentRow(0)

    def _onTopicChanged(self, row):
        if 0 <= row < len(_PAGES):
            _, html = _PAGES[row]
            self._browser.setHtml(f"<style>{_STYLE}</style>{html}")
