"""One-off: draws the site icons (a calendar) with Pillow, no fonts needed.   python sites/atomou/make_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "assets"
BLUE, WHITE, ORANGE = (29, 78, 216, 255), (255, 255, 255, 255), (234, 119, 40, 255)


def icon(size: int) -> Image.Image:
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=BLUE)
    m = int(s * 0.17)
    d.rounded_rectangle([m, int(s * 0.24), s - m, s - m], radius=int(s * 0.07), fill=WHITE)
    d.rectangle([m, int(s * 0.24), s - m, int(s * 0.40)], fill=ORANGE)
    d.rounded_rectangle([m, int(s * 0.24), s - m, int(s * 0.40)], radius=int(s * 0.07), fill=ORANGE)
    d.rectangle([m, int(s * 0.33), s - m, int(s * 0.40)], fill=ORANGE)
    for cx in (0.34, 0.66):
        d.rounded_rectangle([int(s * (cx - 0.035)), int(s * 0.15), int(s * (cx + 0.035)), int(s * 0.30)], radius=int(s * 0.03), fill=WHITE)
    # three bars: "あと" "もう" read as lines of a note
    for i, w in enumerate((0.52, 0.40, 0.46)):
        y = int(s * (0.50 + i * 0.12))
        d.rounded_rectangle([int(s * 0.27), y, int(s * (0.27 + w)), y + int(s * 0.055)], radius=int(s * 0.027), fill=BLUE)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    icon(32).save(OUT / "favicon-32.png")
    icon(180).save(OUT / "apple-touch-icon.png")
    icon(48).save(OUT / "favicon.ico", sizes=[(48, 48)])
    icon(192).save(OUT / "icon-192.png")
    icon(512).save(OUT / "icon-512.png")
    print("icons written")
