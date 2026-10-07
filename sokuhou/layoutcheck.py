"""Phone-width layout check of a BUILT site, measured in a real (headless) Chrome.  Run in CI before every deploy.

    python -m sokuhou.layoutcheck release --base https://minna-no-illust.com

Why: pages that look fine in a desktop screenshot broke on phones (the header links turned into one-character-wide vertical text, wide tables pushed the
page sideways) and nothing measured it.  This loads sample pages of every kind of page in iframes of 300 / 375 / 768 px (an iframe's width is what the page's
media queries see) and measures:
  overflow   the page is wider than the viewport (a sideways scroll on a phone); names the elements that stick out
  squeezed   readable text (a link, a heading, a paragraph, a cell) squeezed into a column narrower than 40px, i.e. vertical text
  nav        a header/nav link narrower than 9px per character (vertical text) or taller than 90px
  images     an image that is not lazy and failed to load
If Chrome is missing the check FAILS: "could not measure" is never reported as "fine".
"""
from __future__ import annotations

import argparse
import functools
import html as _html
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

CHROME_PATHS = (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser")
WIDTHS = (300, 375, 768)

SCENARIO = r"""
const PAGES = __PAGES__, WIDTHS = __WIDTHS__;
const out = [];
const wait = (ms) => new Promise(r => setTimeout(r, ms));
function inScroller(el) {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX;
    if (o === 'auto' || o === 'scroll' || o === 'hidden') return true;
  }
  return false;
}
function name(el) { return el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''); }
function measure(d, w) {
  const res = {overflow: 0, offenders: [], squeezed: [], nav: [], images: []};
  const de = d.documentElement;
  res.overflow = Math.max(de.scrollWidth, d.body ? d.body.scrollWidth : 0) - w;
  if (res.overflow > 1) {
    for (const el of d.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > w + 1 && !inScroller(el) && getComputedStyle(el).position !== 'fixed') { res.offenders.push(name(el) + ' (' + Math.round(r.right) + 'px)'); if (res.offenders.length >= 3) break; }
    }
  }
  for (const el of d.body.querySelectorAll('a, h1, h2, h3, p, li, td, th, button, label')) {
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
    if (own.length < 5) continue;
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (r.width === 0 || r.height <= 2 || cs.display === 'none' || cs.visibility === 'hidden' || el.closest('[aria-hidden="true"]')) continue;     // (a 1px-high box is a visually hidden field such as a honeypot)
    if (cs.display.startsWith('inline') && el.tagName !== 'A') continue;
    if (r.width < 40 && !el.closest('[hidden]')) { res.squeezed.push(name(el) + ' ' + Math.round(r.width) + 'px "' + own.slice(0, 12) + '"'); if (res.squeezed.length >= 3) break; }
  }
  for (const a of d.querySelectorAll('header a, nav a')) {
    const r = a.getBoundingClientRect(), cs = getComputedStyle(a);
    if (r.width === 0 || cs.display === 'none') continue;
    const len = (a.textContent || '').trim().length;
    if (r.width < Math.min(36, 9 * len) || r.height > 90) { res.nav.push((a.textContent || '').trim().slice(0, 10) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); if (res.nav.length >= 3) break; }
  }
  for (const i of d.images) {
    // a picture from another site (a map tile) is blocked on purpose while measuring, so only the site's own pictures can be "broken"
    if (i.complete && i.naturalWidth === 0 && i.getAttribute('src') && !i.hidden && i.loading !== 'lazy' && new URL(i.src, location.href).origin === location.origin) { res.images.push(i.getAttribute('src').slice(0, 60)); if (res.images.length >= 3) break; }
  }
  return res;
}
(async () => {
  try {
    for (const w of WIDTHS) {
      const f = document.createElement('iframe'); f.style.cssText = 'width:' + w + 'px;height:900px;border:0'; document.body.appendChild(f);
      for (const url of PAGES) {
        let loaded = false;
        await new Promise(r => { const t = setTimeout(r, 20000); f.onload = () => { loaded = true; clearTimeout(t); r(); }; f.src = url; });
        await wait(100);
        let m;
        try { m = measure(f.contentDocument, w); } catch (e) { m = {overflow: 0, offenders: [], squeezed: [], nav: [], images: [], failed: String(e)}; }
        if (!loaded) m.failed = 'the page did not finish loading in 20 s';
        m.url = url; m.w = w; out.push(m);
      }
      f.remove();
    }
  } catch (e) { out.push({error: String(e)}); }
  document.getElementById('out').textContent = JSON.stringify(out);
  fetch('/_done');       // releases the held image below, so that the outer page's load event (what --dump-dom waits for) comes only now
})();
"""


def find_chrome() -> str | None:
    return next((p for p in CHROME_PATHS if Path(p).exists()), None) or shutil.which("google-chrome") or shutil.which("chromium")


def run_chrome(chrome: str, url: str, attempts: int = 3, timeout: int = 150) -> str:
    """The DOM after the scripts ran.  A headless Chrome occasionally stalls, so a stalled run is killed and tried again."""
    for attempt in range(attempts):
        profile = tempfile.mkdtemp(prefix="layoutcheck_")
        try:
            r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={profile}",
                                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",     # only the site itself loads: no ad scripts, no slow third parties
                                "--dump-dom", url], capture_output=True, timeout=timeout)
            out = r.stdout.decode("utf-8", "replace")
            if 'id="out"' in out and re.search(r'<pre id="out">\s*\[', out):
                return out
        except subprocess.TimeoutExpired:
            pass
        finally:
            shutil.rmtree(profile, ignore_errors=True)
    return ""


def pick_pages(root: Path, cap: int = 60) -> list[str]:
    """Sample pages of EVERY kind: the pages are grouped by their first path segment (gift, theme, month, illust...) and the first, the middle and the last
    of each group are taken, so a kind of page that exists once is never left out."""
    paths = []
    for sm in sorted(root.glob("sitemap*.xml")):
        for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.read_text(encoding="utf-8", errors="replace")):
            p = urlparse(u).path or "/"
            if p.endswith("/") and (root / p.lstrip("/") / "index.html").exists():
                paths.append(p)
    paths = sorted(set(paths))
    groups: dict[str, list[str]] = {}
    for p in paths:
        groups.setdefault(p.strip("/").split("/")[0], []).append(p)
    chosen: list[str] = []
    for seg, ps in groups.items():
        for p in ([ps[0], ps[len(ps) // 2], ps[-1]] if len(ps) > 2 else ps):
            if p not in chosen:
                chosen.append(p)
    if "/" in paths and "/" not in chosen:
        chosen.insert(0, "/")
    return chosen[:cap]


def measure(root: Path, pages: list[str], widths=WIDTHS, batch: int = 8) -> list[dict]:
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome was not found: the layout cannot be measured (this is a failure, not a pass)")

    done = threading.Event()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_GET(self):
            if self.path == "/_hold.png":          # held until the scenario says it is finished (a Chrome run is retried: the event is re-armed per run)
                done.wait(timeout=140)
                self.send_response(204)
                self.end_headers()
            elif self.path == "/_done":
                done.set()
                self.send_response(204)
                self.end_headers()
            else:
                super().do_GET()

    class Server(http.server.ThreadingHTTPServer):
        def handle_error(self, request, client_address):      # Chrome drops connections when an iframe is replaced: not an error
            pass

    server = Server(("127.0.0.1", 0), functools.partial(Handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    results: list[dict] = []
    try:
        for i in range(0, len(pages), batch):
            chunk = pages[i:i + batch]
            script = SCENARIO.replace("__PAGES__", json.dumps(chunk)).replace("__WIDTHS__", json.dumps(list(widths)))
            name = f"_layoutcheck_{i}.html"
            (root / name).write_text(f'<!doctype html><meta charset="utf-8"><pre id="out"></pre><img src="/_hold.png" width="1" height="1" alt=""><script>{script}</script>', encoding="utf-8")
            done.clear()
            try:
                dom = run_chrome(chrome, f"{base}/{name}")
            finally:
                (root / name).unlink(missing_ok=True)
            m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
            if not m:
                raise RuntimeError(f"Chrome produced no measurement for {chunk[:2]}... after retries")
            results += json.loads(_html.unescape(m.group(1)))
    finally:
        server.shutdown()
        server.server_close()
    return results


def problems_of(results: list[dict]) -> list[str]:
    out: list[str] = []
    for r in results:
        if "error" in r:
            out.append(f"[layout] the measuring script failed: {r['error']}")
            continue
        where = f"{r['url']} @{r['w']}px"
        if r.get("failed"):
            out.append(f"[layout] {where}: {r['failed']}")
        if r["overflow"] > 1:
            out.append(f"[overflow] {where}: {r['overflow']}px wider than the screen; sticking out: {', '.join(r['offenders']) or 'unknown'}")
        if r["squeezed"]:
            out.append(f"[squeezed] {where}: text squeezed into a narrow column: {'; '.join(r['squeezed'])}")
        if r["nav"]:
            out.append(f"[nav] {where}: header/nav links squeezed or stretched: {'; '.join(r['nav'])}")
        if r["images"]:
            out.append(f"[images] {where}: images that did not load: {', '.join(r['images'])}")
    return out


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--base", default="", help="(unused; kept so the call looks like sitecheck's)")
    ap.add_argument("--cap", type=int, default=60, help="the most pages to measure")
    ap.add_argument("--widths", default=",".join(map(str, WIDTHS)))
    ap.add_argument("--max", type=int, default=40)
    a = ap.parse_args(argv)
    root = Path(a.root)
    pages = pick_pages(root, a.cap)
    if not pages:
        print("LAYOUT CHECK FAILED: no pages to measure (is there a sitemap?)")
        return 1
    widths = tuple(int(x) for x in a.widths.split(","))
    try:
        results = measure(root, pages, widths)
    except RuntimeError as e:
        print("LAYOUT CHECK FAILED: " + str(e))
        return 1
    problems = problems_of(results)
    if problems:
        print(f"LAYOUT CHECK FAILED: {len(problems)} problem(s) in {len(pages)} pages x {len(widths)} widths")
        for p in problems[: a.max]:
            print("  - " + p)
        return 1
    print(f"layout ok: {len(pages)} pages x {len(widths)} widths ({len(results)} measurements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
