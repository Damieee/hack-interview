from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import PySimpleGUI as sg
import sounddevice as sd
import soundfile as sf
from loguru import logger

from src.config import OUTPUT_FILE_NAME, SAMPLE_RATE


def find_blackhole_device_id() -> Optional[int]:
    """
    Find the BlackHole device ID in the list of devices.

    Returns:
        Optional[int]: The BlackHole device ID if found, None otherwise.
    """
    devices: List[Dict[str, Any]] = sd.query_devices()
    for device_id, device in enumerate(devices):
        if "BlackHole" in device["name"]:
            return device_id

    return None


def record(button: sg.Element) -> Optional[str]:
    """
    Record audio from the BlackHole device while the record button is active.
    Save the audio to a file.

    Args:
        button (sg.Element): The record button element.
    """
    logger.debug("Recording...")
    frames: List[np.ndarray] = []
    saved_path: Optional[str] = None

    # Find BlackHole device ID
    device_id: Optional[int] = find_blackhole_device_id()

    # Record audio
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, device=device_id) as stream:
            while button.metadata.state:
                data: np.ndarray
                overflowed: bool
                data, overflowed = stream.read(SAMPLE_RATE)
                if overflowed:
                    logger.warning("Audio buffer overflowed")
                frames.append(data)

    except Exception as e:
        logger.error(f"An error occurred during recording: {e}")
    finally:
        # Save audio file
        if frames:
            audio_data: np.ndarray = np.vstack(frames)
            saved_path = save_audio_file(audio_data)
        else:
            logger.warning("No audio recorded.")

    return saved_path


def save_audio_file(
    audio_data: np.ndarray, output_file_name: str = OUTPUT_FILE_NAME
) -> str:
    """
    Save the audio data to a file.

    Args:
        audio_data (np.ndarray): The audio data.
        output_file_name (str, optional): The output file name. Defaults to OUTPUT_FILE_NAME.
    """
    output_path = Path(output_file_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        file=str(output_path),
        data=audio_data,
        samplerate=SAMPLE_RATE,
        format="WAV",
        subtype="PCM_16",
    )
    resolved = str(output_path.resolve())
    logger.debug(f"Audio saved to: {resolved}...")
    return resolved


class ContinuousRecorder:
    """
    Continuously listen for speech, detect pauses, and emit audio segments automatically.
    """

    def __init__(
        self,
        segment_callback: Callable[[str], None],
        silence_duration: float = 1.3,
        min_speech_duration: float = 1.0,
        pre_roll: float = 0.4,
        amplitude_threshold: float = 0.015,
    ) -> None:
        self.segment_callback = segment_callback
        self.silence_frames: int = int(silence_duration * SAMPLE_RATE)
        self.min_frames: int = int(min_speech_duration * SAMPLE_RATE)
        self.pre_roll_limit: int = int(pre_roll * SAMPLE_RATE)
        self.threshold: float = amplitude_threshold
        self.device_id: Optional[int] = find_blackhole_device_id()
        self._queue: Queue = Queue()
        self._stream: Optional[sd.InputStream] = None
        self._processor: Optional[Thread] = None
        self._running: bool = False
        self._capture_active: bool = False
        self._frames_since_voice: int = 0
        self._current_frames: List[np.ndarray] = []
        self._pre_buffer: List[np.ndarray] = []

    def start(self) -> None:
        if self._running:
            logger.debug("Continuous recorder already running.")
            return

        self._running = True
        self._queue = Queue()
        self._processor = Thread(target=self._process_loop, daemon=True)
        self._processor.start()

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                device=self.device_id,
                channels=1,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.debug("Continuous recorder started.")
        except Exception as error:
            self._running = False
            logger.error(f"Unable to start continuous recorder: {error}")
            raise

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as error:
                logger.error(f"Error stopping audio stream: {error}")
            finally:
                self._stream = None

        self._queue.put(None)  # type: ignore[arg-type]
        if self._processor is not None:
            self._processor.join(timeout=1.5)
            self._processor = None

        self._emit_segment(force=True)
        logger.debug("Continuous recorder stopped.")

    def _audio_callback(self, indata: np.ndarray, frames: int, *_: Any) -> None:
        if not self._running:
            return
        self._queue.put(indata.copy())

    def _process_loop(self) -> None:
        while self._running or not self._queue.empty():
            try:
                chunk = self._queue.get(timeout=0.2)
            except Empty:
                continue

            if chunk is None:
                continue

            self._handle_chunk(chunk)

    def _handle_chunk(self, data: np.ndarray) -> None:
        amplitude: float = float(np.max(np.abs(data)))
        speaking: bool = amplitude > self.threshold

        if speaking and not self._capture_active:
            if self._pre_buffer:
                self._current_frames.extend(self._pre_buffer)
            self._capture_active = True
            self._frames_since_voice = 0

        if self._capture_active:
            self._current_frames.append(data)
            if speaking:
                self._frames_since_voice = 0
            else:
                self._frames_since_voice += len(data)
                if self._frames_since_voice >= self.silence_frames:
                    self._emit_segment()
        else:
            self._append_prebuffer(data)

    def _append_prebuffer(self, data: np.ndarray) -> None:
        self._pre_buffer.append(data)
        total_frames = sum(frame.shape[0] for frame in self._pre_buffer)
        while total_frames > self.pre_roll_limit and self._pre_buffer:
            removed = self._pre_buffer.pop(0)
            total_frames -= removed.shape[0]

    def _emit_segment(self, force: bool = False) -> None:
        if not self._current_frames:
            self._reset_capture()
            return

        audio_data = np.vstack(self._current_frames)
        if not force and audio_data.shape[0] < self.min_frames:
            logger.debug("Discarded short audio segment (%s frames).", audio_data.shape[0])
            self._reset_capture()
            return

        output_path = self._build_output_path()
        save_audio_file(audio_data, output_path)

        self._reset_capture()
        if self.segment_callback:
            self.segment_callback(output_path)

    def _reset_capture(self) -> None:
        self._current_frames = []
        self._capture_active = False
        self._frames_since_voice = 0
        self._pre_buffer = []

    def _build_output_path(self) -> str:
        recordings_dir = Path("recordings")
        recordings_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        return str(recordings_dir / f"recording_{timestamp}.wav")
