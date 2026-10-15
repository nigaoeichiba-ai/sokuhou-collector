"""Cloud watchdog (2026-10-15): finds out, without the owner's PC, that a site or the PC-side routines stopped.

Run by .github/workflows/office-watch.yml every 3 hours.  It reads only public pages and the repository's own commit list, writes
watch_report.md (the issue body) and watch.json, and always exits 0: the workflow decides what to do with the problems.

What it checks (every threshold was set against the live data of 2026-10-15):
  - each site's top page answers 200 and has an <h1>;
  - each sitemap.xml's newest lastmod is at most 2 days old (the data sites are rebuilt by Actions every day: a stale sitemap = collection or deploy stopped);
  - yorokobu-present.com/picks/ shows today's or yesterday's date (written by the owner's PC every morning: a stale one = the PC routines stopped);
  - the owner's account made a commit to main in the last 36 hours (the routines commit every day; the bot's data commits do not count).
What it could not read is listed as 確認できなかったこと and never counted as fine.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request

JST = dt.timezone(dt.timedelta(hours=9))
SITES = ["saichin-sokuho.com", "kuma-sokuho.com", "yorokobu-present.com", "minna-no-illust.com"]
SITEMAP_MAX_AGE_DAYS = 2
PICKS_MAX_AGE_DAYS = 1
HUMAN_COMMIT_MAX_HOURS = 36
BOT_NAMES = ("sokuhou-bot", "github-actions[bot]")
REPO = "nigaoeichiba-ai/sokuhou-collector"
UA = {"User-Agent": "Mozilla/5.0 (compatible; MACS-office-watch/1.0)"}


def fetch(url: str, headers: dict | None = None, tries: int = 2) -> str:
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status != 200:
                    raise OSError(f"HTTP {r.status}")
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - every failure is reported, none is hidden
            last = e
    raise OSError(f"{url}: {last}")


def newest_lastmod(sitemap: str) -> dt.date | None:
    days = re.findall(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})", sitemap)
    return max((dt.date.fromisoformat(d) for d in days), default=None)


def newest_japanese_date(html: str) -> dt.date | None:
    found = []
    for y, m, d in re.findall(r"(20\d\d)年(\d{1,2})月(\d{1,2})日", html):
        try:
            found.append(dt.date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return max(found, default=None)


def check(now: dt.datetime, get=fetch, commits=None) -> dict:
    """Return {'problems': [...], 'unverified': [...], 'ok': [...]}.  `get` and `commits` are replaced in the tests."""
    today = now.astimezone(JST).date()
    out = {"problems": [], "unverified": [], "ok": []}

    for site in SITES:
        try:
            top = get(f"https://{site}/")
            if "<h1" not in top:
                out["problems"].append(f"{site}: トップページに見出し(h1)がありません。公開されたページが壊れている可能性があります")
            else:
                out["ok"].append(f"{site}: トップページは開きます")
        except OSError as e:
            out["problems"].append(f"{site}: トップページが開きません({e})")
            continue
        try:
            newest = newest_lastmod(get(f"https://{site}/sitemap.xml"))
            if newest is None:
                out["unverified"].append(f"{site}: sitemap.xml に日付(lastmod)がなく、更新の新しさを確認できませんでした")
            elif (today - newest).days > SITEMAP_MAX_AGE_DAYS:
                out["problems"].append(f"{site}: sitemap の最新の日付が {newest}({(today - newest).days}日前)です。毎日の自動更新か公開が止まっている可能性があります")
            else:
                out["ok"].append(f"{site}: sitemap の最新の日付は {newest}")
        except OSError as e:
            out["unverified"].append(f"{site}: sitemap.xml を読めませんでした({e})")

    try:
        newest = newest_japanese_date(get("https://yorokobu-present.com/picks/"))
        if newest is None:
            out["unverified"].append("yorokobu-present.com/picks/: 日付を読み取れませんでした")
        elif (today - newest).days > PICKS_MAX_AGE_DAYS:
            out["problems"].append(f"yorokobu-present.com/picks/ の最新の日付が {newest} です。毎朝の「今日のおすすめ」が{(today - newest).days}日分たまっていない=パソコン側の定期実行が止まっている可能性があります")
        else:
            out["ok"].append(f"yorokobu-present.com/picks/ の最新の日付は {newest}")
    except OSError as e:
        out["unverified"].append(f"yorokobu-present.com/picks/ を読めませんでした({e})")

    if commits is None:
        out["unverified"].append("コミットの履歴を取得できませんでした")
    else:
        human = [c for c in commits if c["author"] not in BOT_NAMES]
        if not human:
            out["problems"].append(f"直近{HUMAN_COMMIT_MAX_HOURS}時間に、オーナーのアカウントのコミットがありません。パソコン側の定期実行(毎日コミットする)が止まっている可能性があります")
        else:
            newest_c = max(c["time"] for c in human)
            out["ok"].append(f"オーナーのアカウントの最新のコミット: {newest_c.astimezone(JST):%m-%d %H:%M}")
    return out


def recent_commits(now: dt.datetime, token: str | None) -> list[dict] | None:
    since = (now - dt.timedelta(hours=HUMAN_COMMIT_MAX_HOURS)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        data = json.loads(fetch(f"https://api.github.com/repos/{REPO}/commits?sha=main&since={since}&per_page=100", headers))
    except (OSError, ValueError):
        return None
    return [{"author": (c.get("commit", {}).get("author", {}) or {}).get("name", ""),
             "time": dt.datetime.fromisoformat(c["commit"]["committer"]["date"].replace("Z", "+00:00"))} for c in data]


def report(result: dict, now: dt.datetime, test: bool = False) -> str:
    lines = [f"# 見張りの結果 {now.astimezone(JST):%Y-%m-%d %H:%M} JST", ""]
    if test:
        lines += ["**これは通知のテストです。** 届いたことを確認したら、このイシューは次の見張り(3時間以内)で自動的に閉じます。", ""]
    if result["problems"]:
        lines += ["## おかしいところ", *[f"- {p}" for p in result["problems"]], ""]
    if result["unverified"]:
        lines += ["## 確認できなかったこと(問題なしとは扱っていません)", *[f"- {p}" for p in result["unverified"]], ""]
    lines += ["## 確認できたこと", *[f"- {p}" for p in result["ok"]], "",
              "---", "GitHub Actions の office-watch(3時間ごと)が自動で書いています。直ったことを確認すると、自動で閉じます。",
              "パソコンが止まっていたときは、パソコンが起きれば定期実行が遅れて動きます。"]
    return "\n".join(lines) + "\n"


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    test = os.environ.get("WATCH_TEST") == "true"
    result = check(now, commits=recent_commits(now, os.environ.get("GITHUB_TOKEN")))
    if test:
        result["problems"].insert(0, "通知のテスト: 本当の異常ではありません")
    with open("watch_report.md", "w", encoding="utf-8") as f:
        f.write(report(result, now, test))
    with open("watch.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(report(result, now, test))
    return 0


if __name__ == "__main__":
    sys.exit(main())
