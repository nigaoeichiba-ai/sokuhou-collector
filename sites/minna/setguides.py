"""みんなのイラスト: the 使い分けのガイド of a featured set (/series/<slug>/).

A featured set gets what a list of pictures cannot say by itself: which picture is for what, how big each one really prints, where a frame is empty, and a few finished examples made
only from the set's own pictures (setexamples.py).  The words are written by hand for each set after looking at every picture; every number is measured from the files in the build.
Nothing here is said about print quality that has not been measured: the print sizes are the pixels divided by the dpi, nothing more.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
EXAMPLES_DIR = HERE / "assets" / "examples"


def inner_box(im: Image.Image, alpha_max: int = 24) -> tuple[int, int, int, int]:
    """The biggest empty (transparent) rectangle that grows from the centre of a picture, as (x0, y0, x1, y1) in the picture's own pixels: where a frame lets a photo or a text show."""
    a = np.array(im.convert("RGBA"))[:, :, 3] > alpha_max
    h, w = a.shape
    x0, x1, y0, y1 = w // 2, w // 2 + 1, h // 2, h // 2 + 1
    if a[h // 2, w // 2]:
        return (w // 2, h // 2, w // 2, h // 2)
    grown = True
    while grown:
        grown = False
        if x0 > 0 and not a[y0:y1, x0 - 1].any():
            x0 -= 1
            grown = True
        if x1 < w and not a[y0:y1, x1].any():
            x1 += 1
            grown = True
        if y0 > 0 and not a[y0 - 1, x0:x1].any():
            y0 -= 1
            grown = True
        if y1 < h and not a[y1, x0:x1].any():
            y1 += 1
            grown = True
    return (x0, y0, x1, y1)


def blank_box(im: Image.Image, kind: str = "cream") -> tuple[int, int, int, int] | None:
    """The biggest plain rectangle of a picture that can be written on (a name tag, a podium, a white board), as (x0, y0, x1, y1), or None.
    kind 'cream': the cream of a tag (R>245, G>235, 195<B<245); 'white': a near-white board.  A part counts when it fills at least 80% of its bounding box and is wider than 1.3 times its height."""
    import numpy as np
    from scipy import ndimage
    a = np.array(im.convert("RGBA")).astype(int)
    if kind == "white":
        m = (a[:, :, 3] > 200) & (a[:, :, 0] > 245) & (a[:, :, 1] > 240) & (a[:, :, 2] > 225)
    else:
        m = (a[:, :, 3] > 200) & (a[:, :, 0] > 245) & (a[:, :, 1] > 235) & (a[:, :, 2] > 195) & (a[:, :, 2] < 245)
    lab, k = ndimage.label(m)
    best = None
    for i in range(1, k + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 2500:
            continue
        w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if len(ys) / (w * h) > 0.80 and w / h > 1.3 and (best is None or len(ys) > best[0]):
            best = (len(ys), int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return best[1:] if best else None


def mm(px: int, dpi: int) -> int:
    return round(px / dpi * 25.4)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# slug -> the words of the set: library/<slug>/guide.json (one file per set; the factory writes it with the set).  Keys:
#   why       the set in two sentences (40+ characters)
#   frame     true when the pictures are frames (adds the column "中の空き")
#   blank     "cream" when the pictures hold a name tag or a board to write on (adds the column "書き込める白い面")
#   picks     {id without "<slug>-": one line on what the picture is for}: every picture of the set has one
#   points    4+ paragraphs (450+ characters together) on how to use the set.  {n} {wmin} {wmax} {hmin} {hmax} {wide} {tall} {dpi30} {dpi_a4} {wmax_mm} {hmin_mm} {hmax_mm} {dpi60} are measured;
#             {iw_min} {iw_max} {ih_min} {ih_max} {chars24} {lines24} {ratio_max} for frames; {blank_lion} for the set with a lion-medal picture
#   links     [[label, path], ...] pages of the site the paragraphs talk about (optional)
#   examples  2+ of {"name", "caption", "uses": [picture ids], "size", "spec": {...} (optional: how setexamples.py draws it)}; assets/examples/<name>.webp must exist
def load_guides() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted((HERE / "library").glob("*/guide.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        g.setdefault("frame", False)
        g["examples"] = [(e["name"], e["caption"], e.get("uses", []), e.get("size", "")) for e in g.get("examples", [])]
        g["links"] = [tuple(x) for x in g.get("links", [])]
        out[f.parent.name] = g
    return out


GUIDES: dict[str, dict] = load_guides()


def guide_stats(its: list[dict], g: dict) -> dict:
    """The numbers a guide's paragraphs may use ({n}, {wmin}, {iw_min}, ...), measured from the set's pictures."""
    ws, hs = [i["w"] for i in its], [i["h"] for i in its]
    stats = {"n": len(its), "wmin": min(ws), "wmax": max(ws), "hmin": min(hs), "hmax": max(hs), "wide": sum(1 for i in its if i["w"] > i["h"] * 1.15), "tall": sum(1 for i in its if i["h"] > i["w"] * 1.15),
             "dpi30": round(min(ws) / (30 / 25.4)), "dpi_a4": round(max(ws) / (210 / 25.4)), "wmax_mm": mm(max(ws), 300)}
    stats.update({"hmin_mm": mm(min(hs), 300), "hmax_mm": mm(max(hs), 300), "dpi60": round(min(hs) / (60 / 25.4))})
    if g["frame"]:
        boxes = [inner_box(Image.open(i["path"])) for i in its]
        iws, ihs = [b[2] - b[0] for b in boxes], [b[3] - b[1] for b in boxes]
        stats.update({"iw_min": min(iws), "iw_max": max(iws), "ih_min": min(ihs), "ih_max": max(ihs), "chars24": min(iws) // 24, "lines24": int(min(ihs) // (24 * 1.5)),
                      "ratio_max": f"{max(w / h for w, h in zip(iws, ihs)):.1f}:1"})
    lion = next((i for i in its if i["id"].endswith("-lion-medal")), None)
    if lion is not None:
        bb = blank_box(Image.open(lion["path"]), "cream")
        stats["blank_lion"] = f"{bb[2] - bb[0] + 1}×{bb[3] - bb[1] + 1}" if bb else "なし"
    return stats


def set_guide_html(s: dict) -> str:
    """The 使い分けのガイド section of a featured set, or '' for the other sets."""
    g = GUIDES.get(s["slug"])
    if not g:
        return ""
    slug = s["slug"]
    its = s["items"]
    by_key = {i["id"][len(slug) + 1:]: i for i in its}
    assert set(g["picks"]) == set(by_key), f"{slug}: a picture without a line or a line without a picture: {set(g['picks']) ^ set(by_key)}"
    head = ["素材", "使いどころ", "大きさ(px)", "300dpiで印刷すると"] + (["中の空き(px)"] if g["frame"] else []) + (["書き込める白い面(px)"] if g.get("blank") else [])
    rows = []
    for key, it in by_key.items():
        cells = [f'<a href="/illust/{it["id"]}/">{esc(it["title"])}</a>', esc(g["picks"][key]), f'{it["w"]}×{it["h"]}',
                 f'約{mm(it["w"], 300)}×{mm(it["h"], 300)}mm']
        if g["frame"]:
            x0, y0, x1, y1 = inner_box(Image.open(it["path"]))
            cells.append(f"{x1 - x0}×{y1 - y0}")
        if g.get("blank"):
            b = blank_box(Image.open(it["path"]), g["blank"])
            cells.append(f"{b[2] - b[0] + 1}×{b[3] - b[1] + 1}" if b else "なし")
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    table = f'<div class="tablewrap"><table><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    ws, hs = [i["w"] for i in its], [i["h"] for i in its]
    size_note = (f"どの素材も幅{min(ws)}〜{max(ws)}px、高さ{min(hs)}〜{max(hs)}pxです。300dpiの印刷なら約{mm(min(ws), 300)}〜{mm(max(ws), 300)}mm×{mm(min(hs), 300)}〜{mm(max(hs), 300)}mmで、"
                 f"はがき(幅100mm)に載せるなら、150dpi(幅約591px)で作る画面にそのまま置けます。A4の幅(210mm)いっぱいまで広げると、{round(max(ws) / 210 * 25.4)}dpi前後になり、"
                 "線が粗く見えます。小さめに置くか、大きく使うときは試し刷りで確かめてください。")
    ex_html = []
    for name, caption, uses, size_label in g["examples"]:
        f = EXAMPLES_DIR / f"{name}.webp"
        w, h = Image.open(f).size
        used = "、".join(f'<a href="/illust/{u}/">{esc(next(i["title"] for i in its if i["id"] == u))}</a>' for u in uses[:3]) + ("ほか" if len(uses) > 3 else "")
        ex_html.append(f'<figure style="margin:0 0 28px"><img src="/assets/examples/{name}.webp" alt="{esc(caption)}" width="{w}" height="{h}" loading="lazy" '
                       f'style="max-width:100%;height:auto;border-radius:8px"><figcaption class="memo-note" style="margin-top:8px">{esc(caption)}文面は例です。'
                       f'({size_label}、{w}×{h}px)使った素材: {used}</figcaption></figure>')
    frame_note = ""
    if g["frame"]:
        frame_note = "<p>「中の空き」は、枠の真ん中で透明になっている、いちばん大きい四角の大きさです。文字や写真は、この中に収めると枠にかかりません。</p>"
    blank_note = ""
    if g.get("blank"):
        blank_note = "<p>「書き込める白い面」は、名前や文字を書き足せる、四角い白(クリーム色)の部分のいちばん大きいものの大きさです。</p>"
    stats = guide_stats(its, g)
    points = "".join(f"<p>{esc(p.format(**stats))}</p>" for p in g.get("points", []))
    points_html = f'<section style="margin-top:44px"><h2><span class="scribble">使い方のコツ</span></h2>{points}' + (
        '<ul class="check">' + "".join(f'<li><a href="{esc(h)}">{esc(l)}</a></li>' for l, h in g["links"]) + "</ul>" if g.get("links") else "") + "</section>" if points else ""
    return f"""<section style="margin-top:44px"><h2><span class="scribble">このセットの使い分け</span></h2>
<p>{esc(g['why'])}</p>
{table}
{frame_note}{blank_note}<p>{esc(size_note)}</p></section>
{points_html}
<section style="margin-top:44px"><h2><span class="scribble">このセットだけで作った例</span></h2>
{"".join(ex_html)}
<p class="memo-note">見本の絵と文字は、このセットの素材と文字だけで作りました。素材は元の大きさのまま(拡大なし)で、日付は空欄です。素材は、このページ上のまとめて保存ボタンや各素材のページから、ずっと無料・商用OK・クレジット不要で保存できます。詳しい条件は<a href="/license/">利用について</a>へ。</p></section>"""
