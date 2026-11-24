#!/usr/bin/env python3
"""2026-11-25: add the day's articles from their final drafts (Drive) in one go.  Each needs its card image in Drive
(card_<name>.webp); an article whose image is not back yet is skipped.  Safe to run twice.
Usage: apply_batch_20261125.py [slug ...]   (no slug = every article whose image exists)"""
import glob
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_20261123 as base  # noqa: E402
import apply_20261123b as m  # noqa: E402
from apply_shinkansen_20261124 import NTA  # noqa: E402

DRIVE = base.DRIVE
CONTENT = base.CONTENT
TODAY = "2026-11-25"

# slug: (final file, card image, crumb, primary keyword, [related slugs], category from)
ARTICLES = {
    "trend-ski-lift-ticket-2026": ("記事最終稿_リフト券値上げと早割_2026-11-25.md", "card_リフト券値上げと早割.webp", "リフト券の値上げと早割", "リフト券", ["trend-usj-winter-kids-free", "trend-winter-tire-kanki", "trend-nenmatsu-shinkansen-hatsubai-2026"], "trend-winter-tire-kanki"),
    "trend-kfc-christmas-reserve-2026": ("記事最終稿_ケンタ予約期限_2026-11-25.md", "card_ケンタ予約期限.webp", "ケンタッキーのクリスマス予約", "ケンタッキー", ["trend-xmas-cake-hayawari", "trend-kfc-haitoku-burger", "trend-christmas-market-2026-nyujoryo"], "trend-xmas-cake-hayawari"),
    "trend-toto-nesage-toilet-2026": ("記事最終稿_TOTO値上げとトイレ交換_2026-11-25.md", "card_TOTO値上げとトイレ交換.webp", "TOTOの値上げ", "TOTO", ["trend-mado-reno-2026", "trend-osouji-november", "trend-ketsuro-kabi-taisaku"], "trend-mado-reno-2026"),
    "trend-docomo-nesage-1201": ("記事最終稿_ドコモ値上げ12月_2026-11-25.md", "card_ドコモ値上げ12月.webp", "ドコモの値上げ", "ドコモ", ["trend-netflix-nesage", "trend-switch-shuri-nesage-1116", "trend-mobile-battery-jiko"], "trend-netflix-nesage"),
    "trend-ideco-kyoshutsu-2026": ("記事最終稿_iDeCo拠出限度額_2026-11-25.md", "card_iDeCo拠出限度額.webp", "iDeCoの上限の変更", "iDeCo", ["trend-nenmatsu-chosei-kaisei-fuyo62", "trend-kokuho-hokenryo-jougen-96", "trend-furusato-nozei-nenmatsu"], "trend-nenmatsu-chosei-kaisei-fuyo62"),
    "trend-tokyogas-denki-1201": ("記事最終稿_東京ガス電気12月改定_2026-11-25.md", "card_東京ガス電気12月改定.webp", "東京ガスの電気の改定", "東京ガス", ["trend-denki-gas-futan-keigen", "trend-heating-cost-2026", "trend-teiden-danbou"], "trend-denki-gas-futan-keigen"),
    "trend-ajinomoto-mayonnaise-nesage": ("記事最終稿_味の素マヨネーズ値上げ_2026-11-25.md", "card_味の素マヨネーズ値上げ.webp", "マヨネーズの値上げ", "マヨネーズ", ["trend-mercian-nesage-2027", "trend-ibonoito-nesage-2027", "trend-yakult-nesage"], "trend-mercian-nesage-2027"),
    "trend-nenmatsu-9renkyu-2026": ("記事最終稿_年末年始9連休と年内の締め_2026-11-25.md", "card_年末年始9連休と年内の締め.webp", "年末年始の9連休", "9連休", ["trend-nenmatsu-shinkansen-hatsubai-2026", "trend-nenmatsu-chosei-shorui", "trend-furusato-nozei-nenmatsu"], "trend-nenmatsu-shinkansen-hatsubai-2026"),
    "trend-toyu-haitatsu-tentou-2026": ("記事最終稿_灯油配達と店頭_2026-11-25.md", "card_灯油配達と店頭.webp", "灯油の配達と店頭", "灯油", ["trend-heating-cost-2026", "trend-teiden-danbou", "trend-gasoline-hojo-2026"], "trend-heating-cost-2026"),
}


def link_html(label):
    """marker text (without the 【リンク設置・ ... 】 frame) -> the paragraph of the link"""
    if label.startswith("日本旅行"):
        return NTA
    mm = re.match(r"楽天(?:市場|ブックス)で(.+?)を探す（PR）", label)
    if mm:
        q = mm.group(1)
        return '<p><a href="' + base.rakuten(q) + '" rel="nofollow sponsored noopener" target="_blank">' + q + 'を楽天市場で探す</a>（PR）</p>'
    mm = re.match(r"Amazonで(.+?)を探す（PR）", label)
    if mm:
        q = mm.group(1)
        return '<p><a href="https://www.amazon.co.jp/s?k=%s&amp;tag=amazonmacs-22" rel="nofollow sponsored noopener" target="_blank">Amazonで%sを探す</a>（PR）</p>' % (urllib.parse.quote(q), q)
    raise ValueError("unknown link marker: " + label)


def build(slug):
    final, card, crumb, kw, related_slugs, catfrom = ARTICLES[slug]
    md = open(DRIVE + final, encoding="utf-8").read()
    title = re.match(r"# (.+)", md).group(1).strip()
    body, rest = md.split("\n## 出典", 1)
    credits = [x[2:].strip() for x in re.search(r"^(.*?)(?:\n---|\n##|\Z)", rest.split("\n", 1)[1], re.S).group(1).strip().splitlines() if x.startswith("- ")]
    # each marker -> its own token paragraph, then the token section -> the link html
    links = []

    def tok(mo):
        out = []
        for lab in re.findall(r"【リンク設置・(.+?)】", mo.group(0)):
            links.append(link_html(lab))
            out.append("@@LINK%d@@" % (len(links) - 1))
        sep = chr(10) * 2
        return sep + sep.join(out) + sep

    body = re.sub(r"^(?:【リンク設置・.+?】)+\s*$", tok, body, flags=re.M)
    secs = base.md_sections(body + "\n## 出典", "")
    final_secs = []
    for s in secs:
        if "paras" in s and len(s["paras"]) == 1 and s["paras"][0].startswith("@@LINK"):
            final_secs.append({"html": links[int(re.search(r"\d+", s["paras"][0]).group())]})
        else:
            final_secs.append(s)
    assert all("@@LINK" not in json.dumps(s, ensure_ascii=False) for s in final_secs), slug
    paras = next(s["paras"] for s in final_secs if "paras" in s)
    lead = paras[0]
    sent = re.split(r"(?<=。)", lead)
    top_lead = sent[0]
    description = "".join(sent[:2])
    if len(description) > 120:
        description = sent[0]
    answer = top_lead
    cat = json.load(open(os.path.join(CONTENT, catfrom + ".json"), encoding="utf-8"))["category"]
    seq = max(json.load(open(f, encoding="utf-8")).get("seq", 0) for f in glob.glob(os.path.join(CONTENT, "trend-*.json"))) + 1
    rel = [{"path": "/%s/" % r, "text": json.load(open(os.path.join(CONTENT, r + ".json"), encoding="utf-8"))["h1"]} for r in related_slugs]
    final_secs.insert(0, {"html": '<p class="eyecatch"><img src="/assets/img/eye-%s.webp" width="1280" alt="%s" fetchpriority="high"></p>' % (slug, title)})
    page = {"updated": TODAY, "data_basis": "2026年11月25日現在", "sources": [], "credit": "、".join(credits), "path": "/%s/" % slug,
            "top_lead": top_lead, "kind": "article", "parent": "/", "title": title, "h1": title, "category": cat, "published": TODAY, "seq": seq,
            "crumb": crumb, "primary_kw": kw, "secondary_kw": [], "intent": 1, "description": description, "answer": answer,
            "related": rel, "sections": final_secs}
    m.image(card, slug)
    p = os.path.join(CONTENT, slug + ".json")
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(page, ensure_ascii=False, indent=1) + "\n")
    for r in rel:
        rp = os.path.join(CONTENT, r["path"].strip("/") + ".json")
        d = json.load(open(rp, encoding="utf-8"))
        if not any(x["path"] == page["path"] for x in d["related"]):
            d["related"].append({"path": page["path"], "text": title})
            open(rp, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    want = sys.argv[1:] or list(ARTICLES)
    for slug in want:
        card = ARTICLES[slug][1]
        if not os.path.exists(DRIVE + card):
            print("skip (image not back):", slug)
            continue
        build(slug)
        print("built", slug)
