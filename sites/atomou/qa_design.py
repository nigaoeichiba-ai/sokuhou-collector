"""Look at every skin on every kind of page, in a real Chrome (Playwright), and measure what can be measured.

    python sites/atomou/qa_design.py [--dir out/atomou_design] [--out out/atomou_design_qa] [--skins basic,pop] [--pages home,calendar] [--widths 375,500,1280] [--sheets]

For each skin x page x width it writes <out>/<page>_<width>_<skin>.png (the whole page) and prints, per combination, what the browser measured:
  overflow   the page is wider than the window (a sideways scroll)
  tap        a button / link / chip / calendar day smaller than 44px (height) in its box
  clipped    a heading, card title or button whose text is cut off by its own box
  Skins are applied the way the site does it: ?skin= (app.js) puts data-skin and the shape attributes on <html>.
--sheets also writes contact sheets (all skins side by side per page and width) as <out>/sheet_<page>_<width>_<n>.png.
Own days are seeded in localStorage so the calendar, plan and "mine" blocks have something in them (ids o1..o6, one of them a quiet "memorial" day)."""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sites.atomou import skins  # noqa: E402

TODAY = "2026-10-08"
PAGES = {  # name -> path
    "home": "/", "calendar": "/calendar/", "plan": "/plan/?key=m:o1", "search": "/search/?q=%E5%B9%B4%E8%B3%80", "add": "/add/?kind=anniversary",
    "skins": "/skins/", "manual": "/manual/", "my": "/my/", "category": "/c/deadline/", "event": None,
}
SEED = {
    "v": 1, "updated": "2026-10-08T00:00:00.000Z", "deleted": [], "saved": [], "order": [], "genre": {},
    "entries": [
        {"id": "o1", "title": "家族で行く旅行", "date": "2026-10-12", "precision": "day", "kind": "event", "quiet": False, "yearly": False, "every100": False, "alarm": "morning", "time": "09:30", "created": "2026-10-01"},
        {"id": "o2", "title": "禁煙をはじめた日", "date": "2025-09-01", "precision": "day", "kind": "since", "quiet": False, "yearly": False, "every100": True, "alarm": "none", "time": "", "created": "2026-10-01"},
        {"id": "o3", "title": "結婚記念日", "date": "2015-10-20", "precision": "day", "kind": "anniversary", "quiet": False, "yearly": True, "every100": False, "alarm": "week", "time": "", "created": "2026-10-01"},
        {"id": "o4", "title": "祖母を思う日", "date": "2020-10-14", "precision": "day", "kind": "memorial", "quiet": True, "yearly": True, "every100": False, "alarm": "none", "time": "", "created": "2026-10-01"},
        {"id": "o5", "title": "確定申告の準備", "date": "2026-10-09", "precision": "day", "kind": "until", "quiet": False, "yearly": False, "every100": False, "alarm": "morning", "time": "", "created": "2026-10-01"},
        {"id": "o6", "title": "歯医者の予約", "date": "2026-10-08", "precision": "day", "kind": "event", "quiet": False, "yearly": False, "every100": False, "alarm": "morning", "time": "15:00", "created": "2026-10-01"},
    ],
    "notes": {"m:o1": {"memo": "持ち物: 切符、傘、お土産のリスト", "tasks": [{"id": "t1", "before": 7, "text": "宿を予約する", "done": True}, {"id": "t2", "before": 1, "text": "荷物をつめる", "done": False}, {"id": "t3", "before": 3, "text": "天気を確認する", "done": False}]},
              "m:o5": {"memo": "", "tasks": [{"id": "t4", "before": 0, "text": "書類をそろえる", "done": False}]}},
    "prefs": {"skin": "basic", "big": False, "alarm": "morning", "stats": False, "blocks": {"order": [], "hidden": []}},
}
MEASURE = """() => {
  const w = innerWidth, out = {overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - w, tap: [], clipped: []};
  const nm = (e) => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/)[0] : '') + ':' + (e.textContent || '').trim().slice(0, 12);
  document.querySelectorAll('a.btn,button.btn,.chip,header.site nav a,.cal-cell,.cats a,.tile,.mini').forEach(e => {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || !r.width) return;
    if (e.closest('[hidden],.block-off')) return;
    if (r.height < 43.5) out.tap.push(nm(e) + ' h=' + r.height.toFixed(0));
  });
  document.querySelectorAll('h1,h2,h3,.btn,.chip,.c-title,header.site nav a,.cats a').forEach(e => {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || e.closest('[hidden]')) return;
    if (e.scrollWidth > e.clientWidth + 2 && cs.overflow !== 'visible') out.clipped.push(nm(e) + ' sw=' + e.scrollWidth + '>' + e.clientWidth);
  });
  out.right = [];
  document.querySelectorAll('main *, header.site *, footer.site *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width && r.right > w + 1 && !e.closest('.chips.scroll,.cal-grid,svg')) out.right.push(nm(e) + ' r=' + r.right.toFixed(0));
  });
  out.right = out.right.slice(0, 4);
  return out;
}"""


def serve(directory: str):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # no request log
            pass

    handler = functools.partial(Quiet, directory=directory)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> None:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "out" / "atomou_design"))
    ap.add_argument("--out", default=str(ROOT / "out" / "atomou_design_qa"))
    ap.add_argument("--skins", default="")
    ap.add_argument("--pages", default="home,calendar,plan,search,add,skins,manual")
    ap.add_argument("--widths", default="375,500,1280")
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--no-shot", action="store_true")
    ap.add_argument("--crop", type=int, default=1500, help="keep only the top N px of each page in the pictures (0 = the whole page)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    srv = serve(a.dir)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    wanted = [s for s in a.skins.split(",") if s] or skins.ids()
    pages = [p for p in a.pages.split(",") if p]
    widths = [int(w) for w in a.widths.split(",") if w]
    # one event page for the event view
    ev = sorted((Path(a.dir) / "e").glob("*/index.html"))
    PAGES["event"] = "/e/" + ev[0].parent.name + "/" if ev else "/"
    problems = 0
    shots: dict[tuple, list] = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for w in widths:
            ctx = b.new_context(viewport={"width": w, "height": 900})
            ctx.add_init_script("try{if(!localStorage.getItem('atomou.v1'))localStorage.setItem('atomou.v1'," + json.dumps(json.dumps(SEED)) + ")}catch(e){}")
            pg = ctx.new_page()
            errors: list[str] = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
            for name in pages:
                for sid in wanted:
                    path = PAGES[name]
                    url = f"{base}{path}{'&' if '?' in path else '?'}today={TODAY}&skin={sid}"
                    errors.clear()
                    pg.goto(url, wait_until="load")
                    pg.wait_for_timeout(450)
                    m = pg.evaluate(MEASURE)
                    notes = []
                    if m["overflow"] > 1:
                        notes.append(f"OVERFLOW {m['overflow']}px {m['right']}")
                    if m["tap"]:
                        notes.append("tap<44: " + ", ".join(m["tap"][:4]))
                    if m["clipped"]:
                        notes.append("clipped: " + ", ".join(m["clipped"][:3]))
                    if errors:
                        notes.append("console: " + errors[0][:100])
                    if not a.no_shot:
                        dest = out / f"{name}_{w}_{sid}.png"
                        if a.crop:
                            pg.screenshot(path=str(dest), full_page=True, clip={"x": 0, "y": 0, "width": w, "height": a.crop})
                        else:
                            pg.screenshot(path=str(dest), full_page=True)
                        shots.setdefault((name, w), []).append((sid, dest))
                    if notes:
                        problems += 1
                        print(f"{name:9} {w:5} {sid:14} " + " | ".join(notes))
            ctx.close()
        b.close()
    srv.shutdown()
    print(f"{problems} combinations with something to look at")
    if a.sheets:
        from PIL import Image, ImageDraw
        for (name, w), lst in shots.items():
            per = 7 if w <= 500 else 4
            scale = 0.5 if w <= 500 else 0.34
            maxh = 2200 if w <= 500 else 1300
            for i in range(0, len(lst), per):
                chunk = lst[i:i + per]
                ims = [(sid, Image.open(d).convert("RGB")) for sid, d in chunk]
                tw = int(w * scale)
                ims = [(sid, im.resize((tw, int(im.height * tw / im.width)))) for sid, im in ims]
                h = min(maxh, max(im.height for _, im in ims)) + 18
                sheet = Image.new("RGB", (tw * len(ims) + 6 * (len(ims) - 1), h), "white")
                dr = ImageDraw.Draw(sheet)
                for j, (sid, im) in enumerate(ims):
                    sheet.paste(im.crop((0, 0, tw, h - 18)), (j * (tw + 6), 18))
                    dr.text((j * (tw + 6) + 2, 3), sid, fill="black")
                dest = out / f"sheet_{name}_{w}_{i // per + 1}.png"
                sheet.save(dest)
                print(dest)


if __name__ == "__main__":
    main()
