"""The natural-Japanese publish gate (owner-approved 2026-10-20): the same check in the deploy (before the site check) and in publish.ps1 (before the push).

A RATCHET, not a wall.  The warnings that are already on the sites are written down once (data/style/baseline.json: a short hash of each mid/high finding, no text) and are
not counted again.  A new mid finding (a sentence that was not in the baseline) stops the publish; a high finding always stops it; a low one is only a warning.  The text that is
read is the real release AFTER the styleloop dictionary was applied, so a rewording that the dictionary fixes is not a failure and a dictionary that failed to apply is seen.

Per site (data/sites.json, "naturaljp_gate"):  off | shadow | ratchet.  shadow = the same report, as a warning, and the deploy goes on (the first week, to count false positives);
ratchet = it fails.  NATURALJP_GATE=<mode> in the environment overrides the register (an emergency switch in the workflow dispatch).
The gate never fails because of its own error: a crash, a missing baseline or an unreadable folder is a warning.

    python -m sokuhou.stylegate check release --site yorokobu          the deploy step
    python -m sokuhou.stylegate precheck                               publish.ps1: the sites the commits touch, built and checked
    python -m sokuhou.stylegate baseline --site kuma [--dir D]         write down the findings as they are NOW (a person's decision: do it only for a false positive or at the start)
    python -m sokuhou.stylegate baseline --site kuma --shrink          drop the baseline entries that are fixed (never adds)
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from sokuhou import naturaljp as nj

ROOT = nj.ROOT
DATA = ROOT / "data" / "style"
BASELINE = DATA / "baseline.json"
SITES_JSON = ROOT / "data" / "sites.json"
MODES = ("off", "shadow", "ratchet")
LEVELS = ("high", "mid")
SITE_LEVEL_PATH = "(サイト全体)"


# ------------------------------------------------------------------------------------------------------------------------------ keys and the baseline
def normalize(sentence: str) -> str:
    """A sentence as the baseline knows it: the same sentence with other numbers (a date, a count, a prefecture's figure) is the same finding."""
    s = unicodedata.normalize("NFKC", sentence)
    s = re.sub(r"\d+(?:[.,]\d+)*", "0", s)
    s = re.sub(r"\s+", "", s)
    return s[:120]


def key_of(h: nj.Hit) -> str:
    base = SITE_LEVEL_PATH if h.path == SITE_LEVEL_PATH else normalize(h.full or h.sentence)
    return f"{h.rule}:{hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]}"


def load_baseline(path: Path | None = None) -> dict:
    p = path or BASELINE
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "sites": {}}


def save_baseline(data: dict, path: Path | None = None) -> None:
    (path or BASELINE).parent.mkdir(parents=True, exist_ok=True)
    (path or BASELINE).write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def known_keys(base: dict, site: str) -> set[str] | None:
    s = base.get("sites", {}).get(site)
    if s is None:
        return None
    return {f"{rule}:{h}" for rule, hs in s.get("keys", {}).items() for h in hs}


def baseline_entry(hits: list[nj.Hit], today: str) -> dict:
    keys: dict[str, set[str]] = defaultdict(set)
    counts = Counter()
    seen = set()
    for h in hits:
        if h.level not in LEVELS:
            continue
        k = key_of(h)
        if k in seen:
            continue
        seen.add(k)
        counts[h.level] += 1
        rule, _, digest = k.partition(":")
        keys[rule].add(digest)
    return {"date": today, "counts": {"high": counts["high"], "mid": counts["mid"]}, "keys": {r: sorted(v) for r, v in sorted(keys.items())}}


# ------------------------------------------------------------------------------------------------------------------------------ the mode of a site
def load_sites() -> dict:
    try:
        return json.loads(SITES_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def mode_for(site: str, sites: dict | None = None) -> str:
    env = os.environ.get("NATURALJP_GATE", "").strip().lower()
    if env in MODES:
        return env
    sites = load_sites() if sites is None else sites
    mode = sites.get("defaults", {}).get("naturaljp_gate", "shadow")
    for s in sites.get("sites", []):
        if s.get("name") == site and s.get("naturaljp_gate"):
            mode = s["naturaljp_gate"]
    return mode if mode in MODES else "shadow"


# ------------------------------------------------------------------------------------------------------------------------------ the verdict
class Verdict:
    def __init__(self, site: str, mode: str, pages: int):
        self.site, self.mode, self.pages = site, mode, pages
        self.high: list[nj.Hit] = []            # always a failure
        self.new: list[nj.Hit] = []             # mid, not in the baseline: a failure
        self.old = 0                            # mid/high already in the baseline (not counted again)
        self.fixed = 0                          # in the baseline, not found any more
        self.low = 0
        self.note = ""                          # e.g. "no baseline"

    @property
    def failing(self) -> list[nj.Hit]:
        return self.high + self.new

    @property
    def fails(self) -> bool:
        return bool(self.failing)


def evaluate(hits: list[nj.Hit], site: str, mode: str, pages: int, base: dict) -> Verdict:
    v = Verdict(site, mode, pages)
    known = known_keys(base, site)
    if known is None:
        v.note = "このサイトには基準値(data/style/baseline.json)がありません。判定せず、警告だけにします。"
    seen: set[str] = set()
    for h in hits:
        if h.level == "low":
            v.low += 1
            continue
        k = key_of(h)
        if k in seen:
            continue
        seen.add(k)
        if known is None:
            continue
        if h.level == "high":
            v.high.append(h)                      # a high finding is a failure even when it is in the baseline
        elif k in known:
            v.old += 1
        else:
            v.new.append(h)
    if known is not None:
        v.fixed = len(known - seen)
    return v


# ------------------------------------------------------------------------------------------------------------------------------ messages
def explain(h: nj.Hit) -> str:
    r = nj.RULES[h.rule]
    sent = h.full or h.sentence
    sent = sent if len(sent) <= 160 else sent[:157] + "…"
    note = f"  {h.note}" if h.note else ""
    return (f"- {h.path}:{h.line}  [{h.level}] {h.rule}{note}\n"
            f"    文: 「{sent}」\n"
            f"    なぜ: {r.why}\n"
            f"    直し方: {r.fix}")


def fix_hint(site: str) -> str:
    return (f"直す場所: sites/{site}/ の元の文(content など)を言い直す。同じ文が多くのページに出るときは、辞書に1行足す: "
            f"`python -m sokuhou.styleloop add --site {site} --from \"元の文\" --to \"直した文\"`。"
            f"誤検出と判断したときは、担当セッションが窓口に知らせ、`python -m sokuhou.stylegate baseline --site {site}` で基準値に入れる(窓口が規則も直す)。")


def render(v: Verdict, limit: int = 40) -> str:
    head = (f"## 文章チェック(naturaljp ゲート) {v.site} — モード {v.mode}\n"
            f"読んだページ {v.pages} / 新しい mid {len(v.new)} / high {len(v.high)} / 基準値にある既存の警告 {v.old} / 直って基準値から外せる {v.fixed} / low(警告のみ) {v.low}")
    if v.note:
        head += f"\n{v.note}"
    if not v.fails:
        return head + "\n問題なし(新しく足された警告はありません)。"
    rows = sorted(v.failing, key=lambda h: (h.level != "high", h.rule, h.path, h.line))
    body = "\n".join(explain(h) for h in rows[:limit])
    more = f"\n… ほか {len(rows) - limit} 件" if len(rows) > limit else ""
    verdict = {"ratchet": "公開を止めます。", "shadow": "shadow モード: 公開は止めません(1週間の試運転。誤検出の判断材料として数えます)。", "off": ""}[v.mode]
    return f"{head}\n{verdict}\n{body}{more}\n{fix_hint(v.site)}"


def annotate(v: Verdict, limit: int = 15) -> str:
    kind = "error" if v.mode == "ratchet" else "warning"
    lines = []
    for h in sorted(v.failing, key=lambda h: (h.level != "high", h.path))[:limit]:
        sent = (h.full or h.sentence).replace("\n", " ")[:120]
        lines.append(f"::{kind} title=naturaljp {v.site} {h.rule}::{h.path}:{h.line} 「{sent}」 — {nj.RULES[h.rule].fix}")
    return "\n".join(lines)


def keys_line(v: Verdict) -> str:
    """The new mid findings as keys (rule:hash), so that the findings that turn out to be false positives in the real release can be written into the baseline from the log (`accept`)."""
    keys = sorted({key_of(h) for h in v.new})
    return f"GATEKEYS {v.site} {','.join(keys)}" if keys else ""


def shadow_line(v: Verdict) -> str:
    by_rule = Counter(h.rule for h in v.failing)
    rules = ", ".join(f"{r} {n}" for r, n in by_rule.most_common())
    return (f"SHADOW {dt.date.today().isoformat()} {v.site}: would-fail={'yes' if v.fails else 'no'} high={len(v.high)} new_mid={len(v.new)} "
            f"known={v.old} fixed={v.fixed} pages={v.pages}" + (f" rules=[{rules}]" if rules else ""))


# ------------------------------------------------------------------------------------------------------------------------------ the check
# Text that is published as a page only when the shop data answers (yorokobu's 詳しく読む articles /pick/<slug>/ are built from these files, and a local build does not draw them):
# the files are read too, so a new article cannot slip through.  The dictionary is applied to them in memory in every case (it is applied to the pages, not to these files).
SOURCE_TEXT = {"yorokobu": ("sites/yorokobu/content/features/*.json",)}


def source_hits(site: str, repo: Path | None = None) -> tuple[list[nj.Hit], int]:
    hits: list[nj.Hit] = []
    n = 0
    base = repo or ROOT
    for pat in SOURCE_TEXT.get(site, ()):
        for f in sorted(base.glob(pat)):
            try:
                raw = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            n += 1
            blocks = nj.blocks_from_json(nj.published_text(raw, site))
            hits += nj.check_blocks(blocks, f.relative_to(base).as_posix(), site, min_level="low")
    return hits, n


def collect(root: Path, site: str, dictionary: bool) -> tuple[list[nj.Hit], int]:
    hits, n = nj.check_path(root, site, (".html", ".htm"), min_level="low", dictionary=dictionary)
    more, m = source_hits(site)
    return hits + more, n + m


def run_check(root: Path, site: str, mode: str | None = None, dictionary: bool = False, baseline: dict | None = None) -> tuple[int, str, Verdict | None]:
    """(exit code, the report, the verdict).  The code is 1 only in ratchet mode with a finding; any problem of the gate itself is a warning and 0."""
    mode = mode or mode_for(site)
    if mode == "off":
        return 0, f"naturaljp gate {site}: off", None
    try:
        if not root.exists():
            return 0, f"::warning::naturaljp gate {site}: folder {root} not found - not checked", None
        hits, pages = collect(root, site, dictionary)
        v = evaluate(hits, site, mode, pages, load_baseline() if baseline is None else baseline)
    except Exception as e:                       # the gate must never stop a publish because of its own bug
        return 0, f"::warning::naturaljp gate {site}: crashed ({type(e).__name__}: {e}) - not checked", None
    text = render(v)
    code = 1 if (mode == "ratchet" and v.fails and not v.note) else 0
    return code, text, v


# ------------------------------------------------------------------------------------------------------------------------------ publish.ps1: the changed sites
def changed_files(base_ref: str) -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", f"{base_ref}...HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [x.strip() for x in r.stdout.splitlines() if x.strip()]


SHARED = ("sokuhou/naturaljp.py", "sokuhou/stylegate.py", "sokuhou/styleloop.py", "data/style/baseline.json", "data/sites.json")


def sites_touched(files: list[str], sites: dict | None = None, shared_all: bool = False) -> list[str]:
    sites = sites or load_sites()
    names = [s["name"] for s in sites.get("sites", [])]
    if shared_all and any(f in SHARED for f in files):          # a change of the tool itself: every site would be built here (minutes); the deploy checks them, `precheck --all` does it by hand
        return [n for n in names if n in nj.SITES]
    out = []
    for s in sites.get("sites", []):
        n = s["name"]
        pats = [p.replace("{name}", n) for p in (s.get("own") or sites.get("defaults", {}).get("own", []))] + list(s.get("owns", []))
        if n in nj.SITES and any(fnmatch.fnmatch(f, p) for f in files for p in pats):
            out.append(n)
    return out


PRECHECK_FAIL = 8          # the exit code publish.ps1 stops on; any other non-zero code (an import error, a crash) is the gate's own problem and only a warning there


def precheck(base_ref: str = "origin/main", only: list[str] | None = None, shared_all: bool = False) -> int:
    files = changed_files(base_ref)
    targets = only or sites_touched(files, shared_all=shared_all)
    worst = 0
    for site in targets:
        mode = mode_for(site)
        if mode == "off":
            continue
        try:
            out = nj.built_dir(site, rebuild=True, base=ROOT / "out" / "stylegate")
        except SystemExit as e:
            print(f"naturaljp gate {site}: could not build here ({e}) - skipped; the deploy checks it")
            continue
        code, text, v = run_check(out, site, mode, dictionary=True)
        print(text)
        if code:
            worst = PRECHECK_FAIL
    if not targets:
        print("naturaljp gate: no site's text is in these commits")
    return worst


# ------------------------------------------------------------------------------------------------------------------------------ baseline commands
KEYS_LINE = re.compile(r"GATEKEYS ([a-z0-9]+) ([a-z_]+:[0-9a-f]{12}(?:,[a-z_]+:[0-9a-f]{12})*)")


def cmd_accept(site: str, log: Path, only: set[str] | None) -> int:
    """Write the findings of a deploy log (the GATEKEYS line of this site) into the baseline: the false positives that only the real release showed.  A person's decision;
    --rule limits it to those rules.  Mid findings only (a high one is never excused)."""
    text = log.read_text(encoding="utf-8", errors="replace")
    keys: set[str] = set()
    for m in KEYS_LINE.finditer(text):
        if m.group(1) == site:
            keys |= set(m.group(2).split(","))
    keys = {k for k in keys if k.split(":")[0] in nj.RULES and nj.RULES[k.split(":")[0]].level == "mid" and (not only or k.split(":")[0] in only)}
    if not keys:
        print(f"{site}: no key to accept in {log}")
        return 2
    base = load_baseline()
    entry = base.setdefault("sites", {}).setdefault(site, {"date": dt.date.today().isoformat(), "counts": {"high": 0, "mid": 0}, "keys": {}})
    for k in sorted(keys):
        rule, _, digest = k.partition(":")
        lst = set(entry["keys"].get(rule, []))
        lst.add(digest)
        entry["keys"][rule] = sorted(lst)
    entry["counts"] = {"high": entry.get("counts", {}).get("high", 0), "mid": sum(len(v) for v in entry["keys"].values())}
    save_baseline(base)
    print(f"{site}: {len(keys)} key(s) written into the baseline: {', '.join(sorted({k.split(':')[0] for k in keys}))}")
    return 0

def cmd_baseline(site: str, directory: Path | None, shrink: bool) -> int:
    root = directory or nj.built_dir(site, rebuild=True, base=ROOT / "out" / "stylegate")
    hits, pages = collect(root, site, dictionary=directory is None)
    base = load_baseline()
    today = dt.date.today().isoformat()
    new = baseline_entry(hits, today)
    if shrink:
        old = base.get("sites", {}).get(site)
        if old is None:
            print(f"{site}: no baseline to shrink")
            return 2
        have = {f"{r}:{h}" for r, hs in new["keys"].items() for h in hs}
        kept = {r: [h for h in hs if f"{r}:{h}" in have] for r, hs in old["keys"].items()}
        kept = {r: hs for r, hs in kept.items() if hs}
        entry = {"date": old.get("date", today), "shrunk": today, "keys": kept}
        n = Counter()
        for r, hs in kept.items():
            n[nj.RULES[r].level if r in nj.RULES else "mid"] += len(hs)
        entry["counts"] = {"high": n["high"], "mid": n["mid"]}
        base["sites"][site] = entry
        print(f"{site}: {sum(len(v) for v in old['keys'].values())} → {sum(len(v) for v in kept.values())} entries")
    else:
        base.setdefault("sites", {})[site] = new
        print(f"{site}: baseline written: high {new['counts']['high']} / mid {new['counts']['mid']} ({pages} pages)")
    save_baseline(base)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stylegate", description="the natural-Japanese publish gate (ratchet)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("dir")
    c.add_argument("--site", required=True)
    c.add_argument("--mode", choices=MODES)
    c.add_argument("--apply-dictionary", action="store_true", help="read the text with the dictionary applied in memory (the deploy applies it to the folder first)")
    p = sub.add_parser("precheck")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--site", action="append")
    p.add_argument("--all", action="store_true", help="also build every site when the gate itself changed")
    b = sub.add_parser("baseline")
    b.add_argument("--site", required=True, choices=list(nj.SITES))
    b.add_argument("--dir")
    b.add_argument("--shrink", action="store_true")
    ac = sub.add_parser("accept", help="write the findings of a deploy log (GATEKEYS line) into the baseline")
    ac.add_argument("--site", required=True, choices=list(nj.SITES))
    ac.add_argument("--log", required=True)
    ac.add_argument("--rule", action="append")
    sub.add_parser("modes")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "modes":
        for s in nj.SITES:
            print(f"{s}: {mode_for(s)}")
        return 0
    if args.cmd == "accept":
        return cmd_accept(args.site, Path(args.log), set(args.rule) if args.rule else None)
    if args.cmd == "baseline":
        return cmd_baseline(args.site, Path(args.dir) if args.dir else None, args.shrink)
    if args.cmd == "precheck":
        return precheck(args.base, args.site, args.all)
    code, text, v = run_check(Path(args.dir), args.site, args.mode, dictionary=args.apply_dictionary)
    print(text)
    if v is not None:
        ann = annotate(v)
        if ann:
            print(ann)
        if v.mode == "shadow":
            print(shadow_line(v))
        if keys_line(v):
            print(keys_line(v))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            try:
                with open(summary, "a", encoding="utf-8") as f:
                    f.write(text + ("\n\n`" + shadow_line(v) + "`\n" if v.mode == "shadow" else "\n") + "\n")
            except OSError:
                pass
    return code


if __name__ == "__main__":
    sys.exit(main())
