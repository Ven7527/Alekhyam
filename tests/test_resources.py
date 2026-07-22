"""Tests for appResources — icon path resolution."""
from pathlib import Path

from alekhyam.appResources import iconPath, resourceDir


def test_resource_dir_exists():
    assert resourceDir().is_dir()


def test_resource_dir_contains_icons():
    d = resourceDir()
    assert (d / "alekhyam.png").exists()
    assert (d / "alekhyam.svg").exists()
    assert (d / "alekhyam.ico").exists()


def test_icon_path_returns_existing_file():
    assert iconPath().exists()


def test_icon_path_is_absolute():
    assert iconPath().is_absolute()


def test_icon_path_prefers_png_on_linux(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    import importlib
    import alekhyam.appResources as ar
    importlib.reload(ar)
    path = ar.iconPath()
    assert path.suffix in (".png", ".svg")


def test_icon_path_prefers_ico_on_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    import importlib
    import alekhyam.appResources as ar
    importlib.reload(ar)
    path = ar.iconPath()
    assert path.suffix == ".ico"
