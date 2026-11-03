"""みんなのイラスト: the extra section of a single picture's page (content/item_guides.json), for a picture people search for by itself (2026-11-04: 千歳飴の袋).

The words are written by hand after looking at the picture; every number is computed from the file in the build ({w} {h} {mm300_w} ... below), and the examples are drawn from the
set's own pictures at their own size or smaller (setexamples.render_spec).  An entry: {"title", "description", "heading", "paragraphs": [...], "links": [[label, path]], "examples": [{"name", "caption", "uses", "size", "spec"}]}.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
EXAMPLES_DIR = HERE / "assets" / "examples"


def load() -> dict[str, dict]:
    return json.loads((HERE / "content" / "item_guides.json").read_text(encoding="utf-8"))


GUIDES = load()


def stats(it: dict) -> dict:
    w, h = it["w"], it["h"]
    out = {"w": w, "h": h}
    for dpi in (100, 150, 200, 300):
        out[f"mm{dpi}"] = f"約{round(w / dpi * 25.4)}×{round(h / dpi * 25.4)}mm"
    out["a4_cols"], out["a4_rows"] = int(2480 // w), int(3508 // h)
    out["a4_n"] = out["a4_cols"] * out["a4_rows"]
    out["hagaki_pct"] = round(w / 592 * 100)
    return out


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def meta(item_id: str) -> dict | None:
    return GUIDES.get(item_id)


def item_guide_html(it: dict) -> str:
    g = GUIDES.get(it["id"])
    if not g:
        return ""
    st = stats(it)
    paras = "".join(f"<p>{esc(p.format(**st))}</p>" for p in g["paragraphs"])
    links = '<ul class="check">' + "".join(f'<li><a href="{esc(p)}">{esc(l)}</a></li>' for l, p in g.get("links", [])) + "</ul>" if g.get("links") else ""
    figs = []
    for ex in g["examples"]:
        w, h = Image.open(EXAMPLES_DIR / f"{ex['name']}.webp").size
        figs.append(f'<figure style="margin:0 0 28px"><img src="/assets/examples/{ex["name"]}.webp" alt="{esc(ex["caption"])}" width="{w}" height="{h}" loading="lazy" '
                    f'style="max-width:100%;height:auto;border-radius:8px"><figcaption class="memo-note" style="margin-top:8px">{esc(ex["caption"])}文面は例です。({esc(ex["size"])}、{w}×{h}px)</figcaption></figure>')
    return (f'<section style="margin-top:44px"><h2><span class="scribble">{esc(g["heading"])}</span></h2>{paras}{links}</section>\n'
            f'<section style="margin-top:44px"><h2><span class="scribble">{esc(g["examples_heading"])}</span></h2>{"".join(figs)}</section>')


def render_all() -> list[str]:
    """Draw every example that has a "spec" into assets/examples/ (python sites/minna/itemguides.py)."""
    import sys
    sys.path.insert(0, str(HERE))
    import setexamples
    done = []
    for item_id, g in GUIDES.items():
        slug = item_id.rsplit("-", 1)[0]
        for ex in g["examples"]:
            if ex.get("spec"):
                setexamples.save(setexamples.render_spec(slug, ex["spec"]), ex["name"])
                done.append(ex["name"])
    return done


if __name__ == "__main__":
    render_all()
