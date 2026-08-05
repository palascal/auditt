"""Generate PWA / favicon assets: oversized italic TT filling the icon."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(r"C:\Users\coincoin\Documents\AudiTT\docs")
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arialbi.ttf"),  # Bold Italic — closest to Audi TT mark
    Path(r"C:\Windows\Fonts\ARIALNBI.TTF"),
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
]
BG = (12, 12, 14, 255)
FG = (255, 255, 255, 255)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def render_tt_glyph(font_px: int = 900) -> Image.Image:
    """Render TT on a transparent canvas large enough for italic overflow."""
    canvas = Image.new("RGBA", (font_px * 3, font_px * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_px)
    draw.text((font_px // 2, font_px // 4), "TT", font=font, fill=FG)
    bbox = canvas.getbbox()
    if not bbox:
        raise RuntimeError("TT glyph empty")
    return canvas.crop(bbox)


def place_on_square(glyph: Image.Image, size: int, margin_ratio: float = 0.04) -> Image.Image:
    """Scale glyph to nearly fill the square (tiny margin for Windows anti-alias)."""
    out = Image.new("RGBA", (size, size), BG)
    margin = max(1, int(size * margin_ratio))
    max_w = size - 2 * margin
    max_h = size - 2 * margin
    gw, gh = glyph.size
    scale = min(max_w / gw, max_h / gh)
    nw, nh = max(1, int(gw * scale)), max(1, int(gh * scale))
    scaled = glyph.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (size - nw) // 2
    y = (size - nh) // 2
    out.paste(scaled, (x, y), scaled)
    return out


def write_ico(path: Path, glyph: Image.Image) -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    # Tiny sizes: almost no margin so TT stays readable in the taskbar
    frames = [
        place_on_square(glyph, s, margin_ratio=0.02 if s <= 32 else 0.04).convert("RGBA")
        for s in sizes
    ]
    frames[-1].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[:-1],
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font_used = next((p.name for p in FONT_CANDIDATES if p.exists()), "default")
    print("font", font_used)
    glyph = render_tt_glyph(1000)
    print("glyph", glyph.size)

    for size, name, margin in [
        (512, "icon-512.png", 0.04),
        (192, "icon-192.png", 0.04),
        (180, "apple-touch-icon.png", 0.04),
        (48, "favicon-48.png", 0.03),
        (32, "favicon-32.png", 0.02),
        (16, "favicon-16.png", 0.02),
        (192, "icon-maskable-192.png", 0.12),  # safe zone for maskable
        (512, "icon-maskable-512.png", 0.12),
    ]:
        place_on_square(glyph, size, margin_ratio=margin).save(OUT / name)
        print("wrote", name)

    write_ico(OUT / "favicon.ico", glyph)
    print("wrote favicon.ico")


if __name__ == "__main__":
    main()
