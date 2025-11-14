from pathlib import Path
from typing import Any, Dict, List, Optional

import PySimpleGUI as sg
from loguru import logger

from src import audio, gpt_query
from src.button import OFF_IMAGE, ON_IMAGE
from src.config import OUTPUT_FILE_NAME


def _window_metadata(window: sg.Window) -> Dict[str, Any]:
    """
    Ensure the window has a metadata dictionary we can mutate.
    """
    if window.metadata is None or not isinstance(window.metadata, dict):
        window.metadata = {}
    return window.metadata


CONTEXT_TEXT_INPUT_KEYS = {
    "-POSITION_INPUT-",
    "-JOB_DESC_INPUT-",
    "-COMPANY_INFO_INPUT-",
    "-ABOUT_YOU_INPUT-",
    "-RESUME_INPUT-",
}

LOAD_BUTTON_TARGETS: Dict[str, str] = {
    "-LOAD_JOB_DESC-": "-JOB_DESC_INPUT-",
    "-LOAD_COMPANY_INFO-": "-COMPANY_INFO_INPUT-",
    "-LOAD_ABOUT_YOU-": "-ABOUT_YOU_INPUT-",
    "-LOAD_RESUME-": "-RESUME_INPUT-",
}

CONTEXT_FIELD_LABELS: Dict[str, str] = {
    "-JOB_DESC_INPUT-": "Job Description",
    "-COMPANY_INFO_INPUT-": "About the Company",
    "-ABOUT_YOU_INPUT-": "About You",
    "-RESUME_INPUT-": "Resume Highlights",
}

AUTO_SEGMENT_EVENT = "-AUTO_SEGMENT-"


def _should_block_hotkeys(focused_key: Optional[str]) -> bool:
    return focused_key in CONTEXT_TEXT_INPUT_KEYS if focused_key else False


def _focused_element(window: sg.Window) -> Optional[sg.Element]:
    try:
        return window.find_element_with_focus()
    except Exception as error:
        logger.debug(f"Could not determine focused element: {error}")
        return None


def toggle_context_panel(window: sg.Window) -> None:
    metadata: Dict[str, Any] = _window_metadata(window)
    new_state: bool = not metadata.get("context_panel_open", True)
    metadata["context_panel_open"] = new_state
    window["-CONTEXT_PANEL-"].update(visible=new_state)
    button_text: str = "Show Context Panel" if not new_state else "Hide Context Panel"
    window["-TOGGLE_CONTEXT_PANEL-"].update(button_text)


def load_context_from_file(window: sg.Window, target_key: str) -> None:
    file_path: Optional[str] = sg.popup_get_file(
        "Select a text file", keep_on_top=True, no_window=True
    )
    if not file_path:
        return

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except Exception as error:
        sg.popup_error(
            f"Unable to load file:\n{error}",
            title="File Error",
        )
        return

    window[target_key].update(text)


def build_context_payload(values: Dict[str, Any]) -> str:
    sections: List[str] = []
    position_value: Optional[str] = values.get("-POSITION_INPUT-")
    if position_value and position_value.strip():
        sections.append(f"Target Position: {position_value.strip()}")

    for key, label in CONTEXT_FIELD_LABELS.items():
        data = values.get(key)
        if data and data.strip():
            sections.append(f"{label}:\n{data.strip()}")

    return "\n\n".join(sections).strip()


def _get_listener(window: sg.Window) -> audio.ContinuousRecorder:
    metadata: Dict[str, Any] = _window_metadata(window)
    listener: Optional[audio.ContinuousRecorder] = metadata.get("listener")
    if listener is None:
        listener = audio.ContinuousRecorder(
            segment_callback=lambda path: window.write_event_value(AUTO_SEGMENT_EVENT, path)
        )
        metadata["listener"] = listener
    return listener


def initialize_auto_listening(window: sg.Window) -> None:
    metadata: Dict[str, Any] = _window_metadata(window)
    if metadata.get("auto_initialized"):
        return
    metadata["auto_initialized"] = True
    button: sg.Element = window["-RECORD_BUTTON-"]
    if not getattr(button.metadata, "state", False):
        recording_event(window)


def shutdown_listener(window: sg.Window) -> None:
    metadata: Dict[str, Any] = _window_metadata(window)
    listener: Optional[audio.ContinuousRecorder] = metadata.get("listener")
    if listener:
        listener.stop()
    metadata["listener"] = None


def _enqueue_transcription(window: sg.Window, audio_path: str) -> None:
    metadata: Dict[str, Any] = _window_metadata(window)
    queue: List[str] = metadata.setdefault("transcription_queue", [])
    queue.append(audio_path)
    metadata["last_recording_path"] = audio_path
    _process_transcription_queue(window)


def _process_transcription_queue(window: sg.Window) -> None:
    metadata: Dict[str, Any] = _window_metadata(window)
    if metadata.get("transcription_in_progress"):
        return

    queue: List[str] = metadata.get("transcription_queue", [])
    if not queue:
        return

    next_path: str = queue.pop(0)
    metadata["current_audio_path"] = next_path
    metadata["transcription_in_progress"] = True
    _start_transcription(window, next_path)


def _start_transcription(window: sg.Window, audio_path: str) -> None:
    window["-TRANSCRIBED_TEXT-"].update("Transcribing audio...")
    window.perform_long_operation(
        lambda path=audio_path: gpt_query.transcribe_audio(path),
        "-WHISPER-",
    )


def _mark_transcription_complete(window: sg.Window) -> None:
    metadata: Dict[str, Any] = _window_metadata(window)
    metadata["transcription_in_progress"] = False
    _process_transcription_queue(window)


def handle_events(window: sg.Window, event: str, values: Dict[str, Any]) -> None:
    """
    Handle the events. Record audio, transcribe audio, generate quick and full answers.

    Args:
        window (sg.Window): The window element.
        event (str): The event.
        values (Dict[str, Any]): The values of the window.
    """
    if event is None:
        return

    if event == "-TOGGLE_CONTEXT_PANEL-":
        toggle_context_panel(window)
        return

    if event in LOAD_BUTTON_TARGETS:
        load_context_from_file(window, LOAD_BUTTON_TARGETS[event])
        return

    if event == AUTO_SEGMENT_EVENT:
        audio_path: Optional[str] = values.get(AUTO_SEGMENT_EVENT)
        if audio_path:
            _enqueue_transcription(window, audio_path)
        return

    focused_element: Optional[sg.Element] = _focused_element(window)
    focused_key: Optional[str] = getattr(focused_element, "Key", None)
    hotkeys_allowed: bool = not _should_block_hotkeys(focused_key)

    if event in ("-RECORD_BUTTON-",):
        recording_event(window)
    elif event in ("-ANALYZE_BUTTON-",):
        transcribe_event(window)
    elif hotkeys_allowed and event in ("r", "R"):
        recording_event(window)
    elif hotkeys_allowed and event in ("a", "A"):
        transcribe_event(window)

    # If the user is focused on the position input allow Enter/Esc to trigger analyze focus
    if (
        focused_key == "-POSITION_INPUT-"
        and isinstance(event, str)
        and event[:6] in ("Return", "Escape")
    ):
        window["-ANALYZE_BUTTON-"].set_focus()

    # When the transcription is ready
    elif event == "-WHISPER-":
        _mark_transcription_complete(window)
        answer_events(window, values)
        return

    # When the quick answer is ready
    elif event == "-QUICK_ANSWER-":
        logger.debug("Quick answer generated.")
        print("Quick answer:", values["-QUICK_ANSWER-"])
        window["-QUICK_ANSWER-"].update(values["-QUICK_ANSWER-"])

    # When the full answer is ready
    elif event == "-FULL_ANSWER-":
        logger.debug("Full answer generated.")
        print("Full answer:", values["-FULL_ANSWER-"])
        window["-FULL_ANSWER-"].update(values["-FULL_ANSWER-"])


def recording_event(window: sg.Window) -> None:
    """
    Toggle the continuous listening state.

    Args:
        window (sg.Window): The window element.
    """
    button: sg.Element = window["-RECORD_BUTTON-"]
    button.metadata.state = not button.metadata.state
    button.update(image_data=ON_IMAGE if button.metadata.state else OFF_IMAGE)

    if button.metadata.state:
        listener: audio.ContinuousRecorder = _get_listener(window)
        window["-TRANSCRIBED_TEXT-"].update("Listening for speech...")
        try:
            listener.start()
        except Exception:
            button.metadata.state = False
            button.update(image_data=OFF_IMAGE)
            window["-TRANSCRIBED_TEXT-"].update(
                "Unable to start microphone. Check audio input settings."
            )
    else:
        shutdown_listener(window)
        window["-TRANSCRIBED_TEXT-"].update("Listening paused.")


def transcribe_event(window: sg.Window) -> None:
    """
    Manually trigger transcription for the last captured audio segment.

    Args:
        window (sg.Window): The window element.
    """
    metadata: Dict[str, Any] = _window_metadata(window)
    recorded_path: Any = metadata.get("last_recording_path")
    if not recorded_path:
        fallback = Path(OUTPUT_FILE_NAME)
        if fallback.is_file():
            recorded_path = str(fallback.resolve())

    if not recorded_path or not Path(recorded_path).is_file():
        window["-TRANSCRIBED_TEXT-"].update(
            "No captured audio yet. Speak while the listener is active."
        )
        return

    _enqueue_transcription(window, recorded_path)
    window["-TRANSCRIBED_TEXT-"].update("Queued last audio snippet for processing...")


def answer_events(window: sg.Window, values: Dict[str, Any]) -> None:
    """
    Handle the answer events. Generate quick and full answers and update the text areas.

    Args:
        window (sg.Window): The window element.
        values (Dict[str, Any]): The values of the window.
    """
    transcribed_text: sg.Element = window["-TRANSCRIBED_TEXT-"]
    quick_answer: sg.Element = window["-QUICK_ANSWER-"]
    full_answer: sg.Element = window["-FULL_ANSWER-"]

    # Get audio transcript and update text area
    audio_transcript: str = values["-WHISPER-"]
    transcribed_text.update(audio_transcript)

    # Get model and position
    model: str = values["-MODEL_COMBO-"]
    position: str = values["-POSITION_INPUT-"]

    context_payload: str = build_context_payload(values)

    # Generate quick answer
    logger.debug("Generating quick answer...")
    quick_answer.update("Generating quick answer...")
    window.perform_long_operation(
        lambda: gpt_query.generate_answer(
            audio_transcript,
            short_answer=True,
            temperature=0,
            model=model,
            position=position,
            context=context_payload,
        ),
        "-QUICK_ANSWER-",
    )

    # Generate full answer
    logger.debug("Generating full answer...")
    full_answer.update("Generating full answer...")
    window.perform_long_operation(
        lambda: gpt_query.generate_answer(
            audio_transcript,
            short_answer=False,
            temperature=0.7,
            model=model,
            position=position,
            context=context_payload,
        ),
        "-FULL_ANSWER-",
    )
