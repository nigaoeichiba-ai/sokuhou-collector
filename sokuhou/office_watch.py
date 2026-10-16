"""Cloud watchdog (2026-10-15): finds out, without the owner's PC, that a site or the PC-side routines stopped.

Run by .github/workflows/office-watch.yml every hour and after every deploy-sites run.  It reads only public pages and the repository's own commit list, writes
watch_report.md (the issue body) and watch.json, and always exits 0: the workflow decides what to do with the problems.

What it checks (every threshold was set against the live data of 2026-10-15):
  - each site's top page answers 200 and has an <h1>;
  - each sitemap.xml's newest lastmod is at most 2 days old (the data sites are rebuilt by Actions every day: a stale sitemap = collection or deploy stopped);
  - yorokobu-present.com/picks/ shows today's or yesterday's date (written by the owner's PC every morning: a stale one = the PC routines stopped);
  - the owner's account made a commit to main in the last 36 hours (the routines commit every day; the bot's data commits do not count);
  - (2026-10-16) a change that touches a site is live within 2 hours: each site publishes the commit it was built from (/deployed-sha.txt); the commits after it that
    touch the site's files must not be older than 2 hours, else the deploy is started again by hand (watch.json "heal"), and a deploy run that has run for 150
    minutes is reported.
What it could not read is listed as 確認できなかったこと and never counted as fine.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
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

# --- deploy lag (the same ownership rules as the Gate step of deploy.yml; test_office_watch checks that the two agree) ---
LAG_MINUTES = 120
STUCK_RUN_MINUTES = 150
REDISPATCH_HOURS = 3
DEPLOY_SITES = {"saichin": "saichin-sokuho.com", "kuma": "kuma-sokuho.com", "yorokobu": "yorokobu-present.com", "minna": "minna-no-illust.com"}
OWNERS = (
    ("yorokobu", ("sites/yorokobu/*", "tests/test_yorokobu*", "tests/fixtures/yorokobu/*", "data/yorokobu*")),
    ("minna", ("sites/minna/*", "tests/test_minna*")),
    ("atomou", ("sites/atomou/*", "tests/test_atomou*", "tests/fixtures/atomou/*", "data/atomou/*")),
    ("kuma", ("sites/kuma/*", "tests/test_kuma*", "tests/test_*_kuma.py", "tests/test_otsu_bear.py", "tests/fixtures/*kuma*", "tests/fixtures/otsu_bear*",
              "data/*_kuma.json", "data/otsu_bear.json", "sokuhou/sources/*_kuma.py", "sokuhou/sources/otsu_bear.py")),
)
DEPLOY_TRIGGERS = ("sites/", "sokuhou/", "data/", "tests/")
ACTIVE = ("in_progress", "queued", "waiting", "pending", "requested")


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


def owner_of(path: str) -> str:
    for name, patterns in OWNERS:
        if any(fnmatch.fnmatchcase(path, p) for p in patterns):
            return name
    return "shared"


def touches(site: str, files: list[str]) -> bool:
    """Does a push with these files redeploy `site`?  (what the push trigger and the Gate step of deploy.yml decide)"""
    for f in files:
        if not (f.startswith(DEPLOY_TRIGGERS) or f in ("requirements.txt", ".github/workflows/deploy.yml")):
            continue
        if owner_of(f) in ("shared", site):
            return True
    return False


def deploy_lag(now: dt.datetime, served: dict, commits_after, runs: list) -> dict:
    """served: {site: commit id the live site was built from, or None}; commits_after(sha) -> [{'sha','time','files'}] oldest first, or None when unreadable;
    runs: [{'status','event','created'}] of deploy-sites, newest first.  Returns problems / unverified / ok / heal (the sites to deploy again)."""
    out = {"problems": [], "unverified": [], "ok": [], "heal": []}
    active = [r for r in runs if r["status"] in ACTIVE]
    recent_manual = [r for r in runs if r["event"] == "workflow_dispatch" and (now - r["created"]).total_seconds() < REDISPATCH_HOURS * 3600]
    for r in active:
        mins = (now - r["created"]).total_seconds() / 60
        if r["status"] == "in_progress" and mins > STUCK_RUN_MINUTES:
            out["problems"].append(f"deploy-sites の実行が {mins:.0f} 分続いています(目安は {STUCK_RUN_MINUTES} 分まで)。GitHub の Actions で、どのジョブが長いか確認が必要です")
    for site, domain in DEPLOY_SITES.items():
        sha = served.get(site)
        if not sha:
            out["unverified"].append(f"{domain}: 公開中のコミット(/deployed-sha.txt)がまだ読めません。次の公開のあとに現れます")
            continue
        commits = commits_after(sha)
        if commits is None:
            out["unverified"].append(f"{domain}: 公開中のコミット {sha[:8]} 以降の変更を GitHub から読めませんでした")
            continue
        waiting = [c for c in commits if touches(site, c["files"])]
        if not waiting:
            out["ok"].append(f"{domain}: 公開は最新です(公開中のコミット {sha[:8]}。これ以降、このサイトに関わる変更はありません)")
            continue
        oldest = min(c["time"] for c in waiting)
        age = (now - oldest).total_seconds() / 60
        if age <= LAG_MINUTES:
            out["ok"].append(f"{domain}: 公開待ちの変更が {len(waiting)} 件(最古で {age:.0f} 分前。{LAG_MINUTES} 分までは通常の待ち)")
            continue
        out["problems"].append(f"{domain}: 公開されていない変更が {len(waiting)} 件あり、最古は {age:.0f} 分前です(目安は {LAG_MINUTES} 分まで)")
        if active:
            out["unverified"].append(f"{domain}: デプロイが実行中または待機中のため、自動の再公開はまだ行いません")
        elif recent_manual:
            out["unverified"].append(f"{domain}: {REDISPATCH_HOURS} 時間以内に手動のデプロイがあったため、自動の再公開は行いません。それでも公開されない場合は、原因があります")
        else:
            out["heal"].append(site)
    return out


def check(now: dt.datetime, get=fetch, commits=None, deploy=None) -> dict:
    """Return {'problems': [...], 'unverified': [...], 'ok': [...]}.  `get`, `commits` and `deploy` (the result of deploy_lag) are replaced in the tests."""
    today = now.astimezone(JST).date()
    out = {"problems": [], "unverified": [], "ok": [], "heal": []}
    if deploy is not None:
        for k in ("problems", "unverified", "ok", "heal"):
            out[k].extend(deploy[k])

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


def _api(path: str, token: str | None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return json.loads(fetch(f"https://api.github.com{path}", headers))


def read_served() -> dict:
    out = {}
    for site, domain in DEPLOY_SITES.items():
        try:
            text = fetch(f"https://{domain}/deployed-sha.txt").strip()
            out[site] = text if re.fullmatch(r"[0-9a-f]{40}", text) else None
        except OSError:
            out[site] = None
    return out


def make_commits_after(token: str | None):
    def commits_after(sha: str):
        try:
            cmp_ = _api(f"/repos/{REPO}/compare/{sha}...main", token)
            rows = []
            for c in cmp_.get("commits", [])[:60]:
                detail = _api(f"/repos/{REPO}/commits/{c['sha']}", token)
                rows.append({"sha": c["sha"], "files": [f["filename"] for f in detail.get("files", [])],
                             "time": dt.datetime.fromisoformat(detail["commit"]["committer"]["date"].replace("Z", "+00:00"))})
            return rows
        except (OSError, ValueError, KeyError):
            return None
    return commits_after


def read_runs(token: str | None) -> list[dict]:
    try:
        data = _api(f"/repos/{REPO}/actions/workflows/deploy.yml/runs?per_page=20", token)
    except (OSError, ValueError):
        return []
    return [{"status": r["status"], "event": r["event"], "created": dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))} for r in data.get("workflow_runs", [])]


def report(result: dict, now: dt.datetime, test: bool = False) -> str:
    lines = [f"# 見張りの結果 {now.astimezone(JST):%Y-%m-%d %H:%M} JST", ""]
    if test:
        lines += ["**これは通知のテストです。** 届いたことを確認したら、このイシューは次の見張り(1時間以内)で自動的に閉じます。", ""]
    if result["problems"]:
        lines += ["## おかしいところ", *[f"- {p}" for p in result["problems"]], ""]
    if result.get("heal"):
        lines += ["## 自動で再公開を依頼しました", *[f"- {DEPLOY_SITES[h]}(deploy-sites を、このサイトだけ、実際に公開する設定で起動)" for h in result["heal"]], ""]
    if result["unverified"]:
        lines += ["## 確認できなかったこと(問題なしとは扱っていません)", *[f"- {p}" for p in result["unverified"]], ""]
    lines += ["## 確認できたこと", *[f"- {p}" for p in result["ok"]], "",
              "---", "GitHub Actions の office-watch(1時間ごと・デプロイのあと)が自動で書いています。直ったことを確認すると、自動で閉じます。",
              "パソコンが止まっていたときは、パソコンが起きれば定期実行が遅れて動きます。"]
    return "\n".join(lines) + "\n"


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    test = os.environ.get("WATCH_TEST") == "true"
    token = os.environ.get("GITHUB_TOKEN")
    try:
        deploy = deploy_lag(now, read_served(), make_commits_after(token), read_runs(token))
    except Exception as e:  # noqa: BLE001 - a failure here must show up in the report, never stop the other checks
        deploy = {"problems": [], "unverified": [f"公開の遅れの確認に失敗しました({e})"], "ok": [], "heal": []}
    result = check(now, commits=recent_commits(now, token), deploy=deploy)
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
