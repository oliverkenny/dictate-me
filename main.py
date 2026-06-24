"""dictation-me - Lightweight local dictation using Whisper."""

from __future__ import annotations

# Use Windows certificate store for SSL (fixes corporate proxy issues)
import truststore
truststore.inject_into_ssl()

# Disable HF xet protocol (can be unreliable); use standard HTTP downloads
import os
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import logging
import os
import sys
import threading
import time

import keyboard
import pyautogui
import pyperclip

import config
from src.audio import AudioRecorder
from src.overlay import Overlay
from src.settings import Settings
from src.sounds import Sounds
from src.transcriber import Transcriber
from src.tray import SystemTray

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Logging setup - writes to logs/dictation.log
LOG_DIR = os.path.join(APP_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "dictation.log")

log_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("dictation-me")

# Suppress noisy HTTP debug logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

pyautogui.PAUSE = 0


class DictationApp:
    """Main application orchestrating recording, transcription, and text insertion."""

    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_PROCESSING = "processing"

    _ERROR_OVERLAY_COLOUR = "#c0392b"
    _INFO_OVERLAY_COLOUR = "#007aff"
    _OVERLAY_HIDE_DELAY_SECONDS = 1.5
    _CLIPBOARD_DELAY_SECONDS = 0.05

    def __init__(self):
        self.state = self.STATE_IDLE
        self.settings = Settings()
        self.recorder = AudioRecorder(sample_rate=config.SAMPLE_RATE, channels=config.CHANNELS)
        self.transcriber = Transcriber(
            model_size=self.settings.model_size,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
        )
        self.overlay = Overlay()
        self.tray = SystemTray(
            on_quit=self._on_tray_quit,
            on_toggle_startup=self._on_toggle_startup,
            on_model_change=self._on_model_change,
        )
        self.tray.set_startup_enabled(self.settings.start_on_login)
        self.tray.set_current_model(self.settings.model_size)
        self.sounds = Sounds()
        self._lock = threading.RLock()
        self._hotkey_handle = None
        self._overlay_token = 0

    def toggle(self) -> None:
        """Toggle between recording states."""
        with self._lock:
            if self.state == self.STATE_IDLE:
                self._start_recording()
            elif self.state == self.STATE_RECORDING:
                self._stop_and_transcribe()
            else:
                logger.debug("Still processing previous dictation; ignoring hotkey.")

    def _start_recording(self) -> None:
        """Start recording audio."""
        try:
            self.recorder.start()
            self.state = self.STATE_RECORDING
            self.sounds.play_start()
            self._show_recording_overlay()
            logger.info("Recording started")
        except Exception as exc:
            self.state = self.STATE_IDLE
            self._handle_error("Unable to start recording", exc)

    def _stop_and_transcribe(self) -> None:
        """Stop recording and transcribe in a background thread."""
        try:
            audio = self.recorder.stop()
            self.state = self.STATE_PROCESSING
            self.sounds.play_stop()
            self._show_processing_overlay()
            logger.info("Processing audio...")
            threading.Thread(target=self._transcribe_and_type, args=(audio,), daemon=True).start()
        except Exception as exc:
            self.state = self.STATE_IDLE
            self.overlay.hide()
            self._handle_error("Unable to stop recording", exc)

    def _transcribe_and_type(self, audio) -> None:
        """Transcribe audio and type the result."""
        hide_overlay_immediately = True

        try:
            text = self.transcriber.transcribe(audio, sample_rate=config.SAMPLE_RATE)
            if text:
                self._type_text(text)
                self.sounds.play_done()
                logger.info("Transcribed: %s", text)
            else:
                logger.info("No speech detected")
        except Exception as exc:
            hide_overlay_immediately = False
            self._handle_error("Transcription failed", exc)
        finally:
            with self._lock:
                self.state = self.STATE_IDLE
            if hide_overlay_immediately:
                self.overlay.hide()
            self.tray.set_status("Ready")

    def _type_text(self, text: str) -> None:
        """Type text at the current cursor position."""
        if text.isascii():
            pyautogui.write(text, interval=0)
            return

        pyperclip.copy(text)
        time.sleep(self._CLIPBOARD_DELAY_SECONDS)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(self._CLIPBOARD_DELAY_SECONDS)

    def _show_recording_overlay(self) -> None:
        self._bump_overlay_token()
        self.overlay.show_recording()
        self.tray.set_status("Recording...")

    def _show_processing_overlay(self) -> None:
        self._bump_overlay_token()
        self.overlay.show_processing()
        self.tray.set_status("Processing...")

    def _show_download_progress(self, text: str) -> None:
        """Show download/loading status on the overlay."""
        self._bump_overlay_token()
        self.tray.set_status(text)
        try:
            self.overlay._run_on_ui_thread(
                self.overlay._show_state, self._INFO_OVERLAY_COLOUR, text, False
            )
        except Exception:
            pass

    def _show_error_overlay(self, message: str) -> None:
        token = self._bump_overlay_token()

        try:
            show_state = getattr(self.overlay, "_show_state")
            run_on_ui_thread = getattr(self.overlay, "_run_on_ui_thread")
            run_on_ui_thread(show_state, "#c0392b", message, False)
            threading.Thread(
                target=self._hide_overlay_after_delay,
                args=(token,),
                daemon=True,
            ).start()
        except Exception:
            self.overlay.hide()

    def _hide_overlay_after_delay(self, token: int) -> None:
        time.sleep(self._OVERLAY_HIDE_DELAY_SECONDS)
        with self._lock:
            if self.state != self.STATE_IDLE or token != self._overlay_token:
                return
        self.overlay.hide()

    def _bump_overlay_token(self) -> int:
        with self._lock:
            self._overlay_token += 1
            return self._overlay_token

    def _handle_error(self, context: str, exc: Exception) -> None:
        logger.error("%s: %s", context, exc, exc_info=True)
        self._show_error_overlay("Error")
        self.tray.set_status("Ready")

    def _on_tray_quit(self) -> None:
        """Handle quit from system tray."""
        logger.info("Quit requested from tray")
        self._shutdown()
        os._exit(0)

    def _on_toggle_startup(self, enabled: bool) -> None:
        """Handle start-on-login toggle from tray."""
        logger.info("Start on login: %s", enabled)
        self.settings.set_start_on_login(enabled)

    def _on_model_change(self, model: str) -> None:
        """Handle model change from tray."""
        logger.info("Model changed to: %s", model)
        self.settings.model_size = model
        self.transcriber = Transcriber(
            model_size=model,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
        )
        threading.Thread(target=self._preload_model, daemon=True).start()

    def _preload_model(self) -> None:
        """Pre-load the Whisper model, showing download progress if needed."""
        try:
            if not self.transcriber.is_model_cached():
                logger.info("Model not cached, downloading...")
                self._show_download_progress("Downloading model... 0%")

                def on_progress(downloaded, total):
                    if total > 0:
                        pct = int((downloaded / total) * 100)
                        self._show_download_progress(f"Downloading model... {pct}%")

                self.transcriber.download_model(progress_callback=on_progress)
                logger.info("Model downloaded successfully")

            self._show_download_progress("Loading model...")
            self.transcriber.load_model()
            logger.info("Model loaded successfully")
            self._show_download_progress("Ready! Press Ctrl+Space")
            time.sleep(self._OVERLAY_HIDE_DELAY_SECONDS)
            self.overlay.hide()
        except Exception as exc:
            logger.warning("Model pre-load failed: %s (will retry on first use)", exc)
            self.tray.set_status("Ready")
            self.overlay.hide()

    def _shutdown(self) -> None:
        """Clean up resources."""
        logger.info("Shutting down...")

        if self._hotkey_handle is not None:
            keyboard.remove_hotkey(self._hotkey_handle)
            self._hotkey_handle = None
        keyboard.unhook_all()

        if self.recorder.is_recording:
            try:
                self.recorder.stop()
            except Exception:
                pass

        self.overlay.destroy()
        self.tray.stop()
        logger.info("Goodbye!")

    def run(self) -> None:
        """Run the application."""
        logger.info("=" * 50)
        logger.info("  dictation-me - Local Dictation Tool")
        logger.info("=" * 50)
        logger.info("  Model: %s (%s) on %s", self.settings.model_size, self.settings.compute_type, self.settings.device)
        logger.info("  Sample rate: %s Hz", config.SAMPLE_RATE)
        logger.info("  Hotkey: %s", self.settings.hotkey.upper())
        logger.info("  Log file: %s", LOG_FILE)
        logger.info("  Press CTRL+C to quit (or Quit from tray)")
        logger.info("=" * 50)

        self.tray.run()
        logger.info("Loading model in background...")
        threading.Thread(target=self._preload_model, daemon=True).start()
        self._hotkey_handle = keyboard.add_hotkey(self.settings.hotkey, self.toggle, suppress=True)

        try:
            logger.info("Ready! Press CTRL+SPACE to start dictating")
            keyboard.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()


if __name__ == "__main__":
    app = DictationApp()
    app.run()
