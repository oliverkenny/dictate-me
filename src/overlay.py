"""Floating overlay bubble for dictation status."""

from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from typing import Optional


class Overlay:
    """A floating status overlay at the top centre of the screen."""

    WIDTH = 280
    HEIGHT = 50
    TOP_MARGIN = 16
    ARC_RADIUS = 25

    TRANSPARENT_COLOUR = "#ff00ff"

    BG_COLOUR = "#e8eaed"
    BORDER_COLOUR = "#b0b3b8"
    HIGHLIGHT_COLOUR = "#ffffff"
    TEXT_COLOUR = "#1d1d1f"
    RECORDING_ACCENT = "#ff3b30"
    PROCESSING_ACCENT = "#ff9500"
    GLOW_RECORDING = "#ffb3b0"
    GLOW_PROCESSING = "#ffe0b2"

    FADE_STEPS = 8
    FADE_INTERVAL_MS = 16
    PULSE_INTERVAL_MS = 600
    TARGET_ALPHA = 0.88

    DOT_CENTRE_X = 36
    DOT_RADIUS = 7
    GLOW_RADIUS = 12
    TEXT_X = 60

    def __init__(self):
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._bubble_id: Optional[int] = None
        self._border_id: Optional[int] = None
        self._highlight_id: Optional[int] = None
        self._glow_id: Optional[int] = None
        self._dot_id: Optional[int] = None
        self._text_id: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._ui_thread_id: Optional[int] = None
        self._window_ready = threading.Event()
        self._closed = threading.Event()
        self._animation_job: Optional[str] = None
        self._pulse_job: Optional[str] = None
        self._pulse_expanded = False
        self._alpha = 0.0

        self._thread = threading.Thread(
            target=self._create_window,
            name="dictation-overlay",
            daemon=True,
        )
        self._thread.start()
        self._window_ready.wait(timeout=5)

    def _create_window(self):
        """Create the tkinter window in its own thread."""
        self._ui_thread_id = threading.get_ident()

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.wm_attributes("-toolwindow", True)
        root.configure(bg=self.TRANSPARENT_COLOUR)
        root.geometry(f"{self.WIDTH}x{self.HEIGHT}+0+0")

        try:
            root.attributes("-transparentcolor", self.TRANSPARENT_COLOUR)
        except tk.TclError:
            pass

        try:
            root.attributes("-alpha", 0.0)
        except tk.TclError:
            self._alpha = 1.0

        canvas = tk.Canvas(
            root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.TRANSPARENT_COLOUR,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)

        self._root = root
        self._canvas = canvas

        self._border_id = self._create_rounded_rect(
            0,
            0,
            self.WIDTH - 1,
            self.HEIGHT - 1,
            self.ARC_RADIUS,
            fill=self.BORDER_COLOUR,
            outline=self.BORDER_COLOUR,
        )
        self._bubble_id = self._create_rounded_rect(
            1,
            1,
            self.WIDTH - 2,
            self.HEIGHT - 2,
            self.ARC_RADIUS - 1,
            fill=self.BG_COLOUR,
            outline=self.BG_COLOUR,
        )
        self._highlight_id = canvas.create_line(
            self.ARC_RADIUS,
            7,
            self.WIDTH - self.ARC_RADIUS,
            7,
            fill=self.HIGHLIGHT_COLOUR,
            width=1,
        )

        cy = self.HEIGHT // 2
        self._glow_id = canvas.create_oval(0, 0, 0, 0, fill="", outline="")
        self._dot_id = canvas.create_oval(0, 0, 0, 0, fill="", outline="")
        self._text_id = canvas.create_text(
            self.TEXT_X,
            cy,
            text="",
            fill=self.TEXT_COLOUR,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        )

        self._set_indicator(self.RECORDING_ACCENT, self.GLOW_RECORDING, expanded=False)
        self._position_centre_top()
        self._apply_no_activate(show=False)
        self._window_ready.set()

        try:
            root.mainloop()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass
            self._root = None
            self._canvas = None
            self._closed.set()

    def _position_centre_top(self):
        """Position the window at top centre of screen."""
        if self._root is None:
            return

        self._root.update_idletasks()
        x = (self._root.winfo_screenwidth() - self.WIDTH) // 2
        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{self.TOP_MARGIN}")

    def _create_rounded_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs,
    ) -> int:
        if self._canvas is None:
            raise RuntimeError("Canvas is not ready")

        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self._canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)

    @staticmethod
    def _mix_colours(primary: str, secondary: str, primary_ratio: float) -> str:
        primary_ratio = max(0.0, min(1.0, primary_ratio))
        secondary_ratio = 1.0 - primary_ratio

        primary_rgb = tuple(int(primary[index:index + 2], 16) for index in (1, 3, 5))
        secondary_rgb = tuple(int(secondary[index:index + 2], 16) for index in (1, 3, 5))
        mixed = tuple(
            round((accent * primary_ratio) + (base * secondary_ratio))
            for accent, base in zip(primary_rgb, secondary_rgb)
        )
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"

    def _glow_for_accent(self, accent: str) -> str:
        if accent == self.RECORDING_ACCENT:
            return self.GLOW_RECORDING
        return self.GLOW_PROCESSING

    def _set_indicator(self, accent: str, glow: str, expanded: bool) -> None:
        if self._canvas is None or self._dot_id is None or self._glow_id is None:
            return

        cy = self.HEIGHT // 2
        dot_radius = self.DOT_RADIUS + (1 if expanded else 0)
        glow_radius = self.GLOW_RADIUS + (2 if expanded else 0)
        glow_fill = glow if expanded else self._mix_colours(glow, self.BG_COLOUR, 0.7)

        self._canvas.coords(
            self._glow_id,
            self.DOT_CENTRE_X - glow_radius,
            cy - glow_radius,
            self.DOT_CENTRE_X + glow_radius,
            cy + glow_radius,
        )
        self._canvas.itemconfigure(self._glow_id, fill=glow_fill, outline=glow_fill)

        self._canvas.coords(
            self._dot_id,
            self.DOT_CENTRE_X - dot_radius,
            cy - dot_radius,
            self.DOT_CENTRE_X + dot_radius,
            cy + dot_radius,
        )
        self._canvas.itemconfigure(self._dot_id, fill=accent, outline=accent)

    def _start_pulse(self, accent: str) -> None:
        """Start pulsing the recording indicator."""
        self._stop_pulse()
        glow = self._glow_for_accent(accent)
        self._pulse_expanded = False

        def pulse() -> None:
            if self._root is None:
                return
            self._pulse_expanded = not self._pulse_expanded
            self._set_indicator(accent, glow, expanded=self._pulse_expanded)
            self._pulse_job = self._root.after(self.PULSE_INTERVAL_MS, pulse)

        pulse()

    def _stop_pulse(self) -> None:
        """Stop the pulsing animation."""
        if self._root is not None and self._pulse_job is not None:
            try:
                self._root.after_cancel(self._pulse_job)
            except tk.TclError:
                pass
        self._pulse_job = None
        self._pulse_expanded = False

    def _run_on_ui_thread(self, callback, *args) -> None:
        if not self._window_ready.wait(timeout=5):
            return
        if self._root is None or self._closed.is_set():
            return

        if threading.get_ident() == self._ui_thread_id:
            callback(*args)
            return

        try:
            self._root.after(0, lambda: callback(*args))
        except (RuntimeError, tk.TclError):
            pass

    def _cancel_animation(self) -> None:
        if self._root is None or self._animation_job is None:
            return
        try:
            self._root.after_cancel(self._animation_job)
        except tk.TclError:
            pass
        self._animation_job = None

    def _set_alpha(self, alpha: float) -> None:
        if self._root is None:
            return
        self._alpha = max(0.0, min(1.0, alpha))
        try:
            self._root.attributes("-alpha", self._alpha)
        except tk.TclError:
            self._alpha = 1.0 if alpha > 0 else 0.0

    def _fade_to(self, target: float, on_done=None) -> None:
        if self._root is None:
            return

        self._cancel_animation()

        if target > 0:
            self._root.deiconify()
            self._position_centre_top()
            self._apply_no_activate(show=True)

        start = self._alpha
        delta = (target - start) / self.FADE_STEPS if self.FADE_STEPS else 0.0

        def step(index: int = 1) -> None:
            if self._root is None:
                return

            if index > self.FADE_STEPS:
                self._set_alpha(target)
                self._animation_job = None
                if on_done is not None:
                    on_done()
                return

            self._set_alpha(start + (delta * index))
            self._animation_job = self._root.after(self.FADE_INTERVAL_MS, step, index + 1)

        step()

    def _apply_no_activate(self, show: bool) -> None:
        if self._root is None or not sys.platform.startswith("win"):
            return

        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self._root.winfo_id()) or self._root.winfo_id()

        GWL_EXSTYLE = -20
        HWND_TOPMOST = -1
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        SWP_NOOWNERZORDER = 0x0200
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_NOACTIVATE = 0x08000000

        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_FRAMECHANGED
        if show:
            flags |= SWP_SHOWWINDOW

        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)

    def _show_state(self, accent: str, text: str, pulse: bool = False) -> None:
        if self._canvas is None or self._text_id is None:
            return

        glow = self._glow_for_accent(accent)
        self._canvas.itemconfigure(self._text_id, text=text, fill=self.TEXT_COLOUR)
        self._set_indicator(accent, glow, expanded=False)

        if pulse:
            self._start_pulse(accent)
        else:
            self._stop_pulse()
            self._set_indicator(accent, glow, expanded=False)

        self._fade_to(self.TARGET_ALPHA)

    def show_recording(self) -> None:
        """Show the recording state."""
        self._run_on_ui_thread(self._show_state, self.RECORDING_ACCENT, "Recording", True)

    def show_processing(self) -> None:
        """Show the processing state."""
        self._run_on_ui_thread(self._show_state, self.PROCESSING_ACCENT, "Processing...", False)

    def hide(self) -> None:
        """Hide the overlay."""

        def hide_window() -> None:
            self._stop_pulse()
            if self._root is not None:
                self._root.withdraw()

        self._run_on_ui_thread(self._fade_to, 0.0, hide_window)

    def update(self) -> None:
        """Process any pending tkinter work safely from any thread."""

        def flush() -> None:
            if self._root is not None:
                self._root.update_idletasks()

        self._run_on_ui_thread(flush)

    def destroy(self) -> None:
        """Destroy the overlay window."""

        def close() -> None:
            if self._root is None:
                return
            self._stop_pulse()
            self._cancel_animation()
            self._root.quit()

        self._run_on_ui_thread(close)

        if self._thread and self._thread.is_alive() and threading.get_ident() != self._thread.ident:
            self._thread.join(timeout=2)
