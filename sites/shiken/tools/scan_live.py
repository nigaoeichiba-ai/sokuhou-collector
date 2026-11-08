#!/usr/bin/env python3
"""文章ゲートの監視(読むだけ): 全サイトの本番ページを、ng_rules.json で走査して、サイトごと・語ごとの件数を報告する。

デプロイにも定期タスクにも触らない。本番のページを取得するだけで、サーバーへ書き込まない。
使い方: python3 scan_live.py <ng_rules.json> <出力のmd> [サイトID ...]
サイトの指定がなければ、data/sites.json の全サイト。例外(ng_rules.json の exceptions)は、サイトごとに適用して、適用した件数と理由を出す。
取得できなかったサイト・ページは「取得できず」と書く(0件とは書かない)。終了コード: 0=走査できた、1=ルールが読めない、3=取得できなかった所がある。
"""
import collections
import concurrent.futures as cf
import html
import importlib.util
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_checker():
    spec = importlib.util.spec_from_file_location("check_text", HERE / "check_text.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "textgate-live-monitor"})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception:
        return None


def page_urls(base: str):
    sm = get(base + "/sitemap.xml")
    if sm is None:
        return None
    urls = re.findall(r"<loc>(.*?)</loc>", sm)
    for sub in [u for u in urls if u.endswith(".xml")]:
        body = get(html.unescape(sub))
        if body is None:
            return None
        urls += re.findall(r"<loc>(.*?)</loc>", body)
    return [html.unescape(u) for u in urls if not u.endswith(".xml")]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    rules_path, out_path, only = sys.argv[1], sys.argv[2], set(sys.argv[3:])
    mod = load_checker()
    try:
        mod.HARD_PATTERNS, mod.SOFT_PATTERNS, mod.WHITELIST, version, mod.EXCEPTIONS = mod.load_rules(rules_path)
    except Exception as exc:
        print(f"ルールを読めませんでした: {exc}")
        return 1
    reg = json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))
    lines = ["# 文章ゲートの本番の走査(読むだけ)", "", f"- 使ったルール version: {version}", ""]
    bad = 0
    table = []
    for s in reg["sites"]:
        name = s["name"]
        if only and name not in only:
            continue
        base = "https://" + s["domain"]
        urls = page_urls(base)
        if urls is None:
            table.append((name, "取得できず", "", ""))
            bad += 1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            failed = 0
            with cf.ThreadPoolExecutor(8) as pool:
                for i, (u, body) in enumerate(zip(urls, pool.map(get, urls))):
                    if body is None:
                        failed += 1
                        continue
                    (Path(tmp) / f"{i:05d}_{re.sub(r'[^A-Za-z0-9]+', '_', u[-60:])}.html").write_text(body, encoding="utf-8")
            files, hard, _soft, _loc, applied = mod.scan(tmp, site=name)
        by = collections.Counter(label for _rel, label, _ex in hard)
        detail = "、".join(f"{k} {v}" for k, v in by.most_common()) or "なし"
        note = f"例外適用 {len(applied)} 件" if applied else ""
        if failed:
            note += f" 取得できず {failed} ページ"
            bad += 1
        table.append((name, f"{len(urls)}ページ / ハードNG {len(hard)} 件", detail, note.strip()))
    lines += ["| サイト | 走査 | 語ごとの件数 | 備考 |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in table]
    lines += ["", "(取得できなかったものは「取得できず」。0件とは書かない。)"]
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 3 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
