import sys


def _reportImportError(exc):
    msg = str(exc)
    lines = [
        "Alekhyam failed to start because PySide6 could not be loaded:",
        f"  {msg}",
        "",
    ]
    if "DLL load failed" in msg:
        lines += [
            "This is almost always a Qt DLL conflict inside a Conda/Anaconda",
            "environment — the base env often ships its own Qt5 (via 'pyqt',",
            "'qt', or a dependency like Jupyter/Spyder), which collides with",
            "PySide6's bundled Qt6 DLLs.",
            "",
            "Fix: install Alekhyam in a fresh, isolated environment rather than",
            "Anaconda's base environment:",
            "",
            "    conda create -n alekhyam python=3.11",
            "    conda activate alekhyam",
            "    pip install alekhyam",
            "    alekhyam",
            "",
            "If you must use an existing environment, remove the conflicting",
            "Qt packages first, then reinstall PySide6:",
            "",
            "    conda remove pyqt qt qt-main --force",
            "    pip install --force-reinstall pyside6",
        ]
    else:
        lines.append(
            "Try reinstalling: pip install --force-reinstall alekhyam"
        )
    print("\n".join(lines), file=sys.stderr)


def _darkPalette():
    """A cohesive dark palette so the app looks right regardless of platform."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette

    p = QPalette()
    p.setColor(QPalette.Window,          QColor(0x2b, 0x2b, 0x30))
    p.setColor(QPalette.WindowText,      QColor(0xe7, 0xe7, 0xec))
    p.setColor(QPalette.Base,            QColor(0x23, 0x23, 0x28))
    p.setColor(QPalette.AlternateBase,   QColor(0x30, 0x30, 0x36))
    p.setColor(QPalette.Text,            QColor(0xe7, 0xe7, 0xec))
    p.setColor(QPalette.PlaceholderText, QColor(0x9a, 0x9a, 0xa4))
    p.setColor(QPalette.Button,          QColor(0x34, 0x34, 0x3b))
    p.setColor(QPalette.ButtonText,      QColor(0xe7, 0xe7, 0xec))
    p.setColor(QPalette.BrightText,      QColor(0xff, 0x6b, 0x6b))
    p.setColor(QPalette.ToolTipBase,     QColor(0x2b, 0x2b, 0x30))
    p.setColor(QPalette.ToolTipText,     QColor(0xe7, 0xe7, 0xec))
    p.setColor(QPalette.Mid,             QColor(0x53, 0x53, 0x5d))
    p.setColor(QPalette.Midlight,        QColor(0x3c, 0x3c, 0x44))
    p.setColor(QPalette.Dark,            QColor(0x6b, 0x6b, 0x77))
    p.setColor(QPalette.Light,           QColor(0x42, 0x42, 0x4a))
    p.setColor(QPalette.Shadow,          QColor(0x14, 0x14, 0x18))
    p.setColor(QPalette.Highlight,       QColor(0x2e, 0x73, 0xb8))
    p.setColor(QPalette.HighlightedText, Qt.white)
    p.setColor(QPalette.Link,            QColor(0x5a, 0x9d, 0xd8))
    disabled = QColor(0x77, 0x77, 0x80)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, disabled)
    return p


def _applyTheme(app):
    """Force Fusion (styles our QSS uniformly on all platforms) and pick a
    light or dark palette from the OS colour scheme."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette

    dark = False
    hints = app.styleHints()
    if hasattr(hints, "colorScheme"):
        try:
            dark = hints.colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            dark = False
    else:
        dark = app.palette().color(QPalette.Window).lightness() < 128

    app.setStyle("Fusion")
    if dark:
        app.setPalette(_darkPalette())


def main():
    try:
        from PySide6.QtGui import QFont, QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        _reportImportError(exc)
        sys.exit(1)

    from .appResources import iconPath
    from .desktopEntry import installDesktopEntry
    from .mainWindow import MainWindow

    # Windows: tell the shell this process belongs to our own AppUserModelID so
    # pinned taskbar buttons group correctly and show our icon, not the generic
    # python.exe one.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "alekhyam.alekhyam"
            )
        except Exception:
            pass

    installDesktopEntry()
    app = QApplication(sys.argv)
    app.setApplicationName("Alekhyam")
    app.setOrganizationName("alekhyam")

    # Consistent styling + a proper light/dark theme on every platform.
    _applyTheme(app)

    # A modern system UI font (falls through to whatever the OS provides).
    uiFont = QFont()
    uiFont.setFamilies(["Segoe UI", "SF Pro Text", "Inter", "Ubuntu",
                        "Noto Sans", "Cantarell", "DejaVu Sans"])
    uiFont.setPointSize(11)
    app.setFont(uiFont)
    # Linux: match the .desktop file name so the WM groups windows correctly
    # and clicking the launcher focuses the existing window instead of
    # launching a second instance.
    app.setDesktopFileName("alekhyam")

    icon = QIcon()
    icon.addFile(str(iconPath()))
    app.setWindowIcon(icon)

    window = MainWindow(icon)

    def _reveal():
        window.showMaximized()
        window.raise_()
        window.activateWindow()

    from .splash import SplashScreen
    splash = SplashScreen(on_done=_reveal)
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
