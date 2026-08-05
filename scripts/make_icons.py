"""Generate PWA / favicon assets: TT maximized for square taskbar icons."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(r"C:\Users\coincoin\Documents\AudiTT\docs")
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arialbi.ttf"),
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


def render_tt_glyph() -> Image.Image:
    font_px = 1200
    canvas = Image.new("RGBA", (font_px * 3, font_px * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_px)
    # Tighter tracking: draw each T closer (Audi mark is compact)
    t_font = font
    # Measure single T
    tb = draw.textbbox((0, 0), "T", font=t_font)
    tw = tb[2] - tb[0]
    gap = int(tw * -0.08)  # slight overlap / tight kerning
    x0 = font_px // 2
    y0 = font_px // 5
    draw.text((x0, y0), "T", font=t_font, fill=FG)
    draw.text((x0 + tw + gap, y0), "T", font=t_font, fill=FG)
    bbox = canvas.getbbox()
    if not bbox:
        raise RuntimeError("TT glyph empty")
    glyph = canvas.crop(bbox)
    # Squash toward square so it fills taskbar icons (wide italic otherwise leaves empty bands)
    gw, gh = glyph.size
    target_aspect = 1.15  # nearly square
    new_h = max(1, int(gw / target_aspect))
    if new_h > gh:
        # stretch height
        glyph = glyph.resize((gw, new_h), Image.Resampling.LANCZOS)
    else:
        # already tall enough — mild vertical boost
        glyph = glyph.resize((gw, int(gh * 1.25)), Image.Resampling.LANCZOS)
    return glyph


def place_on_square(glyph: Image.Image, size: int, margin_ratio: float = 0.03) -> Image.Image:
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
    frames = [
        place_on_square(glyph, s, margin_ratio=0.02 if s <= 48 else 0.03).convert("RGBA")
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
    glyph = render_tt_glyph()
    print("glyph", glyph.size, "aspect", round(glyph.size[0] / glyph.size[1], 2))

    for size, name, margin in [
        (512, "icon-512.png", 0.03),
        (192, "icon-192.png", 0.03),
        (180, "apple-touch-icon.png", 0.03),
        (48, "favicon-48.png", 0.02),
        (32, "favicon-32.png", 0.02),
        (16, "favicon-16.png", 0.02),
        (192, "icon-maskable-192.png", 0.10),
        (512, "icon-maskable-512.png", 0.10),
    ]:
        place_on_square(glyph, size, margin_ratio=margin).save(OUT / name)
        print("wrote", name)

    write_ico(OUT / "favicon.ico", glyph)
    print("wrote favicon.ico")


if __name__ == "__main__":
    main()
