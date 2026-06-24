"""Transcription module using faster-whisper."""

from __future__ import annotations

import threading
from typing import Any, Optional

import numpy as np


class Transcriber:
    """Transcribes audio using a local Whisper model via faster-whisper."""

    _TARGET_SAMPLE_RATE = 16000

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model: Any | None = None
        self._model_lock = threading.Lock()
        self._transcribe_lock = threading.Lock()

    def load_model(self) -> None:
        """Pre-load the Whisper model (downloads on first use)."""
        if self._model is not None:
            return

        with self._model_lock:
            if self._model is not None:
                return

            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. Install project dependencies to enable transcription."
                ) from exc

            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load Whisper model '{self.model_size}'. "
                    "This can happen if the model download fails or the runtime is unsupported."
                ) from exc

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio array to text."""
        prepared_audio = self._prepare_audio(audio, sample_rate)
        self.load_model()

        with self._transcribe_lock:
            try:
                transcribe_kwargs = {"language": self.language} if self.language else {}
                segments, _ = self._model.transcribe(
                    prepared_audio,
                    beam_size=1,
                    vad_filter=True,
                    **transcribe_kwargs,
                )
                text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
                return " ".join(text_parts).strip()
            except Exception as exc:
                raise RuntimeError(f"Failed to transcribe audio: {exc}") from exc

    def _prepare_audio(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        if not isinstance(audio, np.ndarray):
            raise TypeError("audio must be a numpy.ndarray")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be a positive integer")

        prepared_audio = np.asarray(audio, dtype=np.float32).squeeze()
        if prepared_audio.size == 0:
            raise ValueError("audio array is empty")

        if prepared_audio.ndim == 2:
            channel_axis = 0 if prepared_audio.shape[0] <= prepared_audio.shape[1] else 1
            prepared_audio = prepared_audio.mean(axis=channel_axis, dtype=np.float32)
        elif prepared_audio.ndim != 1:
            raise ValueError("audio must be a 1D mono signal or a 2D multi-channel signal")

        if sample_rate != self._TARGET_SAMPLE_RATE:
            prepared_audio = self._resample_audio(
                prepared_audio,
                source_rate=sample_rate,
                target_rate=self._TARGET_SAMPLE_RATE,
            )

        return np.ascontiguousarray(prepared_audio, dtype=np.float32)

    def _resample_audio(
        self,
        audio: np.ndarray,
        source_rate: int,
        target_rate: int,
    ) -> np.ndarray:
        if source_rate == target_rate or audio.size < 2:
            return np.ascontiguousarray(audio, dtype=np.float32)

        duration = audio.shape[0] / float(source_rate)
        target_length = max(1, int(round(duration * target_rate)))
        source_positions = np.linspace(0.0, duration, num=audio.shape[0], endpoint=False)
        target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)
