"""Audio feedback sounds for dictation-me."""

from __future__ import annotations

import numpy as np
import sounddevice as sd


class Sounds:
    """Generates and plays lightweight audio feedback tones."""

    SAMPLE_RATE = 44100
    VOLUME = 0.3

    def __init__(self):
        self._start_tone = self._generate_start_tone()
        self._stop_tone = self._generate_stop_tone()
        self._done_tone = self._generate_done_tone()

    def play_start(self) -> None:
        """Play the start-recording chime."""
        sd.play(self._start_tone, self.SAMPLE_RATE)

    def play_stop(self) -> None:
        """Play the stop-recording tone."""
        sd.play(self._stop_tone, self.SAMPLE_RATE)

    def play_done(self) -> None:
        """Play the transcription-complete ping."""
        sd.play(self._done_tone, self.SAMPLE_RATE)

    def _generate_start_tone(self) -> np.ndarray:
        """Rising two-note chime (C5 -> E5)."""
        first = self._make_tone(523.25, 0.06, attack=0.006, decay=0.03)
        second = self._make_tone(659.25, 0.06, attack=0.006, decay=0.035)
        return np.concatenate((first, second)).astype(np.float32, copy=False)

    def _generate_stop_tone(self) -> np.ndarray:
        """Gentle descending tone."""
        duration = 0.1
        sample_count = max(1, int(round(duration * self.SAMPLE_RATE)))
        t = np.arange(sample_count, dtype=np.float32) / self.SAMPLE_RATE
        frequencies = np.linspace(440.0, 392.0, sample_count, dtype=np.float32)
        phase = 2 * np.pi * np.cumsum(frequencies) / self.SAMPLE_RATE
        wave = np.sin(phase).astype(np.float32, copy=False)
        envelope = self._make_envelope(duration, attack=0.008, decay=0.08)
        tone = self.VOLUME * 0.9 * wave * envelope
        return tone.astype(np.float32, copy=False)

    def _generate_done_tone(self) -> np.ndarray:
        """Pleasant notification ping."""
        duration = 0.2
        sample_count = max(1, int(round(duration * self.SAMPLE_RATE)))
        t = np.arange(sample_count, dtype=np.float32) / self.SAMPLE_RATE
        fundamental = np.sin(2 * np.pi * 880.0 * t)
        harmonic = 0.3 * np.sin(2 * np.pi * 1760.0 * t)
        wave = fundamental + harmonic
        peak = float(np.max(np.abs(wave))) or 1.0
        envelope = self._make_envelope(duration, attack=0.008, decay=0.16)
        tone = self.VOLUME * (wave / peak) * envelope
        return tone.astype(np.float32, copy=False)

    def _make_tone(
        self, frequency: float, duration: float, attack: float = 0.01, decay: float = 0.05
    ) -> np.ndarray:
        """Generate a single tone with envelope."""
        sample_count = max(1, int(round(duration * self.SAMPLE_RATE)))
        t = np.arange(sample_count, dtype=np.float32) / self.SAMPLE_RATE
        wave = np.sin(2 * np.pi * frequency * t)
        envelope = self._make_envelope(duration, attack=attack, decay=decay)
        tone = self.VOLUME * wave * envelope
        return tone.astype(np.float32, copy=False)

    def _make_envelope(self, duration: float, attack: float, decay: float) -> np.ndarray:
        """Generate a smooth attack/decay envelope."""
        sample_count = max(1, int(round(duration * self.SAMPLE_RATE)))
        envelope = np.ones(sample_count, dtype=np.float32)

        attack_samples = min(sample_count, max(1, int(round(attack * self.SAMPLE_RATE))))
        decay_samples = min(sample_count, max(1, int(round(decay * self.SAMPLE_RATE))))

        envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples, endpoint=False, dtype=np.float32)
        envelope[-decay_samples:] *= np.linspace(1.0, 0.0, decay_samples, endpoint=True, dtype=np.float32)
        return envelope
