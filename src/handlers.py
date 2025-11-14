from pathlib import Path
from typing import Any, Dict

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


def handle_events(window: sg.Window, event: str, values: Dict[str, Any]) -> None:
    """
    Handle the events. Record audio, transcribe audio, generate quick and full answers.

    Args:
        window (sg.Window): The window element.
        event (str): The event.
        values (Dict[str, Any]): The values of the window.
    """
    # If the user is not focused on the position input, process the events
    focused_element: sg.Element = window.find_element_with_focus()
    if not focused_element or focused_element.Key != "-POSITION_INPUT-":
        if event in ("r", "R", "-RECORD_BUTTON-"):
            recording_event(window)
        elif event in ("a", "A", "-ANALYZE_BUTTON-"):
            transcribe_event(window)

    # If the user is focused on the position input
    if event[:6] in ("Return", "Escape"):
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
