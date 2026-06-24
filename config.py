"""Configuration for dictation-me."""

# Whisper model settings
MODEL_SIZE = "base"  # Options: tiny, base, small, medium, large-v3
COMPUTE_TYPE = "int8"  # Options: int8, float16, float32
DEVICE = "cpu"  # Options: cpu, cuda

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1

# Hotkey
HOTKEY = "ctrl+space"

# UI settings
OVERLAY_WIDTH = 200
OVERLAY_HEIGHT = 40
OVERLAY_BG_RECORDING = "#e74c3c"
OVERLAY_BG_PROCESSING = "#f39c12"
OVERLAY_BG_READY = "#2ecc40"
OVERLAY_FONT_SIZE = 12
OVERLAY_FONT_COLOUR = "#ffffff"
