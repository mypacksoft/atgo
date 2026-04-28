"""Render icon.png + banner.png for the Odoo Apps Store listing.

Output:
    apps/atgo_connect/static/description/icon.png      256 x 256
    apps/atgo_connect/static/description/banner.png   1280 x 480

Pure Pillow drawing, no external assets. Re-runnable.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "apps" / "atgo_connect" / "static" / "description"
OUT.mkdir(parents=True, exist_ok=True)

ACCENT = (99, 102, 241)        # indigo-500
ACCENT_DARK = (67, 56, 202)    # indigo-700
ACCENT_LIGHT = (165, 180, 252) # indigo-300
BG = (15, 23, 42)              # slate-900
PANEL = (30, 41, 59)           # slate-800
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)        # slate-400


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try common system fonts. Bold variant when requested."""
    candidates_bold = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in (candidates_bold if bold else candidates):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _gradient_bg(size, top, bottom):
    """Vertical gradient image."""
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


# ============================================================
# ICON 256 x 256 — solid rounded square + bold "A" + clock dot
# ============================================================

def make_icon(path: Path) -> None:
    size = 256
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # Rounded panel with subtle inner gradient
    grad = _gradient_bg((size, size), ACCENT, ACCENT_DARK)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((6, 6, size - 6, size - 6), radius=44, fill=255)
    img.paste(grad, mask=mask)

    # Soft white inner glow
    glow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow).rounded_rectangle((20, 20, size - 20, size - 20), radius=36, fill=80)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
    overlay = Image.new("RGB", (size, size), WHITE)
    img.paste(overlay, mask=glow)

    # Bold "A" centered
    f_a = _font(168, bold=True)
    bbox = d.textbbox((0, 0), "A", font=f_a)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx = (size - tw) // 2 - bbox[0]
    cy = (size - th) // 2 - bbox[2 if False else 1] - 12
    # Drop shadow
    d.text((cx + 4, cy + 4), "A", font=f_a, fill=(0, 0, 0, 90))
    d.text((cx, cy), "A", font=f_a, fill=WHITE)

    # Tiny clock-tick (punch-in dot) under the A
    tick_y = size - 70
    d.ellipse((size // 2 - 8, tick_y, size // 2 + 8, tick_y + 16), fill=WHITE)

    img.save(path, "PNG", optimize=True)
    print(f"  wrote {path.relative_to(HERE)} ({path.stat().st_size // 1024} KB)")


# ============================================================
# BANNER 1280 x 480
# ============================================================

def make_banner(path: Path) -> None:
    w, h = 1280, 480

    # Diagonal gradient background
    bg = _gradient_bg((w, h), (37, 33, 99), (8, 11, 38))
    img = bg.copy()
    d = ImageDraw.Draw(img, "RGBA")

    # Decorative blurred blobs for depth
    blob = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    bd.ellipse((w - 600, -200, w + 100, 500), fill=(99, 102, 241, 110))
    bd.ellipse((-200, h - 300, 400, h + 200), fill=(168, 85, 247, 80))
    blob = blob.filter(ImageFilter.GaussianBlur(radius=100))
    img.paste(blob, (0, 0), blob)
    d = ImageDraw.Draw(img, "RGBA")

    # Logo block: rounded square + "A"
    pad = 60
    logo_size = 140
    _rounded_rect(d, (pad, pad, pad + logo_size, pad + logo_size),
                   radius=28, fill=ACCENT)
    fa = _font(110, bold=True)
    bbox = d.textbbox((0, 0), "A", font=fa)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((pad + (logo_size - tw) // 2 - bbox[0],
            pad + (logo_size - th) // 2 - bbox[1] - 6),
           "A", font=fa, fill=WHITE)

    # Headline + sub
    f_title = _font(72, bold=True)
    f_sub = _font(34)
    f_small = _font(24)

    text_x = pad + logo_size + 36
    d.text((text_x, pad + 8), "ATGO Connect", font=f_title, fill=WHITE)
    d.text((text_x, pad + 100),
           "Cloud attendance for ZKTeco devices",
           font=f_sub, fill=ACCENT_LIGHT)

    # Tagline below
    tagline_y = h - 160
    d.text((pad, tagline_y),
           "No static IP   .   No port forwarding   .   No local server",
           font=f_sub, fill=WHITE)
    d.text((pad, tagline_y + 56),
           "Pulls punches into hr.attendance every 5 minutes",
           font=f_small, fill=MUTED)

    # Right-side pill row "Odoo 16 / 17 / 18 / 19"
    versions = ["Odoo 16", "Odoo 17", "Odoo 18", "Odoo 19"]
    pill_y = pad + 16
    pill_x = w - pad
    for v in reversed(versions):
        bbox = d.textbbox((0, 0), v, font=f_small)
        tw = bbox[2] - bbox[0]
        pad_x, pad_y = 18, 10
        right = pill_x
        left = right - tw - 2 * pad_x
        _rounded_rect(d, (left, pill_y, right, pill_y + 44),
                       radius=22, fill=(255, 255, 255, 30),
                       outline=(255, 255, 255, 80), width=1)
        d.text((left + pad_x, pill_y + pad_y - bbox[1]), v,
               font=f_small, fill=WHITE)
        pill_x = left - 12

    # Bottom-right small "atgo.io"
    f_url = _font(22, bold=True)
    bbox = d.textbbox((0, 0), "atgo.io", font=f_url)
    d.text((w - pad - (bbox[2] - bbox[0]), h - pad - 28),
           "atgo.io", font=f_url, fill=WHITE)

    img.save(path, "PNG", optimize=True)
    print(f"  wrote {path.relative_to(HERE)} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    print("Rendering Odoo Apps assets...")
    make_icon(OUT / "icon.png")
    make_banner(OUT / "banner.png")
    print("Done.")


if __name__ == "__main__":
    main()
