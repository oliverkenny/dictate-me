from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"
SIZE = 256


def interpolate_channel(start: int, end: int, step: int, max_step: int) -> int:
    return round(start + (end - start) * (step / max_step))


def create_gradient_background() -> Image.Image:
    start = (0x1A, 0x1A, 0x2E)
    end = (0x2D, 0x2D, 0x44)
    image = Image.new("RGBA", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)

    max_step = max((SIZE - 1) * 2, 1)
    for y in range(SIZE):
        for x in range(SIZE):
            step = x + y
            colour = tuple(interpolate_channel(start[i], end[i], step, max_step) for i in range(3))
            draw.point((x, y), fill=colour + (255,))

    return image


def draw_microphone(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    white = (255, 255, 255, 255)

    head = (88, 42, 168, 146)
    draw.rounded_rectangle(head, radius=40, fill=white)

    inner = (102, 58, 154, 132)
    draw.rounded_rectangle(inner, radius=28, outline=(26, 26, 46, 90), width=6)

    draw.rounded_rectangle((118, 142, 138, 192), radius=10, fill=white)
    draw.arc((70, 92, 186, 206), start=200, end=-20, fill=white, width=12)
    draw.rounded_rectangle((84, 194, 172, 208), radius=7, fill=white)
    draw.rounded_rectangle((70, 208, 186, 220), radius=6, fill=white)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image = create_gradient_background()
    draw_microphone(image)
    image.save(
        ICON_PATH,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
