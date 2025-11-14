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


def _should_block_hotkeys(focused_key: Optional[str]) -> bool:
    return focused_key in CONTEXT_TEXT_INPUT_KEYS if focused_key else False


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

    focused_element: Optional[sg.Element] = window.find_element_with_focus()
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

    # When the recording thread finished saving audio
    elif event == "-RECORDED-":
        recording_complete_event(window, values)

    # When the transcription is ready
    elif event == "-WHISPER-":
        answer_events(window, values)

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
    Handle the recording event. Record audio and update the record button.

    Args:
        window (sg.Window): The window element.
    """
    button: sg.Element = window["-RECORD_BUTTON-"]
    button.metadata.state = not button.metadata.state
    button.update(image_data=ON_IMAGE if button.metadata.state else OFF_IMAGE)
    metadata: Dict[str, Any] = _window_metadata(window)

    # Record audio
    if button.metadata.state:
        metadata["recording_in_progress"] = True
        metadata["pending_transcription"] = False
        window.perform_long_operation(lambda: audio.record(button), "-RECORDED-")
    else:
        logger.debug("Stopping recording...")


def transcribe_event(window: sg.Window) -> None:
    """
    Handle the transcribe event. Transcribe audio and update the text area.

    Args:
        window (sg.Window): The window element.
    """
    metadata: Dict[str, Any] = _window_metadata(window)
    record_button: sg.Element = window["-RECORD_BUTTON-"]

    # If we are still recording, stop first and wait for completion
    if record_button.metadata.state:
        recording_event(window)

    if metadata.get("recording_in_progress"):
        metadata["pending_transcription"] = True
        window["-TRANSCRIBED_TEXT-"].update("Finishing recording...")
        return

    recorded_path: Any = metadata.get("last_recording_path")
    if not recorded_path:
        output_path = Path(OUTPUT_FILE_NAME)
        if output_path.is_file():
            recorded_path = str(output_path.resolve())

    if not recorded_path or not Path(recorded_path).is_file():
        window["-TRANSCRIBED_TEXT-"].update(
            "No recording found. Press 'R' to record audio first."
        )
        sg.popup_error(
            "No recording found. Please record audio before transcribing.",
            title="Recording Missing",
        )
        return

    metadata["pending_transcription"] = False
    transcribed_text: sg.Element = window["-TRANSCRIBED_TEXT-"]
    transcribed_text.update("Transcribing audio...")

    # Transcribe audio
    window.perform_long_operation(
        lambda: gpt_query.transcribe_audio(recorded_path), "-WHISPER-"
    )


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


def recording_complete_event(window: sg.Window, values: Dict[str, Any]) -> None:
    """
    Handle the completion of the background recording operation.
    """
    metadata: Dict[str, Any] = _window_metadata(window)
    metadata["recording_in_progress"] = False
    recorded_path: Any = values.get("-RECORDED-")

    if recorded_path:
        metadata["last_recording_path"] = recorded_path
        logger.debug(f"Recording saved at {recorded_path}")
    else:
        metadata["last_recording_path"] = None
        logger.warning("Recording finished without audio output.")

    if metadata.pop("pending_transcription", False):
        transcribe_event(window)
