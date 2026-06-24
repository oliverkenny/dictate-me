"""System tray icon for dictation-me."""

from __future__ import annotations

import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw
import pystray
from pystray import Icon, Menu, MenuItem


class SystemTray:
    """System tray icon with settings menu."""

    MODELS = ["tiny", "base", "small", "medium", "large-v3"]
    ICON_SIZE = 64
    BACKGROUND_COLOUR = "#1f2933"
    FOREGROUND_COLOUR = "#ffffff"

    def __init__(
        self,
        on_quit: Optional[Callable[[], None]] = None,
        on_toggle_startup: Optional[Callable[[bool], None]] = None,
        on_model_change: Optional[Callable[[str], None]] = None,
    ):
        self._on_quit = on_quit
        self._on_toggle_startup = on_toggle_startup
        self._on_model_change = on_model_change

        self._lock = threading.RLock()
        self._status = "Ready"
        self._startup_enabled = False
        self._current_model = "base"
        self._icon: Optional[Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _create_icon_image(self) -> Image.Image:
        """Create a simple microphone icon."""
        image = Image.new(
            "RGBA",
            (self.ICON_SIZE, self.ICON_SIZE),
            self.BACKGROUND_COLOUR,
        )
        draw = ImageDraw.Draw(image)

        line_width = 4
        head_left = 22
        head_top = 10
        head_right = 42
        head_bottom = 34

        draw.rounded_rectangle(
            (head_left, head_top, head_right, head_bottom),
            radius=10,
            outline=self.FOREGROUND_COLOUR,
            width=line_width,
        )
        draw.line(
            ((32, head_bottom), (32, 46)),
            fill=self.FOREGROUND_COLOUR,
            width=line_width,
        )
        draw.arc(
            (16, 18, 48, 50),
            start=200,
            end=340,
            fill=self.FOREGROUND_COLOUR,
            width=line_width,
        )
        draw.line(
            ((22, 52), (42, 52)),
            fill=self.FOREGROUND_COLOUR,
            width=line_width,
        )

        return image

    def _build_menu(self) -> Menu:
        """Build the context menu."""
        return Menu(
            MenuItem("dictation-me", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(lambda item: f"Status: {self._get_status()}", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(
                "Start on login",
                self._handle_toggle_startup,
                checked=lambda item: self._is_startup_enabled(),
            ),
            MenuItem("Model", self._build_model_menu()),
            Menu.SEPARATOR,
            MenuItem("Quit", self._handle_quit),
        )

    def _build_model_menu(self) -> Menu:
        items = []
        for model in self.MODELS:
            items.append(
                MenuItem(
                    model,
                    self._make_model_handler(model),
                    checked=self._make_model_checker(model),
                    radio=True,
                )
            )
        return Menu(*items)

    def _make_model_handler(self, model: str):
        def handler(icon, item):
            self._handle_model_change(model)
        return handler

    def _make_model_checker(self, model: str):
        def checker(item):
            return self._is_current_model(model)
        return checker

    def _create_icon(self) -> Icon:
        return pystray.Icon(
            "dictation-me",
            self._create_icon_image(),
            "dictation-me",
            menu=self._build_menu(),
        )

    def _get_status(self) -> str:
        with self._lock:
            return self._status

    def _is_startup_enabled(self) -> bool:
        with self._lock:
            return self._startup_enabled

    def _is_current_model(self, model: str) -> bool:
        with self._lock:
            return self._current_model == model

    def _refresh_menu(self) -> None:
        with self._lock:
            icon = self._icon

        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    def _handle_toggle_startup(self, icon: Icon, item: MenuItem) -> None:
        with self._lock:
            self._startup_enabled = not self._startup_enabled
            enabled = self._startup_enabled

        self._refresh_menu()

        if self._on_toggle_startup is not None:
            self._on_toggle_startup(enabled)

    def _handle_model_change(self, model: str) -> None:
        with self._lock:
            if model not in self.MODELS:
                return
            self._current_model = model

        self._refresh_menu()

        if self._on_model_change is not None:
            self._on_model_change(model)

    def _handle_quit(self, icon: Icon, item: MenuItem) -> None:
        try:
            if self._on_quit is not None:
                self._on_quit()
        finally:
            self.stop()

    def _run_icon(self) -> None:
        with self._lock:
            icon = self._icon

        if icon is None:
            return

        try:
            icon.run()
        finally:
            with self._lock:
                self._icon = None
                self._thread = None

    def set_status(self, status: str) -> None:
        """Update the status display."""
        with self._lock:
            self._status = status

        self._refresh_menu()

    def set_startup_enabled(self, enabled: bool) -> None:
        """Update the startup toggle state."""
        with self._lock:
            self._startup_enabled = enabled

        self._refresh_menu()

    def set_current_model(self, model: str) -> None:
        """Update the current model selection."""
        if model not in self.MODELS:
            raise ValueError(f"Unsupported model: {model}")

        with self._lock:
            self._current_model = model

        self._refresh_menu()

    def run(self) -> None:
        """Start the tray icon (non-blocking, runs in background thread)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._icon = self._create_icon()
            self._thread = threading.Thread(
                target=self._run_icon,
                name="dictation-system-tray",
                daemon=True,
            )
            thread = self._thread

        thread.start()

    def stop(self) -> None:
        """Stop and remove the tray icon."""
        with self._lock:
            icon = self._icon
            thread = self._thread

        if icon is None:
            return

        try:
            icon.stop()
        except Exception:
            pass

        if (
            thread is not None
            and thread.is_alive()
            and threading.get_ident() != thread.ident
        ):
            thread.join(timeout=2)

