from typing import Any, Dict, TYPE_CHECKING

from loguru import logger

from src.utils.display import DisplayNotAvailableError, ensure_display

if TYPE_CHECKING:
    import PySimpleGUI as sg


def main() -> None:
    """
    Main function. Initialize the window and handle the events.
    """
    try:
        ensure_display()
    except DisplayNotAvailableError as exc:
        logger.error(exc)
        logger.info(
            "If you're running headless (e.g. in a container or CI), forward an X11 "
            "display or use a virtual display such as Xvfb before launching the GUI."
        )
        return

    import PySimpleGUI as sg
    from src.gui import initialize_window
    from src.handlers import (
        handle_events,
        initialize_auto_listening,
        shutdown_listener,
    )

    window: "sg.Window" = initialize_window()
    logger.debug("Application started.")
    initialize_auto_listening(window)

    while True:
        event: str
        values: Dict[str, Any]
        event, values = window.read()

        if event in ["-CLOSE_BUTTON-", sg.WIN_CLOSED]:
            logger.debug("Closing...")
            shutdown_listener(window)
            break

        handle_events(window, event, values)

    shutdown_listener(window)
    window.close()


if __name__ == "__main__":
    main()
