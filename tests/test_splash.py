"""Tests for the opening splash — state machine and hand-off."""
import pytest


@pytest.fixture
def splash(qapp):
    from alekhyam.splash import SplashScreen
    calls = []
    s = SplashScreen(on_done=lambda: calls.append(1))
    s._calls = calls
    yield s
    s._timer.stop()
    s.deleteLater()


def test_scene_svg_loads(splash):
    # The bundled splash illustration must be a valid SVG.
    assert splash._scene.isValid()


def test_skip_before_begin_stays_skipped(splash):
    # A click can land before the deferred _begin() singleShot fires.
    # _begin() must not yank the state machine back to the start.
    splash.mousePressEvent(None)
    assert splash._phase == "fade"
    splash._begin()
    assert splash._phase == "fade"


def test_begin_starts_in_from_idle(splash):
    assert splash._phase == "idle"
    splash._begin()
    assert splash._phase == "in"
    assert splash._timer.isActive()


def test_key_press_skips(splash):
    splash._begin()
    splash.keyPressEvent(None)
    assert splash._phase == "fade"
    assert splash._reveal == 1.0


def test_finish_calls_on_done_exactly_once(splash):
    splash._finish()
    splash._finish()
    assert splash._calls == [1]
    assert not splash._timer.isActive()


def test_close_event_hands_off_to_app(splash):
    # If the window manager closes the splash, the main window must
    # still be shown — on_done may never be silently dropped.
    splash.close()
    assert splash._calls == [1]
