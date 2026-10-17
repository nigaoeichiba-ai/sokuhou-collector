"""Aggregate a web server access log (combined format) read from stdin.

Prints counts only: the repository and the Actions log are public, so nothing that identifies a
visitor leaves this module (no IP, no full user agent, no query string, no cookie, no single request).
Rows with fewer than MIN_ROWS hits are left out.

    cat access_log | python -m sokuhou.accesslog --site kuma-sokuho.com
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import urlsplit

MIN_ROWS = 3
LINE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) \S+ "([^"]*)" "([^"]*)"')
ASSET = re.compile(r"\.(css|js|mjs|map|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|otf|xml|txt|json|csv|pdf|ics|mp4|webm|zip)$", re.I)

# order matters: the first match wins
AGENTS = (
    ("Googlebot", r"googlebot|google-inspectiontool|googleother|adsbot-google|storebot-google|google-extended"),
    ("Bingbot", r"bingbot|bingpreview|msnbot"),
    ("OpenAI(GPTBot等)", r"gptbot|oai-searchbot|chatgpt-user"),
    ("Anthropic(ClaudeBot等)", r"claudebot|claude-user|claude-web|anthropic"),
    ("Perplexity", r"perplexity"),
    ("Applebot", r"applebot"),
    ("Bytespider", r"bytespider|bytedance"),
    ("SEOツール", r"ahrefs|semrush|mj12|dotbot|petalbot|dataforseo|blexbot"),
    ("Yandex・Baidu", r"yandex|baiduspider"),
    ("SNS・プレビュー", r"facebookexternalhit|twitterbot|slackbot|discordbot|line-poker|linebot|bluesky|bsky"),
    ("その他のBot・自動取得", r"bot|crawl|spider|slurp|curl|wget|python|java/|go-http|scrapy|okhttp|headless|monitor|uptime|\bhttp"),
)
AGENT_RES = [(name, re.compile(rx, re.I)) for name, rx in AGENTS]

SEARCH = (
    ("Google", ("google.",)),
    ("Bing", ("bing.com",)),
    ("Yahoo!", ("yahoo.",)),
    ("DuckDuckGo", ("duckduckgo.com",)),
    ("Ecosia・Brave・その他", ("ecosia.org", "search.brave.com", "baidu.com", "naver.com", "yandex.")),
)


def classify_agent(ua: str) -> str:
    if not ua or ua == "-":
        return "UAなし"
    for name, rx in AGENT_RES:
        if rx.search(ua):
            return name
    return "ブラウザ(人)"


def is_page(path: str) -> bool:
    return not ASSET.search(path)


def search_engine(host: str) -> str:
    h = host.lower()
    for name, keys in SEARCH:
        if any(k in h for k in keys):
            return name
    return ""


def referrer_host(ref: str) -> str:
    if not ref or ref == "-":
        return ""
    try:
        return (urlsplit(ref).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def parse_day(stamp: str) -> str:
    try:
        return datetime.strptime(stamp.split()[0], "%d/%b/%Y:%H:%M:%S").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def aggregate(lines, own_domain: str = "") -> dict:
    own = own_domain.lower().removeprefix("www.")
    r = {"lines": 0, "parsed": 0, "first": "", "last": "", "days": Counter(), "days_human": Counter(),
         "pages": Counter(), "refs": Counter(), "search": Counter(), "agents": Counter(), "n404": Counter(),
         "visitors": set(), "human_views": 0}
    for raw in lines:
        r["lines"] += 1
        m = LINE.match(raw)
        if not m:
            continue
        r["parsed"] += 1
        ip, stamp, method, target, status, ref, ua = m.groups()
        day = parse_day(stamp)
        path = target.split("?", 1)[0].split("#", 1)[0]
        if day:
            r["first"] = day if not r["first"] or day < r["first"] else r["first"]
            r["last"] = day if day > r["last"] else r["last"]
        if status == "404" and method == "GET" and "@" not in path:
            r["n404"][path[:120]] += 1
        if method != "GET" or status not in ("200", "304") or not is_page(path):
            continue
        agent = classify_agent(ua)
        r["agents"][agent] += 1
        r["days"][day] += 1
        if agent != "ブラウザ(人)":
            continue
        r["human_views"] += 1
        r["days_human"][day] += 1
        r["pages"][path[:120]] += 1
        r["visitors"].add(hashlib.sha1(f"{day}|{ip}|{ua}".encode()).digest()[:8])
        host = referrer_host(ref)
        if not host:
            r["refs"]["(直接・不明)"] += 1
        elif own and host.endswith(own):
            r["refs"]["(サイト内)"] += 1
        else:
            r["refs"][host] += 1
            eng = search_engine(host)
            if eng:
                r["search"][eng] += 1
    return r


def _rows(counter: Counter, limit: int) -> list[tuple[str, int]]:
    return [(k, v) for k, v in counter.most_common(limit) if v >= MIN_ROWS]


def render(r: dict, site: str) -> str:
    out = [f"### {site}"]
    out.append(f"- 読めた行 {r['parsed']}/{r['lines']}(形式が合わない行は数えていない)。期間 {r['first'] or '不明'} 〜 {r['last'] or '不明'}")
    hv = r["human_views"]
    out.append(f"- ブラウザ(人)のページ表示 {hv}、のべ訪問者(日×端末の組)およそ {len(r['visitors'])}")
    ext = sum(v for k, v in r["refs"].items() if k not in ("(直接・不明)", "(サイト内)"))
    se = sum(r["search"].values())
    out.append(f"- 検索経由のページ表示 {se}" + (f"({se * 100 // hv}%)" if hv else "") +
               ("。内訳 " + "・".join(f"{k} {v}" for k, v in r["search"].most_common() if v >= MIN_ROWS) if se else "") +
               f"。検索以外の外部サイトから {ext - se}")
    out.append("- 日別(人 / 全体のページ表示): " + (" ".join(f"{d[5:]}:{r['days_human'][d]}/{c}" for d, c in sorted(r["days"].items()) if d and c >= MIN_ROWS) or "なし"))
    for title, key, limit in (("ページ別(人)", "pages", 15), ("流入元(人。リファラのドメイン)", "refs", 15),
                              ("Bot・自動取得の種別(ページ取得の件数)", "agents", 15), ("404 になったパス(3回以上)", "n404", 15)):
        rows = _rows(r[key], limit)
        out.append(f"- {title}: " + (" / ".join(f"{k} {v}" for k, v in rows) if rows else "なし"))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="domain of the site, e.g. kuma-sokuho.com")
    a = ap.parse_args(argv)
    stream = (ln.decode("utf-8", "replace") if isinstance(ln, bytes) else ln for ln in sys.stdin.buffer)
    r = aggregate(stream, a.site)
    print(render(r, a.site))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
