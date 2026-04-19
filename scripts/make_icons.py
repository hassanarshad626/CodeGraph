"""Generate app icons from a procedurally drawn hexagon logo.

Outputs:
  electron/icon.png  (512x512 — used by BrowserWindow + tray on macOS/Linux)
  electron/icon.ico  (Windows multi-res icon for the app + taskbar + tray)
  electron/icon_tray.png  (32x32 tray-sized PNG)

Run:  python scripts/make_icons.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "electron"
OUT.mkdir(exist_ok=True)


def _hexagon(size: int, fill: tuple, outline: tuple) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size / 2
    r = size * 0.42
    # Flat-top hexagon
    pts = [
        (cx + r * math.cos(math.radians(60 * i)),
         cy + r * math.sin(math.radians(60 * i)))
        for i in range(6)
    ]
    d.polygon(pts, fill=fill, outline=outline, width=max(2, size // 64))

    # Inner graph dots + connecting lines
    dot_r = max(2, size // 42)
    dots = [
        (cx, cy - r * 0.45),
        (cx - r * 0.45, cy - r * 0.12),
        (cx + r * 0.45, cy - r * 0.12),
        (cx - r * 0.30, cy + r * 0.40),
        (cx + r * 0.30, cy + r * 0.40),
    ]
    line_w = max(2, size // 100)
    for i in range(len(dots)):
        for j in range(i + 1, len(dots)):
            if (i + j) % 2 == 0:
                d.line([dots[i], dots[j]], fill=(255, 255, 255, 90), width=line_w)
    for (x, y) in dots:
        d.ellipse((x - dot_r, y - dot_r, x + dot_r, y + dot_r),
                  fill=(255, 255, 255, 230))
    return img


def _with_glow(hex_img: Image.Image, size: int, glow_color=(123, 211, 234)) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (15, 17, 23, 0))
    # Soft glow behind the hex
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx = cy = size / 2
    gr = size * 0.48
    gd.ellipse((cx - gr, cy - gr, cx + gr, cy + gr),
               fill=(*glow_color, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size // 10))
    canvas = Image.alpha_composite(canvas, glow)
    canvas = Image.alpha_composite(canvas, hex_img)
    return canvas


def make_png(size: int) -> Image.Image:
    hex_img = _hexagon(size, fill=(123, 211, 234, 255), outline=(255, 255, 255, 200))
    return _with_glow(hex_img, size)


def main():
    # Main app icon
    big = make_png(512)
    big.save(OUT / "icon.png", "PNG")
    print(f"wrote {OUT / 'icon.png'}")

    # Tray icon — keep it small and sharp; no glow because tray rescales it.
    tray_hex = _hexagon(64, fill=(123, 211, 234, 255), outline=(255, 255, 255, 220))
    tray = tray_hex.resize((32, 32), Image.LANCZOS)
    tray.save(OUT / "icon_tray.png", "PNG")
    print(f"wrote {OUT / 'icon_tray.png'}")

    # Windows multi-res .ico
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    frames = [make_png(s[0]) for s in ico_sizes]
    frames[0].save(OUT / "icon.ico", format="ICO", sizes=ico_sizes,
                   append_images=frames[1:])
    print(f"wrote {OUT / 'icon.ico'}")


if __name__ == "__main__":
    main()
