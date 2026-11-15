"""After a deploy: open the LIVE site and check that what was published really reached the home page, the category, the related pages and the affiliate links,
then write the draft of the 公開結果 file (the one Muse reads) from what was seen.  Nothing here is typed by hand: every line of the draft is a thing this run fetched.

    python -m sokuhou.postcheck --site trend --base https://trend-sokuho.com --page /trend-x/ --page /trend-y/ --title "<what was published>" \\
        [--asked "<what was asked>"] [--commit abc1234] [--out-dir H:/マイドライブ/sokuhou/outbox] [--index]

Checks per page (a failed one is written as 「要修正」 and the exit status is 1):
  page      answers 200, has a title and one h1, and is in /sitemap.xml
  parent    the page above it (the breadcrumb) lists it
  home      the home page links to it when it is among the newest `home_newest` articles (data/linkage/config.json); otherwise only reported
  related   every page it lists under 「関連するページ」 answers 200 and links back
  affiliate the affiliate links on it (host, count, PR mark, rel="nofollow sponsored"); no link worded as a URL; every affiliated advertiser it names has a link
            (data/linkage/advertisers.json).  A page with no affiliate link at all is reported as 「貼らない理由を書く」: the writer must say why (owner 2026-11-13).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from sokuhou import linkage
from sokuhou import sitecheck as sc

OUTBOX = Path("H:/マイドライブ/sokuhou/outbox")
JST = timezone(timedelta(hours=9))


class Fetcher:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.cache: dict[str, tuple[int, str]] = {}

    def __call__(self, path: str) -> tuple[int, str]:
        if path not in self.cache:
            code, body = sc._get(self.base + path)
            self.cache[path] = (code, body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body))
        return self.cache[path]


def parse(text: str) -> sc.Page:
    p = sc.Page()
    p.feed(text)
    p.close()
    return p


def _path(base: str, ref: str, here: str = "/") -> str | None:
    u = urlparse(urljoin(base + here, ref))
    return u.path if u.netloc == urlparse(base).netloc else None


def _ld(pg: sc.Page, typ: str) -> list[dict]:
    out = []
    for b in pg.ld:
        try:
            d = json.loads(b)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == typ:
            out.append(d)
    return out


def _local_links(pg: sc.Page, base: str, here: str) -> set[str]:
    return {x for tag, ref in pg.links if tag == "a" for x in [_path(base, ref, here)] if x}


def verify(site: str, base: str, pages: list[str], fetch=None) -> list[dict]:
    """[{'page', 'check', 'ok', 'detail'}]; ok is True / False, or None for a note that is not a pass or a fail."""
    fetch = fetch or Fetcher(base)
    base = base.rstrip("/")
    rows: list[dict] = []

    def add(page, check, ok, detail):
        rows.append({"page": page, "check": check, "ok": ok, "detail": detail})

    code, sm = fetch("/sitemap.xml")
    sitemap = set(urlparse(u).path for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm)) if code == 200 else set()
    hcode, htext = fetch("/")
    home = parse(htext) if hcode == 200 else None
    home_links = _local_links(home, base, "/") if home else set()
    add("/", "home", hcode == 200, f"top page HTTP {hcode}")
    cfg = linkage.load_config().get(site, {})
    n_newest = int(cfg.get("home_newest", 0))
    ads = linkage.load_advertisers(site)
    for path in pages:
        code, text = fetch(path)
        if code != 200:
            add(path, "page", False, f"HTTP {code}")
            continue
        pg = parse(text)
        add(path, "page", bool(pg.title.strip()) and pg.h1 == 1, f"HTTP 200, title「{pg.title.strip()[:50]}」, h1 {pg.h1}")
        add(path, "sitemap", path in sitemap or pg.noindex, "in /sitemap.xml" if path in sitemap else ("noindex page (not in the sitemap on purpose)" if pg.noindex else "NOT in /sitemap.xml"))
        # parent
        parent = None
        for d in _ld(pg, "BreadcrumbList"):
            items = d.get("itemListElement") or []
            if len(items) >= 2:
                parent = urlparse(str(items[-2].get("item", ""))).path or "/"
        if parent:
            pc, ptext = fetch(parent)
            ok = pc == 200 and path in _local_links(parse(ptext), base, parent)
            add(path, "parent", ok, f"{parent} (HTTP {pc}) " + ("lists this page" if ok else "does NOT link to this page"))
        else:
            add(path, "parent", None, "no breadcrumb parent found")
        # home
        shown = path in home_links
        art = _ld(pg, "Article")
        newest = False
        if n_newest and art and home is not None:
            days = []
            for p2 in sitemap:
                c2, t2 = fetch(p2)
                if c2 == 200:
                    for d in _ld(parse(t2), "Article"):
                        if d.get("datePublished"):
                            days.append((d["datePublished"], p2))
            days.sort(reverse=True)
            newest = path in [p for _, p in days[:n_newest]]
        add(path, "home", (shown if newest else None), ("on the top page" if shown else "not on the top page") + (f" (one of the {n_newest} newest: must be there)" if newest else ""))
        # related
        rel = linkage.BLOCK_RE.search(text)
        targets = []
        if rel:
            targets = [x for h in re.findall(r'href="([^"]+)"', rel.group(1)) for x in [_path(base, h, path)] if x]
        if not targets:
            add(path, "related", None, "no 「関連するページ」 block")
        for q in targets:
            qc, qt = fetch(q)
            back = qc == 200 and path in _local_links(parse(qt), base, q)
            add(path, "related", qc == 200 and back, f"{q} HTTP {qc}, " + ("links back" if back else "does NOT link back"))
        # affiliate
        text_plain = " ".join(pg.text)
        links = []
        for m in re.finditer(r"<a\b([^>]*)>", text):
            a = m.group(1)
            hm = re.search(r'href="([^"]+)"', a)
            if hm and linkage._is_affiliate(hm.group(1)) and "gifbanner" not in hm.group(1):
                rel_attr = (re.search(r'rel="([^"]*)"', a) or [None, ""])[1]
                links.append((hm.group(1), rel_attr))
        hosts = sorted({(urlparse(h).netloc or "amazon-tag") for h, _ in links})
        bad_rel = [h for h, r in links if "sponsored" not in r or "nofollow" not in r]
        has_pr = "PR" in text_plain or "広告" in text_plain
        if links:
            add(path, "affiliate", not bad_rel and has_pr, f"{len(links)} affiliate link(s) to {', '.join(hosts)}; " + ("all rel=nofollow sponsored" if not bad_rel else f"{len(bad_rel)} WITHOUT rel=nofollow sponsored") + "; " + ("PR mark present" if has_pr else "NO PR mark"))
        else:
            add(path, "affiliate", None, "no affiliate link on this page: write why none could be placed (the owner's rule: look for a natural place yourself)")
        urls = [t for h, t in pg.anchor_text if t and linkage.URL_TEXT.match(t.strip())]
        add(path, "link-text", not urls, "no link is worded as a URL" if not urls else "links worded as a URL: " + ", ".join(urls[:3]))
        for ad in ads:
            if any(n in text_plain for n in ad["names"]):
                ok = any(any(n in t for n in ad["names"]) or any(tok in h for tok in ad.get("href_has", [])) for h, t in pg.anchor_text if linkage._is_affiliate(h))
                add(path, "advertiser", ok, f"{ad['names'][0]} is named: " + ("its affiliate link is there" if ok else "NO affiliate link for it"))
    return rows


def render(site: str, base: str, rows: list[dict], title: str, asked: str, commit: str, now: datetime) -> tuple[str, bool]:
    bad = [r for r in rows if r["ok"] is False]
    notes = [r for r in rows if r["ok"] is None]
    lines = [f"# 公開結果(自動確認の下書き): {site} / {title}", "",
             f"自動確認: **{'要修正(' + str(len(bad)) + '件)' if bad else 'OK'}**　{now:%Y-%m-%d %H:%M} JST に {base} の本番を取得して照合(sokuhou/postcheck.py)", "",
             "## 何を依頼されたか", asked or "(記入)", "", "## 何を変えたか", f"コミット: {commit or '(記入)'}", ""]
    pages = sorted({r["page"] for r in rows if r["page"] != "/"})
    for p in pages:
        lines.append(f"- {base}{p}")
    lines += ["", "## 本番で実際に見たこと(自動取得。見ていないものは書いていない)", "", "| ページ | 項目 | 結果 | 見たもの |", "|---|---|---|---|"]
    for r in rows:
        mark = {True: "OK", False: "要修正", None: "要記入/参考"}[r["ok"]]
        lines.append(f"| {r['page']} | {r['check']} | {mark} | {r['detail']} |")
    lines += ["", "## トップ・カテゴリ・関連ページのリンクの確認", "上の表の home / parent / related の行。要修正が 0 件なら、トップ(新着の対象のとき)・所属カテゴリ・関連ページの相互リンクを本番で確認済み。", ""]
    if bad:
        lines += ["## 要修正", ""] + [f"- {r['page']} {r['check']}: {r['detail']}" for r in bad] + [""]
    if notes:
        lines += ["## 書き手が埋めること", ""] + [f"- {r['page']} {r['check']}: {r['detail']}" for r in notes if r["check"] == "affiliate"] + ["- 確認できなかったこと:(なければ「なし」)", ""]
    return "\n".join(lines), not bad


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--page", action="append", required=True)
    ap.add_argument("--title", default="更新")
    ap.add_argument("--asked", default="")
    ap.add_argument("--commit", default="")
    ap.add_argument("--out-dir", default=str(OUTBOX))
    ap.add_argument("--index", action="store_true", help="also add the line to 公開結果_索引.md (a failure is marked 要修正 in the Muse column)")
    a = ap.parse_args(argv)
    now = datetime.now(JST)
    rows = verify(a.site, a.base, a.page)
    text, ok = render(a.site, a.base, rows, a.title, a.asked, a.commit, now)
    out = Path(a.out_dir)
    slug = re.sub(r"[^\w\-]+", "", a.title)[:30] or "更新"
    name = f"公開結果_{a.site}_{now:%Y-%m-%d}_{slug}.md"
    if out.is_dir():
        (out / name).write_text(text + "\n", encoding="utf-8")
        print(f"written: {out / name}")
        if a.index:
            idx = out / "公開結果_索引.md"
            if idx.exists():
                t = idx.read_text(encoding="utf-8")
                head = "| 日時 | サイト | 内容 | 結果ファイル | Muse確認 | 対応 |\n"
                row = f"| {now:%Y-%m-%d} | {a.site} | {a.title}(自動確認) | {name} | {'' if ok else '要修正(自動確認)'} | |\n"
                if head in t:
                    idx.write_text(t.replace(head, head + row, 1), encoding="utf-8")
                    print("index line added")
    else:
        print(f"(the outbox {out} is not there: the draft is only printed)")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
