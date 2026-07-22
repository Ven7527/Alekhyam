import shutil
import subprocess
import sys
from pathlib import Path

from .appResources import resourceDir

appId = "alekhyam"


def _resolveExecCommand():
    # Prefer the installed console-script (put on PATH by pip) so the menu
    # entry keeps working even if this venv/conda env isn't the active shell.
    resolved = shutil.which("alekhyam")
    if resolved:
        return resolved
    return f"{sys.executable} -m alekhyam.app"


def installDesktopEntry(verbose=False):
    """Best-effort: register Alekhyam in the OS application menu/shortcuts.
    Never raises — menu integration is a nicety, not a launch requirement."""
    try:
        if sys.platform.startswith("linux"):
            _installLinuxDesktopEntry()
            if verbose:
                print("Alekhyam registered in the application menu.")
        elif sys.platform.startswith("win"):
            _installWindowsShortcut()
            if verbose:
                print("Alekhyam shortcut added to Start Menu.")
        else:
            if verbose:
                print(f"App menu registration is not supported on {sys.platform}.")
    except Exception as exc:
        if verbose:
            print(f"Registration failed: {exc}")


def main():
    """Entry point for the `alekhyam-register` console script."""
    installDesktopEntry(verbose=True)


def _installLinuxDesktopEntry():
    applicationsDir = Path.home() / ".local" / "share" / "applications"
    applicationsDir.mkdir(parents=True, exist_ok=True)

    # PNG rather than SVG: some desktop environments lack an SVG pixbuf
    # loader and silently fall back to a blank/generic icon otherwise.
    iconPath = resourceDir() / "alekhyam.png"
    execCommand = _resolveExecCommand()

    desktopContent = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Alekhyam\n"
        "Comment=Lightweight multi-CSV line/scatter plotter\n"
        f"Exec={execCommand}\n"
        f"Icon={iconPath}\n"
        "Terminal=false\n"
        "Categories=Science;Education;Utility;\n"
    )

    desktopFile = applicationsDir / f"{appId}.desktop"
    if not desktopFile.exists() or desktopFile.read_text() != desktopContent:
        desktopFile.write_text(desktopContent)
        desktopFile.chmod(0o755)

    updateCommand = shutil.which("update-desktop-database")
    if updateCommand:
        subprocess.run(
            [updateCommand, str(applicationsDir)],
            check=False, capture_output=True,
        )


def _installWindowsShortcut():
    # Optional: only runs if pywin32 + winshell are installed (Windows-only
    # deps in pyproject.toml). Without them, Windows users can pin alekhyam.exe
    # (in their Python Scripts folder) to the taskbar manually.
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        return

    startMenu = Path(winshell.start_menu())
    shortcutPath = startMenu / f"{appId.capitalize()}.lnk"
    execCommand = shutil.which("alekhyam") or sys.executable
    iconLocation = str(resourceDir() / "alekhyam.ico")

    if shortcutPath.exists():
        shell = Dispatch("WScript.Shell")
        existing = shell.CreateShortCut(str(shortcutPath))
        if existing.Targetpath == execCommand and existing.IconLocation == iconLocation:
            return  # already up to date

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcutPath))
    shortcut.Targetpath = execCommand
    shortcut.IconLocation = iconLocation
    shortcut.WorkingDirectory = str(Path(execCommand).parent)
    shortcut.save()
