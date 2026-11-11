"""Turns Muse's approved product-page prototype (an HTML file) into the JSON that the redesign's product template reads.

    python -X utf8 sites/kaidoki/redesign/tools/extract_product.py <prototype.html> [--out sites/kaidoki/private/products/iphone-18-pro.json]

The JSON holds store campaign conditions and the stores' own page addresses, among them an Amazon product page.  Under the owner's rule (the public
repository takes no mall product information) it is NOT committed: the default output folder is git-ignored, and the build reads it from there when it is
present (the page simply does not exist when it is not).  The wording is Muse's, copied as it stands; the site name in the title and the sentence that
sends the reader to "the public site's calculator" (the page now lives on the site) are handled by the renderer, not here.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


def txt(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def extract(src: str, slug: str = "iphone-18-pro") -> dict:
    title = txt(re.search(r"<title>(.*?)</title>", src, re.S).group(1))
    title = re.sub(r"[｜|]買い時カレンダー.*$", "", title)
    hero = re.search(r'<header class="hero">(.*?)</header>', src, re.S).group(1)
    kicker = txt(re.search(r'class="kicker">(.*?)</span>', hero, re.S).group(1)).split("｜")[0].strip()
    h1 = re.search(r"<h1>(.*?)</h1>", hero, re.S).group(1).strip()
    sub = txt(re.search(r"</h1>\s*<p>(.*?)</p>", hero, re.S).group(1))
    meta = txt(re.search(r'class="meta">(.*?)</span>', hero, re.S).group(1))
    lead = txt(re.search(r'<p class="lead">(.*?)</p>', src, re.S).group(1))
    stores = []
    for m in re.finditer(r'<section class="store">(.*?)</section>', src, re.S):
        block = m.group(1)
        head = re.search(r"<h3>(.*?)<span class=\"tag\">(.*?)</span></h3>", block, re.S)
        rows = [[txt(a), txt(b)] for a, b in re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", block, re.S)]
        srcp = re.search(r'<p class="src">(.*?)</p>', block, re.S).group(1)
        checked = txt(srcp.split("｜")[0]).replace("確認日：", "")
        links = [[txt(t), html.unescape(h)] for h, t in re.findall(r'<a href="([^"]+)">(.*?)</a>', srcp, re.S)]
        stores.append({"name": txt(head.group(1)), "tag": txt(head.group(2)), "rows": rows, "checked": checked, "links": links})
    h2 = re.search(r'<h2><span class="burst">(.*?)</span>(.*?)</h2>', src, re.S)
    note = txt(re.search(r'<p class="note">(.*?)</p>', src, re.S).group(1))
    calc_block = re.search(r'<div class="calc">(.*?)</div>\s*<h2>', src, re.S).group(1)
    calc_ps = [txt(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", calc_block, re.S)]
    how = [txt(p) for p in re.findall(r"<p>(.*?)</p>", re.search(r'<div class="howto">(.*?)</div>', src, re.S).group(1), re.S)]
    return {"slug": slug, "title": title, "kicker": kicker, "h1_html": h1, "sub": sub, "meta": meta, "lead": lead,
            "stores_burst": txt(h2.group(1)), "stores_h2": txt(h2.group(2)), "stores": stores, "note": note,
            "calc_big": calc_ps[0], "calc_text": calc_ps[1], "howto_h2": txt(re.search(r"<h2>([^<]*)</h2>\s*<div class=\"howto\">", src).group(1)),
            "howto": how, "checked": "2026-11-09", "category": "electronics", "crumb": "スマートフォン"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prototype")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "private" / "products" / "iphone-18-pro.json"))
    a = ap.parse_args()
    data = extract(Path(a.prototype).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(data['stores'])} stores")


if __name__ == "__main__":
    main()
