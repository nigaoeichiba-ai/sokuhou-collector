"""Builds shiken-nittei.com (資格・試験への道).  python sites/shiken/build.py --release --out release

Since 2026-11-13 the site is the design of renewal/template/ (the owner's template: static pages made by running its browser templates against a DOM, the schedule in
renewal/template/schedule/registry.json).  This file:

  1. runs `node renewal/template/scripts/build-site.mjs` (Node 18+; the deploy workflow sets Node up) into a folder,
  2. adds what the template does not have: the contact receiver (contact/send.php), the visit counter (assets/measure.js, m/t.gif; the privacy page says what it counts),
     the Search Console verification file,
  3. copies the result to --out.

The pages are made again on every build (the lists of coming dates and the 'days left' of the detail pages are of the day of the build).  No product data of any mall is read here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parents[1]
sys.path.insert(0, str(ROOT))
from sokuhou import contactform, measure  # noqa: E402

TEMPLATE = SITE / "renewal" / "template"
CONFIG = json.loads((SITE / "config.json").read_text(encoding="utf-8"))


def find_node() -> str:
    """Node: the one on PATH (the deploy workflow's), NODE_BIN, or - on the owner's PC, where Node is not installed - Deno's Node-compatible launcher."""
    for cand in (os.environ.get("NODE_BIN"), shutil.which("node")):
        if cand:
            return cand
    real = Path("C:/Program Files/nodejs/node.exe")      # the owner installed Node 22 here (2026-11-13); a session started before that may not have it on PATH
    if real.exists():
        return str(real)
    home = Path.home() / "AppData" / "Local" / "deno" / "node_compat_bin" / "node.exe"
    if home.exists():
        return str(home)
    raise RuntimeError("Node.js was not found: put node on PATH (or set NODE_BIN)")


def make_site(out: Path, today: str | None = None) -> dict:
    """The whole site into `out` (which is emptied).  `today` (YYYY-MM-DD, Japan time) is for tests; the real build uses the clock."""
    out = Path(out).resolve()      # the Node build runs in the template folder: a relative --out (the workflow's `release`) must be made absolute here
    if out.exists():
        for child in out.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if today:
        env["SHIKEN_TODAY"] = today
    node = find_node()
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([node, str(TEMPLATE / "scripts" / "build-site.mjs"), "--out", str(out)], cwd=str(TEMPLATE), env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("build-site.mjs failed:\n" + r.stdout[-2000:] + r.stderr[-4000:])
    info = json.loads(r.stdout.strip().splitlines()[-1])
    finish(out)
    return info


def finish(out: Path) -> None:
    tag = f'<script src="/assets/measure.js?v={hashlib.sha1(measure.MEASURE_JS.encode()).hexdigest()[:8]}" defer></script>'
    for f in out.rglob("*.html"):
        html = f.read_text(encoding="utf-8")
        if "</head>" in html and "/assets/measure.js" not in html:
            f.write_text(html.replace("</head>", tag + "</head>", 1), encoding="utf-8", newline="\n")
    (out / "assets").mkdir(exist_ok=True)
    (out / "assets" / "measure.js").write_text(measure.MEASURE_JS, encoding="utf-8", newline="\n")
    (out / "m").mkdir(exist_ok=True)
    (out / "m" / "t.gif").write_bytes(measure.GIF)
    cfg = dict(CONFIG)
    (out / "contact").mkdir(exist_ok=True)
    (out / "contact" / "send.php").write_text(contactform.send_php(cfg), encoding="utf-8", newline="\n")
    v = cfg.get("google_site_verification")
    if v:
        if not re.fullmatch(r"google[0-9a-f]{16}\.html", v):
            raise RuntimeError("google_site_verification must look like google<16 hex>.html")
        (out / v).write_text(f"google-site-verification: {v}\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="release")
    ap.add_argument("--release", action="store_true")      # kept for the shared build command; the output is the same
    args = ap.parse_args(argv)
    info = make_site(Path(args.out))
    print(f"shiken: {info['pages']} pages, {info['files']} files ({info['today']}) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
