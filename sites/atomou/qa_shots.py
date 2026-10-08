"""Screenshots of the built atomou site in a real (headless) Chrome, for looking at the layout with eyes.

    python sites/atomou/qa_shots.py [--dir out/atomou_preview] [--out out/atomou_qa] [--only home,my] [--skins basic,dark]

Headless Chrome does not go narrower than about 500px, so phone widths are checked in the Browser pane (375) and with sitecheck/layoutcheck;
this tool shows the 500 and 1280 layouts.  Writes <out>/<page>_<width>_<skin>.png.  ?today= and ?skin= (see app.js) make the pages repeatable."""
from __future__ import annotations

import argparse
import functools
import http.server
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TODAY = "2026-10-08"
PAGES = {  # name -> (path, {width: height})
    "home": ("/", {500: 3000, 1280: 2200}), "search": ("/search/?q=%E5%B9%B4%E8%B3%80", {500: 1900, 1280: 1500}), "my": ("/my/", {500: 1400}),
    "add": ("/add/?kind=anniversary", {500: 1700, 1280: 1300}), "skins": ("/skins/", {500: 3200, 1280: 2000}), "use": ("/use/", {500: 3000}),
    "usecase": ("/use/couple-anniversary/", {500: 1800, 1280: 1400}), "category": ("/c/deadline/", {500: 2400}), "manual": ("/manual/", {500: 5200}), "today": ("/today/", {500: 3400, 1280: 2200}),
}


def shot(base: str, name: str, path: str, w: int, h: int, skin: str, out: Path, chrome: str) -> Path:
    sep = "&" if "?" in path else "?"
    url = f"{base}{path}{sep}today={TODAY}&skin={skin}"
    dest = out / f"{name}_{w}_{skin}.png"
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", f"--user-data-dir={prof}", f"--window-size={w},{h}",
                        "--virtual-time-budget=5000", f"--screenshot={dest}", url], capture_output=True, timeout=120)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "out" / "atomou_preview"))
    ap.add_argument("--out", default=str(ROOT / "out" / "atomou_qa"))
    ap.add_argument("--only", default="")
    ap.add_argument("--skins", default="basic")
    ap.add_argument("--widths", default="")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=a.dir)
    handler.log_message = lambda *args: None  # type: ignore[attr-defined]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    only = set(filter(None, a.only.split(",")))
    widths = {int(x) for x in a.widths.split(",") if x}
    for name, (path, sizes) in PAGES.items():
        if only and name not in only:
            continue
        for w, h in sizes.items():
            if widths and w not in widths:
                continue
            for skin in a.skins.split(","):
                print(shot(base, name, path, w, h, skin, out, CHROME))
    srv.shutdown()


if __name__ == "__main__":
    main()
