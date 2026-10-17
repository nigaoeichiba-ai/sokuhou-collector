"""Which sites does a push publish?  The plan step of .github/workflows/deploy.yml (2026-10-18), and the one place that knows whose a file is.

    python -m sokuhou.deployplan plan --event push --before <sha> --after <sha> [--only kuma]

reads data/sites.json (the site register) and prints the matrix of the sites to build, test and publish (one entry per site; a site with nothing to do is
not in it, so it costs no runner).  It replaces the shell 'Gate' of the old workflow and keeps its meaning:

  * a push of another site's own files (sites/<name>/, its tests, its data) does not publish this site; anything shared (the collector, kit, workflows,
    other data, other tests, requirements) publishes every site; whatever cannot be told is published;
  * the comparison starts at the commit the LIVE site was built from (the build writes it to /deployed-sha.txt), not only at the push's BEFORE: while a site's
    previous job runs, GitHub keeps only the newest waiting job of a concurrency group and cancels the older one, and the newest push may not touch that site
    (2026-10-16, minna's +9 series).  No such file, or a commit this checkout does not know: the push's own BEFORE;
  * a schedule or a manual run publishes every site (or the one named by --only); the 'fast lane' is only for a push whose relevant files are all content.

The register's `own` patterns are shell-style (fnmatch: `*` also crosses `/`), `{name}` is the site's name; a site's `owns` are added to them.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sites.json"
SHA = re.compile(r"[0-9a-f]{40}")
ZEROS = re.compile(r"0+")
NAME = re.compile(r"[a-z][a-z0-9]*")
SKIPPABLE = ("sites/", "sokuhou/", "data/", "tests/")   # what the push trigger of deploy.yml watches (besides requirements.txt and the workflow itself)


class RegistryError(ValueError):
    pass


BUILTIN = {"min_pages": 20, "min_cards": 0, "probe": "/sitemap.xml", "needs_var": False, "live_sha": True, "watch": True, "group": "deploy-{name}", "timeout_minutes": 90,
           "build": "python sites/{name}/build.py --release --out release",
           "own": ["sites/{name}/*", "tests/test_{name}*", "tests/fixtures/{name}/*", "data/{name}*", "data/style/rewrites/{name}.json"]}   # what data/sites.json says too; a register without "defaults" still works


def _fill(value, name: str, env: dict | None = None):
    """{name} and {env:VAR} in a register string."""
    if isinstance(value, str):
        value = value.replace("{name}", name)
        value = re.sub(r"\{env:([A-Z0-9_]+)\}", lambda m: (env if env is not None else os.environ).get(m.group(1), ""), value)
    return value


def load_registry(path: Path | str = REGISTRY, env: dict | None = None) -> dict:
    """The register with the defaults filled in: {'ignore': [...], 'sites': {name: {...}}} (sites in file order)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    defaults = {**BUILTIN, **raw.get("defaults", {})}
    sites: dict[str, dict] = {}
    for entry in raw.get("sites", []):
        name = entry.get("name", "")
        if not NAME.fullmatch(name):
            raise RegistryError(f"site name {name!r}: lower-case letters and digits, starting with a letter")
        if name in sites:
            raise RegistryError(f"site {name!r} is listed twice")
        if not entry.get("domain") or not entry.get("marker"):
            raise RegistryError(f"site {name!r}: domain and marker are needed")
        site = {**defaults, **entry}
        site["own"] = [_fill(p, name) for p in defaults.get("own", [])] + [_fill(p, name) for p in entry.get("owns", [])]
        site["fast_lane"] = list(entry.get("fast_lane", []))
        for key in ("build", "probe", "group", "marker"):
            site[key] = _fill(site[key], name, env)
        site["dir"] = entry.get("dir", entry["domain"])
        site["url"] = entry.get("url", "https://" + entry["domain"])
        sites[name] = site
    domains = [s["domain"] for s in sites.values()]
    if len(set(domains)) != len(domains):
        raise RegistryError("two sites share a domain")
    return {"ignore": list(raw.get("ignore", [])), "sites": sites}


def owner_of(path: str, reg: dict) -> str:
    """The site that owns a file; 'none' for a file that changes no published page (the judge's notes); 'shared' for the rest (it publishes every site)."""
    for name, site in reg["sites"].items():
        if any(fnmatch.fnmatchcase(path, p) for p in site["own"]):
            return name
    if any(fnmatch.fnmatchcase(path, p) for p in reg["ignore"]):
        return "none"
    return "shared"


def is_trigger(path: str) -> bool:
    return path.startswith(SKIPPABLE) or path in ("requirements.txt", ".github/workflows/deploy.yml")


def touches(site: str, files: list[str], reg: dict, changed_entries: set[str] | None = None) -> bool:
    """Does a push with these files publish `site`? (what the push trigger and the plan decide; the watchdog asks the same)"""
    return bool(relevant_files(site, files, reg, changed_entries))


REGISTRY_FILE = "data/sites.json"


def registry_changes(base: str, after: str, cwd: Path = ROOT) -> set[str] | None:
    """The sites whose register entry differs between two commits (a new site, a changed build command); None when that cannot be told or the shared part
    (defaults, ignore list) changed: then every site is affected.  Adding a site to the register must not republish the others."""
    def read(rev: str):
        out = _git("show", f"{rev}:{REGISTRY_FILE}", cwd=cwd)
        return json.loads(out.stdout) if out.returncode == 0 else None
    try:
        old, new = read(base), read(after)
    except ValueError:
        return None
    if old is None or new is None:
        return None
    if {k: v for k, v in old.items() if k != "sites"} != {k: v for k, v in new.items() if k != "sites"}:
        return None
    a = {e.get("name"): e for e in old.get("sites", [])}
    b = {e.get("name"): e for e in new.get("sites", [])}
    return {n for n in set(a) | set(b) if a.get(n) != b.get(n)}


def relevant_files(site: str, files: list[str], reg: dict, changed_entries: set[str] | None = None) -> list[str]:
    """The changed files that concern `site`.  Files the push trigger does not watch (other workflows, README) concern no site;
    the register file concerns the sites whose entry changed (`changed_entries`; None = all)."""
    out = []
    for f in files:
        if not is_trigger(f):
            continue
        if f == REGISTRY_FILE:
            if changed_entries is None or site in changed_entries:
                out.append(f)
        elif owner_of(f, reg) in ("shared", site):
            out.append(f)
    return out


def is_fast(site: dict, relevant: list[str]) -> bool:
    return bool(site["fast_lane"]) and bool(relevant) and all(any(fnmatch.fnmatchcase(f, p) for p in site["fast_lane"]) for f in relevant)


def _git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def served_sha(site: dict, cwd: Path = ROOT, timeout: int = 20) -> str:
    """The commit the live site was built from, when its /deployed-sha.txt says one this checkout knows; otherwise ''."""
    if not site.get("live_sha", True):
        return ""
    try:
        with urllib.request.urlopen(urllib.request.Request(site["url"] + "/deployed-sha.txt", headers={"User-Agent": "sokuhou-deployplan"}), timeout=timeout) as r:
            text = r.read(200).decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001 - an unreadable file only means the fallback comparison
        return ""
    if SHA.fullmatch(text) and _git("cat-file", "-e", text + "^{commit}", cwd=cwd).returncode == 0:
        return text
    return ""


def decide(name: str, site: dict, *, event: str, only: str, before: str, after: str, served: str, cwd: Path = ROOT) -> dict:
    """{'go': bool, 'fast': bool, 'why': str} for one site."""
    if only and only != name:
        return {"go": False, "fast": False, "why": f"this run is for {only} only"}
    base = served or before
    if event != "push":
        return {"go": True, "fast": False, "why": f"{event}: every site"}
    if not base or ZEROS.fullmatch(base):
        return {"go": True, "fast": False, "why": "no base commit: published"}
    why_base = f"compared with the live commit {served[:10]}" if served else f"compared with the push's before {base[:10]}"
    diff = _git("diff", "--name-only", base, after, cwd=cwd)
    files = [f for f in diff.stdout.splitlines() if f.strip()] if diff.returncode == 0 else []
    if not files:
        return {"go": True, "fast": False, "why": f"{why_base}: no list of changed files, so published"}
    return {"files": files, "why_base": why_base, "base": base}


def plan(reg: dict, *, event: str, only: str, before: str, after: str, cwd: Path = ROOT, fetch_served=True) -> dict:
    """{'include': [matrix entries], 'decisions': {site: {...}}}"""
    if only and only not in reg["sites"]:
        raise RegistryError(f"--only {only!r}: no such site (register: {', '.join(reg['sites'])})")
    names = list(reg["sites"])
    for n in names:
        if not reg["sites"][n]["probe"].startswith("/"):
            raise RegistryError(f"site {n}: the probe path {reg['sites'][n]['probe']!r} is not a path (an {{env:...}} placeholder with no value?)")
    served: dict[str, str] = {n: "" for n in names}
    if event == "push" and fetch_served:
        cand = [n for n in names if not only or only == n]
        with ThreadPoolExecutor(16) as ex:
            for n, sha in zip(cand, ex.map(lambda n: served_sha(reg["sites"][n], cwd), cand)):
                served[n] = sha
    include, decisions = [], {}
    for n in names:
        site = reg["sites"][n]
        d = decide(n, site, event=event, only=only, before=before, after=after, served=served[n], cwd=cwd)
        if "files" in d:
            changed = registry_changes(d["base"], after, cwd) if REGISTRY_FILE in d["files"] else None
            rel = relevant_files(n, d["files"], reg, changed)
            if not rel:
                d = {"go": False, "fast": False, "why": f"{d['why_base']}: only other sites' files changed"}
            else:
                fast = is_fast(site, rel)
                d = {"go": True, "fast": fast, "why": f"{d['why_base']}: {len(rel)} of {len(d['files'])} changed files concern it" + (" (content only: fast lane)" if fast else "")}
        decisions[n] = d
        if d["go"]:
            include.append({"site": n, "dir": site["dir"], "url": site["url"], "build": site["build"], "min_pages": site["min_pages"], "min_cards": site["min_cards"],
                            "marker": site["marker"], "probe": site["probe"], "group": site["group"], "fast": d["fast"], "timeout": site["timeout_minutes"]})
    return {"include": include, "decisions": decisions}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--registry", default=str(REGISTRY))
    p.add_argument("--event", default=os.environ.get("EVENT", "push"))
    p.add_argument("--only", default=os.environ.get("ONLY", ""))
    p.add_argument("--before", default=os.environ.get("BEFORE", ""))
    p.add_argument("--after", default=os.environ.get("AFTER", "HEAD"))
    a = ap.parse_args(argv)
    reg = load_registry(a.registry)
    result = plan(reg, event=a.event, only=a.only, before=a.before, after=a.after)
    lines = [f"| {n} | {'**publish**' if d['go'] else 'skip'}{' (fast lane)' if d['fast'] else ''} | {d['why']} |" for n, d in result["decisions"].items()]
    summary = "### deploy plan\n\n| site | decision | why |\n|---|---|---|\n" + "\n".join(lines) + "\n"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary)
    matrix = json.dumps({"include": result["include"]}, ensure_ascii=False, separators=(",", ":"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"matrix={matrix}\ncount={len(result['include'])}\n")
    else:
        print(matrix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
