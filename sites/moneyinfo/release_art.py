"""Package only the bitmap data used by the generated release pages."""

from io import BytesIO
import re

from PIL import Image


ART = re.compile(
    r'(<svg\b[^>]*\bviewBox="(\d+) (\d+) (\d+) (\d+)"[^>]*>\s*)'
    r'<image href="(assets/(approved-[^"]+\.webp))" width="\d+" height="\d+"\s*/>'
)
ASSET_REFERENCE = re.compile(r'assets/([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)')
SOURCE_ART = ("approved-article-mobile.webp", "approved-article-pc.webp", "article-home.webp",
              "brand-mark.webp", "care-hands.png", "care-heart.svg", "hero.webp")


def trim_category_art(output):
    """Keep SVG coordinates and decoded pixels. A border retains adjacent samples."""
    assets = output / "assets"
    inputs = {}
    for slug in ("cases", "events", "guide", "tools-category"):
        page = output / f"{slug}.html"

        def crop(match):
            prefix, x, y, width, height, _, name = match.groups()
            if name not in inputs:
                with Image.open(assets / name) as original:
                    inputs[name] = original.convert("RGBA")
            original = inputs[name]
            x, y, width, height = map(int, (x, y, width, height))
            pad = 2
            left, top = max(0, x - pad), max(0, y - pad)
            region = (left, top, min(original.width, x + width + pad),
                      min(original.height, y + height + pad))
            target = assets / f"{name.removesuffix('.webp')}-{x}-{y}-{width}-{height}.webp"
            if not target.exists():
                cut = original.crop(region)
                cut.save(target, lossless=True, quality=100, method=6, exact=True,
                         icc_profile=original.info.get("icc_profile"))
            return (f'{prefix}<image href="assets/{target.name}" x="{left}" y="{top}" '
                    f'width="{region[2] - left}" height="{region[3] - top}"/>')

        html = page.read_text(encoding="utf-8")
        page.write_text(ART.sub(crop, html), encoding="utf-8")


def optimize_release_art(output):
    trim_category_art(output)
    references = set()
    for file in output.rglob("*"):
        if file.suffix in {".html", ".css", ".js", ".mjs"}:
            references.update(ASSET_REFERENCE.findall(file.read_text(encoding="utf-8")))
    assets = output / "assets"
    for name in SOURCE_ART:
        if name not in references:
            (assets / name).unlink(missing_ok=True)
    icon = assets / "site-icon.webp"
    with Image.open(icon) as original:
        candidate = BytesIO()
        original.save(candidate, format="WEBP", lossless=True, quality=100,
                      method=6, exact=True, icc_profile=original.info.get("icc_profile"))
    if candidate.tell() < icon.stat().st_size:
        icon.write_bytes(candidate.getvalue())
