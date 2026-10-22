"""Render the existing engineering brand as a crisp multi-resolution Windows icon."""

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    size = 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (20, 20, 1004, 1004), radius=210, fill="#161b20", outline="#48535c", width=12
    )
    # Three isotherms through an offset Gaussian peak, matching the Studio mark.
    for y, width in ((320, 290), (510, 420), (700, 290)):
        draw.rounded_rectangle(
            (512 - width, y - 36, 512 + width, y + 36), radius=36, fill="#c9d4dc"
        )
    draw.rounded_rectangle((462, 234, 562, 786), radius=40, fill="#91a5b5")
    output = Path(__file__).resolve().parents[1] / "desktop"
    output.mkdir(exist_ok=True)
    image.save(output / "neuralheat.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    image.resize((256, 256), Image.Resampling.LANCZOS).save(output / "neuralheat.png")


if __name__ == "__main__":
    main()
