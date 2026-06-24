"""Audio recording module using sounddevice."""

from __future__ import annotations

import queue
import threading

import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._audio_queue: queue.Queue[np.ndarray | Exception] = queue.Queue()
        self._lock = threading.RLock()
        self._callback_error: Exception | None = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start(self) -> None:
        """Start recording audio from the default microphone."""
        with self._lock:
            if self._recording:
                raise RuntimeError("Recording is already in progress.")

            self._audio_queue = queue.Queue()
            self._callback_error = None

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self._stream.start()
            except Exception as exc:
                self._stream = None
                raise RuntimeError(
                    "Unable to start audio recording. Check microphone availability and permissions."
                ) from exc

            self._recording = True

    def stop(self) -> np.ndarray:
        """Stop recording and return the audio as a float32 numpy array."""
        with self._lock:
            if not self._recording:
                raise RuntimeError("Recording is not in progress.")

            stream = self._stream
            self._stream = None
            self._recording = False

        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                raise RuntimeError("Unable to stop audio recording cleanly.") from exc

        chunks: list[np.ndarray] = []
        while True:
            try:
                item = self._audio_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(item, Exception):
                self._callback_error = item
                continue

            chunks.append(item)

        if self._callback_error is not None:
            raise RuntimeError("Audio capture failed during recording.") from self._callback_error

        if not chunks:
            return np.empty(0, dtype=np.float32)

        audio = np.concatenate(chunks, axis=0).astype(np.float32, copy=False)
        if self.channels == 1:
            audio = audio.reshape(-1)

        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak

        return np.clip(audio, -1.0, 1.0).astype(np.float32, copy=False)

    def _audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice stream."""
        if status:
            self._audio_queue.put(RuntimeError(f"Audio input error: {status}"))
            return

        try:
            self._audio_queue.put(indata.copy())
        except Exception as exc:
            self._audio_queue.put(exc)
