import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget

from .appResources import resourceDir

# ── Timing (seconds) ──────────────────────────────────────────────────────────
_IN_SECS    = 0.40   # card eases in
_PAINT_SECS = 0.95   # illustration is "painted" left → right
_TITLE_SECS = 0.85   # ALEKHYAM types out, letter by letter
_HOLD_SECS  = 1.10
_FADE_SECS  = 0.45
_FPS        = 60

# ── Palette ───────────────────────────────────────────────────────────────────
_MILKY  = QColor(0xec, 0xe3, 0xd1)   # milky brown-white card
_BORDER = QColor(0xd6, 0xc9, 0xac)
_INK    = QColor(0x2b, 0x2b, 0x2b)   # wordmark
_SHADOW = QColor(0x3a, 0x33, 0x24)

# ── Illustration content box inside the SVG's 1107×694 viewBox ────────────────
# (measured tight bounds, so the art fills the card edge-to-edge with no margin)
_SVG_W, _SVG_H = 1107.0, 694.0
_BX, _BY, _BW, _BH = 17.0, 30.0, 1030.0, 647.0
_ART_ASPECT = _BW / _BH

# ── Card design space (scaled to the screen at paint time) ────────────────────
_CARD_W  = 560.0
_PAD     = 34.0
_GAP     = 16.0


def _ease_out(t):
    return 1.0 - (1.0 - t) * (1.0 - t)


class SplashScreen(QWidget):
    """
    Fullscreen (translucent) splash showing a small centred card.

      In    — the card eases and fades in.
      Paint — the painting-python illustration is revealed left→right, as if
              being painted onto the canvas.
      Title — the ALEKHYAM wordmark fades in.
      Hold  — brief pause, then the whole card fades out and hands off.

    Click anywhere to skip.
    """

    def __init__(self, on_done):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._on_done   = on_done
        self._done      = False
        self._cardIn    = 0.0     # 0 → 1 card ease-in
        self._reveal    = 0.0     # 0 → 1 paint wipe
        self._titleAlpha = 0.0
        self._phase     = "idle"

        self._scene = QSvgRenderer(str(resourceDir() / "splash.svg"))

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(1.0)

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // _FPS)
        self._timer.timeout.connect(self._tick)
        QTimer.singleShot(100, self._begin)

    # ── State machine ─────────────────────────────────────────────────────────

    def _begin(self):
        # A click may have skipped ahead before this deferred start fired;
        # never yank the state machine back to the beginning.
        if self._phase != "idle":
            return
        self._t0    = time.monotonic()
        self._phase = "in"
        self._timer.start()

    def _finish(self):
        """Hand off to the app exactly once, whatever path got us here."""
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._on_done()
        self.deleteLater()

    def _tick(self):
        now = time.monotonic()
        if self._phase == "in":
            self._cardIn = min((now - self._t0) / _IN_SECS, 1.0)
            if self._cardIn >= 1.0:
                self._phase   = "paint"
                self._t_paint = now
        elif self._phase == "paint":
            self._reveal = min((now - self._t_paint) / _PAINT_SECS, 1.0)
            if self._reveal >= 1.0:
                self._phase   = "title"
                self._t_title = now
        elif self._phase == "title":
            self._titleAlpha = min((now - self._t_title) / _TITLE_SECS, 1.0)
            if self._titleAlpha >= 1.0:
                self._phase  = "hold"
                self._t_hold = now
        elif self._phase == "hold":
            if now - self._t_hold >= _HOLD_SECS:
                self._phase  = "fade"
                self._t_fade = now
        elif self._phase == "fade":
            alpha = max(0.0, 1.0 - (now - self._t_fade) / _FADE_SECS)
            self._effect.setOpacity(alpha)
            if alpha <= 0.0:
                self._finish()
                return
        self.update()

    def _skip(self):
        self._cardIn = self._reveal = self._titleAlpha = 1.0
        if self._phase != "fade":
            self._phase  = "fade"
            self._t_fade = time.monotonic()
        if not self._timer.isActive():
            self._timer.start()

    def mousePressEvent(self, event):
        self._skip()

    def keyPressEvent(self, event):
        self._skip()

    def closeEvent(self, event):
        # If the window manager closes the splash, still show the app.
        self._finish()
        event.accept()

    # ── Illustration (crop the SVG's tight content box into `rect`) ───────────

    def _renderArt(self, p, rect):
        if not self._scene.isValid():
            return
        sx = rect.width() / _BW
        sy = rect.height() / _BH
        full = QRectF(rect.x() - _BX * sx, rect.y() - _BY * sy,
                      _SVG_W * sx, _SVG_H * sy)
        self._scene.render(p, full)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self._phase == "idle":
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()

        # ── Card geometry (scaled to screen) ──────────────────────────────
        card_w = min(_CARD_W, w * 0.42)
        sc     = card_w / _CARD_W
        pad    = _PAD * sc
        gap    = _GAP * sc

        # Monospace "typewriter" wordmark
        wf = QFont()
        wf.setFamilies(["Courier New", "Courier 10 Pitch", "Liberation Mono",
                        "DejaVu Sans Mono", "Consolas", "monospace"])
        wf.setStyleHint(QFont.TypeWriter)
        wf.setPixelSize(max(12, int(40 * sc)))
        wf.setWeight(QFont.Bold)
        fm_w = QFontMetrics(wf)

        art_w  = card_w - 2 * pad
        art_h  = art_w / _ART_ASPECT
        card_h = pad + art_h + gap + fm_w.height() + pad

        cx = (w - card_w) / 2.0
        cy = (h - card_h) / 2.0

        # ── Ease/scale the whole card in ──────────────────────────────────
        e = _ease_out(self._cardIn)
        p.setOpacity(e)
        scale = 0.93 + 0.07 * e
        p.translate(cx + card_w / 2, cy + card_h / 2)
        p.scale(scale, scale)
        p.translate(-(cx + card_w / 2), -(cy + card_h / 2))

        card = QRectF(cx, cy, card_w, card_h)
        rr   = 26 * sc

        # Soft drop shadow (stacked translucent rounded rects)
        p.setPen(Qt.NoPen)
        for i in range(10, 0, -1):
            off = i * 1.6 * sc
            p.setBrush(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 5))
            p.drawRoundedRect(card.adjusted(-off, -off + 4 * sc, off, off + 4 * sc),
                              rr + off, rr + off)

        # Card
        p.setBrush(_MILKY)
        p.setPen(QPen(_BORDER, 1.5 * sc))
        p.drawRoundedRect(card, rr, rr)

        # ── Illustration, revealed left → right ───────────────────────────
        art_rect = QRectF(cx + pad, cy + pad, art_w, art_h)
        wipe = _ease_out(self._reveal)
        p.save()
        clip = QRectF(art_rect.x(), art_rect.y(), art_rect.width() * wipe, art_rect.height())
        p.setClipRect(clip)
        self._renderArt(p, art_rect)
        p.restore()

        # ── Typewriter wordmark ───────────────────────────────────────────
        # Letters appear one at a time; a block cursor sits at the caret and
        # blinks once the word is complete. The full width is reserved so the
        # text grows rightward without shifting.
        if self._phase in ("title", "hold", "fade"):
            full   = "ALEKHYAM"
            n      = int(round(self._titleAlpha * len(full)))
            typed  = full[:n]
            typing = n < len(full)

            char_w = fm_w.horizontalAdvance("A")           # monospace cell
            full_w = fm_w.horizontalAdvance(full)
            base_x = cx + (card_w - (full_w + char_w)) / 2
            baseline = cy + pad + art_h + gap + fm_w.ascent()

            p.setFont(wf)
            p.setPen(_INK)
            p.drawText(int(base_x), int(baseline), typed)

            # Cursor: solid while typing, blinking after.
            cursor_on = True if typing else (time.monotonic() % 0.9) < 0.5
            if cursor_on:
                cap = fm_w.capHeight() or fm_w.ascent() * 0.7
                cx0 = base_x + fm_w.horizontalAdvance(typed) + char_w * 0.08
                p.setBrush(_INK)
                p.setPen(Qt.NoPen)
                p.drawRect(QRectF(cx0, baseline - cap, char_w * 0.72, cap))
