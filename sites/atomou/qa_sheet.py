"""Contact sheets: the same page in every skin side by side (so colour/contrast problems stand out).

    python sites/atomou/qa_sheet.py [--path /] [--w 500] [--h 1500] [--per 7] [--scale 0.5]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path

from PIL import Image, ImageDraw

from sites.atomou import skins
from sites.atomou.qa_shots import CHROME, ROOT, shot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "out" / "atomou_preview"))
    ap.add_argument("--out", default=str(ROOT / "out" / "atomou_qa"))
    ap.add_argument("--path", default="/")
    ap.add_argument("--w", type=int, default=500)
    ap.add_argument("--h", type=int, default=1500)
    ap.add_argument("--per", type=int, default=7)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--tag", default="home")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=a.dir)
    handler.log_message = lambda *args: None  # type: ignore[attr-defined]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    shots = []
    for s in skins.SKINS:
        dest = shot(base, a.tag, a.path, a.w, a.h, s["id"], out, CHROME)
        shots.append((s["id"], s["name"], dest))
    srv.shutdown()
    for i in range(0, len(shots), a.per):
        chunk = shots[i:i + a.per]
        w, h = int(a.w * a.scale), int(a.h * a.scale)
        sheet = Image.new("RGB", (w * len(chunk) + 6 * (len(chunk) - 1), h + 20), "white")
        d = ImageDraw.Draw(sheet)
        for j, (sid, name, p) in enumerate(chunk):
            im = Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS)
            sheet.paste(im, (j * (w + 6), 20))
            d.text((j * (w + 6) + 2, 4), sid, fill="black")
        dest = out / f"sheet_{a.tag}_{i // a.per + 1}.png"
        sheet.save(dest)
        print(dest)


if __name__ == "__main__":
    main()
