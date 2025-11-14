import os
import sys


class DisplayNotAvailableError(RuntimeError):
    """Raised when the application needs a GUI but no display server is available."""


def has_display() -> bool:
    """
    Check whether a graphical display is available.

    On Windows and macOS we optimistically assume a display exists. On Unix-like systems,
    we verify that either DISPLAY or WAYLAND_DISPLAY is set.
    """
    if sys.platform.startswith(("win32", "cygwin")):
        return True

    if sys.platform == "darwin":
        return True

    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def ensure_display() -> None:
    """
    Ensure the current environment can start a GUI.

    Raises:
        DisplayNotAvailableError: If no display server is detected.
    """
    if not has_display():
        raise DisplayNotAvailableError(
            "No display server detected. PySimpleGUI requires an X11/Wayland display "
            "to start. Run the app on a desktop environment or forward a DISPLAY."
        )
