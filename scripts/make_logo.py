from PIL import Image
import os

src = r"C:\Users\coincoin\Documents\audi.png"
out_dir = r"C:\Users\coincoin\Documents\AudiTT\docs"
os.makedirs(out_dir, exist_ok=True)

im = Image.open(src).convert("RGBA")
w, h = im.size
pixels = im.load()

# Aggressive chroma-key: anything light becomes transparent; dark stays black.
out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
op = out.load()
for y in range(h):
    for x in range(w):
        r, g, b, a = pixels[x, y]
        brightness = (r + g + b) / 3.0
        # Soft alpha based on darkness
        if brightness >= 245:
            alpha = 0
        elif brightness >= 200:
            alpha = int((245 - brightness) / 45 * 255)
        else:
            alpha = 255
        if alpha <= 0:
            continue
        # Force pure black logo strokes
        op[x, y] = (0, 0, 0, alpha)

bbox = out.getbbox()
if bbox:
    # pad a little
    x0, y0, x1, y1 = bbox
    pad = 4
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(w, x1 + pad)
    y1 = min(h, y1 + pad)
    out = out.crop((x0, y0, x1, y1))

out.save(os.path.join(out_dir, "logo.png"))

# Square app icons: place wide logo centered on transparent square
iw, ih = out.size
side = max(iw, ih, 512)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
scale = min((side * 0.88) / iw, (side * 0.45) / ih)
nw, nh = int(iw * scale), int(ih * scale)
scaled = out.resize((nw, nh), Image.Resampling.LANCZOS)
canvas.paste(scaled, ((side - nw) // 2, (side - nh) // 2), scaled)

for size, name in [
    (192, "icon-192.png"),
    (512, "icon-512.png"),
    (180, "apple-touch-icon.png"),
    (32, "favicon-32.png"),
    (16, "favicon-16.png"),
]:
    canvas.resize((size, size), Image.Resampling.LANCZOS).save(os.path.join(out_dir, name))

# Maskable: black logo on dark charcoal circle-ish square
for size, name in [(192, "icon-maskable-192.png"), (512, "icon-maskable-512.png")]:
    bg = Image.new("RGBA", (size, size), (20, 20, 22, 255))
    mark = canvas.resize((size, size), Image.Resampling.LANCZOS)
    # invert logo to white for dark bg
    px = mark.load()
    inv = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ip = inv.load()
    for yy in range(size):
        for xx in range(size):
            r, g, b, a = px[xx, yy]
            if a > 20:
                ip[xx, yy] = (255, 255, 255, a)
    bg.paste(inv, (0, 0), inv)
    bg.save(os.path.join(out_dir, name))

canvas.resize((32, 32), Image.Resampling.LANCZOS).save(
    os.path.join(out_dir, "favicon.ico"), format="ICO", sizes=[(32, 32)]
)
print("logo ok", out.size)
