"""Generate PWA / favicon assets: italic bold TT only."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(r"C:\Users\coincoin\Documents\AudiTT\docs")
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arialbi.ttf"),  # Arial Bold Italic — closest common match to Audi TT
    Path(r"C:\Windows\Fonts\ARIALNBI.TTF"),
    Path(r"C:\Windows\Fonts\impact.ttf"),
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def render_tt(
    size: int,
    *,
    fg=(255, 255, 255, 255),
    bg=(17, 17, 19, 255),
    scale: float = 0.62,
) -> Image.Image:
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)
    font = load_font(int(size * scale))
    text = "TT"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Optical centering for italic glyphs (lean right)
    x = (size - tw) / 2 - bbox[0] - size * 0.02
    y = (size - th) / 2 - bbox[1] - size * 0.04
    draw.text((x, y), text, font=font, fill=fg)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font_used = next((p.name for p in FONT_CANDIDATES if p.exists()), "default")
    print("font", font_used)

    for size, name in [
        (192, "icon-192.png"),
        (512, "icon-512.png"),
        (180, "apple-touch-icon.png"),
        (32, "favicon-32.png"),
        (16, "favicon-16.png"),
    ]:
        render_tt(size).save(OUT / name)
        print("wrote", name)

    for size, name in [(192, "icon-maskable-192.png"), (512, "icon-maskable-512.png")]:
        render_tt(size, scale=0.52).save(OUT / name)
        print("wrote", name)

    render_tt(32).save(OUT / "favicon.ico", format="ICO", sizes=[(32, 32)])
    print("wrote favicon.ico")


if __name__ == "__main__":
    main()
