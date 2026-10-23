"""The deploy's page data, taken from the server's private folder instead of fetched (and cached in the public repository's Actions cache) at every deploy.

    python -m sites.yorokobu.items_fresh [--max-hours 36] [--in data/yorokobu_items.json] [--out out/yorokobu_items.json]

The scheduled workflow yorokobu-items (refresh.py, about 40 minutes of API calls) leaves data/yorokobu_items.json in ~/yorokobu-private/; the deploy pulls it (privatedata.py).
What changed in the content since that fetch is topped up here with a few calls: the daily picks' item codes that the file does not have, and the pages (themes, ideas) that it does
not have.  Exit 0: the file is written; exit 1: the data is missing, too old or too different, and the caller runs the full `refresh` instead.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu import dailypicks as dp  # noqa: E402
from sites.yorokobu import refresh as rf  # noqa: E402
from sokuhou import rakuten  # noqa: E402

JST = timezone(timedelta(hours=9))
MAX_MISSING_PAGE_SHARE = 0.25          # more new pages than this and the full refresh is the better way
ITEMS_WORKFLOW = "yorokobu-items.yml"
WAIT_MAX_MINUTES = 50                  # how long the deploy waits for a running yorokobu-items before it fetches everything itself
WAIT_POLL_SECONDS = 90                 # one call per poll: about 35 calls in the 50 minutes, under the 60 an hour that GitHub allows without a token


def age_hours(data: dict, now: datetime) -> float:
    try:
        t = datetime.fromisoformat(data["fetched_at"])
    except (KeyError, ValueError, TypeError):
        return 1e9
    if t.tzinfo is None:
        t = t.replace(tzinfo=JST)
    return (now - t).total_seconds() / 3600


def missing(c: dict, data: dict) -> tuple[list[str], list[str], list[str]]:
    """(item codes of the daily picks that the file does not have, page keys that it does not have, recipient slugs whose like lines it does not have)."""
    codes = [x for x in dp.rakuten_codes(c.get("daily") or []) if x not in (data.get("daily") or {})]
    keys = [ct.pair_key(p) for p in ct.pages(c) if ct.pair_key(p) not in (data.get("pairs") or {})]
    likes = [r["slug"] for r in c.get("recipients") or [] if r.get("like_rows") and r["slug"] not in (data.get("likes") or {})]
    return codes, keys, likes


def top_up(data: dict, c: dict, client: rakuten.Client, picks: dict, codes: list[str], keys: list[str]) -> dict:
    """The file with the missing daily lookups and pages added (a copy)."""
    out = dict(data)
    if codes:
        daily = dict(out.get("daily") or {})
        state = {"errors": 0}
        for code in codes:
            it = rf.lookup(client, code, state, len(codes))
            if it:
                daily[code] = it
        out["daily"] = daily
    if keys:
        add = rf.refresh(c, client, picks, keys=set(keys))["pairs"]
        out["pairs"] = {**(out.get("pairs") or {}), **add}
    return out


def prepare(data: dict | None, c: dict, picks: dict, now: datetime, max_hours: float, client_factory) -> tuple[dict | None, str]:
    """(the data to build with, or None) and a one-line reason."""
    if not data:
        return None, "no data from the private folder"
    h = age_hours(data, now)
    if h > max_hours:
        return None, f"the data is {h:.0f} hours old (limit {max_hours:.0f})"
    codes, keys, likes = missing(c, data)
    total = len(ct.pages(c)) or 1
    if likes or len(keys) > MAX_MISSING_PAGE_SHARE * total:
        return None, f"too different from the content: {len(keys)} pages and {len(likes)} like lines missing"
    if not codes and not keys:
        return data, f"fresh ({h:.1f} hours old), nothing to top up"
    client = client_factory()
    if client is None:
        return None, f"{len(codes)} daily items and {len(keys)} pages are missing and there is no API key to top them up"
    try:
        return top_up(data, c, client, picks, codes, keys), f"fresh ({h:.1f} hours old), topped up {len(codes)} daily items and {len(keys)} pages"
    except rakuten.RakutenError as e:
        return None, f"the top-up failed: {e}"


def running_items_run(repo: str, token: str | None = None) -> bool:
    """Is a run of the scheduled yorokobu-items workflow going (or queued) now?  The runs of a public repository can be listed without a token; None of the answers means no."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/workflows/{ITEMS_WORKFLOW}/runs?per_page=3",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "yorokobu-items-fresh", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return any(x.get("status") in ("in_progress", "queued") for x in json.load(r).get("workflow_runs") or [])


def wait_for_items_run(repo: str | None, token: str | None = None, *, running=running_items_run, sleep=time.sleep, clock=time.monotonic,
                       max_minutes: float = WAIT_MAX_MINUTES, poll: float = WAIT_POLL_SECONDS) -> str:
    """When the data is old because the scheduled fetch has not finished (or failed and its retry is running), the deploy asking the API for everything at the same time ends in
    429s for both (2026-10-24).  So: wait, up to `max_minutes`, while that workflow runs.  Returns what happened, in a few words ('' when there was nothing to wait for)."""
    if not repo:
        return ""
    try:
        if not running(repo, token):
            return ""
    except Exception as e:                                                  # no answer from GitHub: do not wait for something that cannot be seen
        return f"could not ask GitHub whether {ITEMS_WORKFLOW} is running ({type(e).__name__})"
    start = clock()
    while clock() - start < max_minutes * 60:
        sleep(poll)
        try:
            if not running(repo, token):
                return f"waited {(clock() - start) / 60:.0f} minutes for {ITEMS_WORKFLOW} to finish"
        except Exception:
            return "lost sight of the workflow while waiting"
    return f"{ITEMS_WORKFLOW} was still running after {max_minutes:.0f} minutes"


def pull_items() -> None:
    """Takes the (possibly new) data file from the server's private folder again."""
    subprocess.run([sys.executable, "-m", "sites.yorokobu.privatedata", "pull", "yorokobu_items.json"], cwd=str(ROOT), check=False)


def _client() -> rakuten.Client | None:
    app_id, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app_id and key):
        return None
    cfg = json.loads((ROOT / "sites" / "yorokobu" / "config.json").read_text(encoding="utf-8"))
    return rakuten.Client(app_id, key, referer=cfg["site_url"].rstrip("/") + "/", affiliate_id=None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=36)
    ap.add_argument("--in", dest="src", default=str(ROOT / "data" / "yorokobu_items.json"))
    ap.add_argument("--out", default=str(ROOT / "out" / "yorokobu_items.json"))
    a = ap.parse_args(argv)
    src = Path(a.src)
    data = json.loads(src.read_text(encoding="utf-8")) if src.exists() else None
    c = ct.load()
    picks_file = ct.CONTENT_DIR / "picks.json"
    picks = json.loads(picks_file.read_text(encoding="utf-8")) if picks_file.exists() else {}
    out, why = prepare(data, c, picks, datetime.now(JST), a.max_hours, _client)
    if out is None:
        waited = wait_for_items_run(os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN"))
        if waited:
            print(f"items_fresh: {why}; {waited}")
            if src == ROOT / "data" / "yorokobu_items.json":
                pull_items()
            data = json.loads(src.read_text(encoding="utf-8")) if src.exists() else None
            out, why = prepare(data, c, picks, datetime.now(JST), a.max_hours, _client)
    print(f"items_fresh: {why}")
    if out is None:
        return 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
