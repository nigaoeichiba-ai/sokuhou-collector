"""みんなのイラスト: what a picture page can say about this picture alone, from the numbers measured in facts.py.

  similar_map  the pictures of OTHER sets whose main colours and shape are closest (one per set), nearest first: "色と形が近いイラスト";
  tip_lines    a few sentences on how to use this picture: which backgrounds to choose, how big it prints, what to do about its margin, what its shape suits.

Every sentence is chosen by a measured value and says nothing the numbers do not show; nothing here names how the picture was made.
"""
from __future__ import annotations

from sites.minna import facts

NEAR = 6                # pictures shown
SHAPE_PENALTY = 0.25    # added to the distance when the shapes differ
FILL_WEIGHT = 0.3       # weight of the difference of the filled shares (0..1)


def colour_vector(f: dict) -> dict[str, float]:
    return {n: p / 100 for n, p in f["colors"]}


def distance(a: dict, b: dict, shape_a: str, shape_b: str) -> float:
    va, vb = colour_vector(a), colour_vector(b)
    d = sum(abs(va.get(k, 0) - vb.get(k, 0)) for k in set(va) | set(vb))
    d += SHAPE_PENALTY if shape_a != shape_b else 0
    d += FILL_WEIGHT * abs(a["fill"] - b["fill"]) / 100
    return d


def similar_map(items: list[dict], facts_of) -> dict[str, list[tuple[str, float]]]:
    """{item id: [(other id, distance), ...]} nearest first, at most one picture per other set, never the picture itself or a picture of its own set."""
    info = {i["id"]: (facts_of(i), facts.shape(i["w"], i["h"]), i["series"]) for i in items}
    by_colour: dict[str, list[str]] = {}
    for i in items:
        for name, _p in info[i["id"]][0]["colors"][:2]:
            by_colour.setdefault(name, []).append(i["id"])
    out: dict[str, list[tuple[str, float]]] = {}
    for i in items:
        f, shape, series = info[i["id"]]
        pool = {c for name, _p in f["colors"][:2] for c in by_colour.get(name, ())}
        scored = sorted((distance(f, info[c][0], shape, info[c][1]), c) for c in pool if info[c][2] != series)
        picked, used = [], set()
        for d, c in scored:
            if info[c][2] in used:
                continue
            used.add(info[c][2])
            picked.append((c, round(d, 3)))
            if len(picked) == NEAR:
                break
        out[i["id"]] = picked
    return out


def tip_lines(it: dict, f: dict) -> list[str]:
    """The how-to-use sentences of one picture, chosen by its measured values."""
    w, h = it["w"], it["h"]
    low = f["bg_low"]
    bad = [n for n, v in low.items() if v >= 30]
    good = [n for n, v in low.items() if v < 15]
    light = [n for n in bad if n != "黒"]
    lines = []
    # 1. which background
    if not bad:
        lines.append("輪郭はどの背景でも見分けられるので、背景色は紙面や画面の色に合わせて決められます。")
    elif bad == ["黒"]:
        lines.append("黒の背景に置くと輪郭が沈みます。絵の周りに白い縁を付けるか、白・黄・桃・空の上に置きます。")
    elif light and good:
        lines.append("輪郭が" + "・".join(light) + "の背景に近い色で、沈みます。" + "・".join(good) + "の上に置くか、絵の周りに濃い縁を付けます。")
    else:
        lines.append("輪郭が背景に近い色になりやすい絵です。置くときは絵の周りに白か黒の縁を付けます。")
    # 2. print size
    w3, h3, w1, h1 = facts.mm(w, 300), facts.mm(h, 300), facts.mm(w, 150), facts.mm(h, 150)
    size = f"300dpiで約{w3:.0f}×{h3:.0f}mm、150dpiで約{w1:.0f}×{h1:.0f}mmの大きさに印刷できます。150dpiの幅はA4用紙の幅(210mm)の約{round(100 * w1 / 210)}%です。"
    if w1 >= 100:
        size += "150dpiでもはがきの幅(100mm)を超えるので、紙面いっぱいに使えます。"
    else:
        size += f"はがきの幅(100mm)いっぱいに使うと約{round(100 / w1, 1)}倍の拡大になり、細かい線が粗くなります。"
    lines.append(size)
    # 3. margin
    if f["fill"] < 45:
        lines.append(f"絵が画像の面積の{f['fill']}%で余白が広めです。大きく使うなら余白を切り落としてから配置します。")
    elif f["fill"] >= 75:
        lines.append(f"絵が画像の面積の{f['fill']}%を占め、余白がほとんどありません。縁ぎりぎりに置かず周りを少し空けて配置します。")
    # 4. shape
    s = facts.shape(w, h)
    if s == "横長":
        lines.append("横長なので、見出しの横やスライド下の帯など、横に広い場所に合います。")
    elif s == "縦長":
        lines.append("縦長なので縦書きの文章の横やスマホの画面に合います。")
    else:
        lines.append("ほぼ正方形なので、SNSのアイコンや1080px四方の枠にそのまま保存できます。")
    return lines
