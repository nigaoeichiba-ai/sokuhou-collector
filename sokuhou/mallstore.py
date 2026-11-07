"""The shared, site-independent store of the Rakuten products that a site's pages show in "shelves" (棚).

The rule (owner's decision 2026-11-07; Rakuten Web Service terms Article 10 (1) (9): no keeping of the shops' data where many people can read it):
the repository, the Actions logs, the artifacts and the cache never hold a product name, price, picture or link of a shop.  They hold only the *definition* of a shelf
(`sites/<name>/shelves.json`: an id, the site's own label, a search word, the bars a product has to pass).  The products themselves live in the server's private folder
`~/<name>-private/` (outside public_html) and a small PHP file (`api/shelf.php`, made here) gives out a few of them at a time to the pages of the same site.

    python -m sokuhou.mallstore plan                      # the sites that have shelves and how many calls a refresh makes (no network, no keys)
    python -m sokuhou.mallstore refresh [--sites a,b]     # every site in turn (one application ID allows one request a second): fetch -> select -> push (needs RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY and the SSH secrets)

`shelves.json`:
    {"shelves": [{"id": "light", "label": "防災用の懐中電灯", "keyword": "防災 懐中電灯", "count": 3, "min_price": 500, "max_price": 8000, "min_reviews": 20, "min_rating": 4.0, "exclude": ["福袋"]}]}
The label is the site's own word for the product kind: it is what the card says (a shop's own title is never shown or changed) and the alt text of the picture.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
SLUG = re.compile(r"^[a-z0-9_-]{1,40}$")
DB_NAME = "shelves_db.json"
PORT = os.environ.get("SSH_PORT", "10022")
DAILY_LIMIT = 600
WAIT = (0, 10, 30)
KEYS = ("id", "label", "keyword", "count", "min_price", "max_price", "min_reviews", "min_rating", "exclude", "sort")


class ShelfError(Exception):
    pass


# ---------------------------------------------------------------- the definition of a shelf (public, no shop data)
def load_shelves(site_dir: Path) -> list[dict]:
    p = Path(site_dir) / "shelves.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out, seen = [], set()
    for s in data.get("shelves", []):
        bad = [k for k in s if k not in KEYS]
        if bad:
            raise ShelfError(f"{p}: unknown key {bad} (a shelf holds a definition only, never a product)")
        if not SLUG.match(str(s.get("id", ""))):
            raise ShelfError(f"{p}: the id of a shelf is a-z, 0-9, - and _ (up to 40): {s.get('id')!r}")
        if s["id"] in seen:
            raise ShelfError(f"{p}: the shelf id {s['id']!r} is used twice")
        seen.add(s["id"])
        if not str(s.get("label", "")).strip() or not str(s.get("keyword", "")).strip():
            raise ShelfError(f"{p}: shelf {s['id']!r} needs a label and a keyword")
        out.append(s)
    return out


def sites_with_shelves(root: Path = ROOT) -> list[dict]:
    """The rows of data/sites.json whose site folder has a shelves.json."""
    reg = json.loads((root / "data" / "sites.json").read_text(encoding="utf-8"))
    return [r for r in reg["sites"] if (root / "sites" / r["name"] / "shelves.json").exists()]


# ---------------------------------------------------------------- choosing the products of a shelf
def select(items: list[dict], shelf: dict) -> list[dict]:
    """The first `count` products (in the order the API gave) that pass the shelf's bars; one product per shop."""
    want = int(shelf.get("count", 3))
    out, shops = [], set()
    for it in items:
        if not it.get("available", True):
            continue
        if it.get("reviews", 0) < int(shelf.get("min_reviews", 10)):
            continue
        if it.get("rating", 0) < float(shelf.get("min_rating", 4.0)):
            continue
        if any(w and w in it.get("name", "") for w in shelf.get("exclude", [])):
            continue
        shop = it.get("shop_code") or it.get("shop") or ""
        if shop and shop in shops:
            continue
        shops.add(shop)
        out.append(it)
        if len(out) >= want:
            break
    return out


def row(it: dict) -> dict:
    """What the private store keeps of a product: the picture and the product page exactly as the API gave them, the price, and the review figures for the choice."""
    return {"i": it["image"], "u": it["url"], "p": it["price"], "r": it.get("rating", 0), "n": it.get("reviews", 0)}


def fetch_shelf(client, shelf: dict) -> list[dict]:
    from sokuhou import rakuten
    params = {"keyword": shelf["keyword"], "hits": 30, "imageFlag": 1, "availability": 1, "sort": shelf.get("sort", "standard")}
    if shelf.get("min_price"):
        params["minPrice"] = int(shelf["min_price"])
    if shelf.get("max_price"):
        params["maxPrice"] = int(shelf["max_price"])
    if shelf.get("exclude"):
        params["NGKeyword"] = " ".join(shelf["exclude"])
    raw = client.search(**params)
    items = [x for x in (rakuten.normalize(r) for r in raw) if x]
    return select(items, shelf)


def build_db(shelves: list[dict], client, today: str, log=print) -> dict:
    """{"updated": "2026-11-08", "shelves": {id: [row, ...]}}.  A shelf that finds nothing is left out (the page then shows nothing; no empty frame)."""
    db: dict = {"updated": today, "shelves": {}}
    for s in shelves:
        try:
            got = fetch_shelf(client, s)
        except Exception as e:                                   # one shelf failing must not stop the others; the message carries no shop data
            from sokuhou import rakuten
            why = f" {str(e)[:200]}" if isinstance(e, rakuten.RakutenError) else ""      # an API error text (HTTP code and its reason) carries no product; any other error shows its type only
            log(f"mallstore: shelf {s['id']}: {type(e).__name__}{why}")
            continue
        if got:
            db["shelves"][s["id"]] = [row(x) for x in got]
        log(f"mallstore: shelf {s['id']}: {len(got)} product(s)")
    return db


SHOP_DATA = ("thumbnail.image.rakuten", "item.rakuten.co.jp", "image.rakuten.co.jp", "\"itemName\"", "\"shopName\"", "itemCode")


def shop_data_in(text: str) -> list[str]:
    """The marks of a shop's product data found in a public text (the tests run this over the repository's site folders and the built pages)."""
    return [m for m in SHOP_DATA if m in text]


# ---------------------------------------------------------------- the answer of api/shelf.php (the same logic in Python: the tests and the test server use it; the PHP does exactly this)
def affiliate_href(affiliate_id: str, product_url: str) -> str:
    """Rakuten's own redirect form (API specification: hgc/<ID>/?pc=<URL>): nothing is added behind the ID and the product page is the one the API gave."""
    return f"https://hb.afl.rakuten.co.jp/hgc/{affiliate_id}/?pc={urllib.parse.quote(product_url, safe='')}"


def answer(query: dict, db: dict, affiliate_id: str) -> tuple[int, object]:
    s = query.get("s", "")
    if not isinstance(s, str) or not SLUG.match(s):
        return 400, None
    rows = (db.get("shelves") or {}).get(s) or []
    if not rows:
        return 200, {"u": db.get("updated", ""), "items": []}
    return 200, {"u": db.get("updated", ""), "items": [{"i": r["i"], "h": affiliate_href(affiliate_id, r["u"]), "p": r["p"]} for r in rows[:6]]}


def shelf_php(cfg: dict) -> str:
    aff = cfg.get("rakuten_affiliate_id")
    if not aff or not re.fullmatch(r"[0-9a-f.]{10,60}", aff):
        raise ShelfError("config.json needs rakuten_affiliate_id (a site with shelves)")
    name = cfg["_site_name_key"]
    return ((HERE / "mallshelf.php.tpl").read_text(encoding="utf-8").replace("__SITE_URL__", cfg["site_url"].rstrip("/")).replace("__PRIVATE__", f"{name}-private")
            .replace("__AFF__", aff).replace("__DB__", DB_NAME).replace("__LIMIT__", str(DAILY_LIMIT)))


def shelf_js() -> str:
    return (HERE / "mallshelf.js").read_text(encoding="utf-8")


def shelf_html(shelf_id: str, label: str) -> str:
    """The place of a shelf in a page: empty and hidden until the page's script has the products (nothing shows when there are none)."""
    from html import escape
    return (f'<div class="shelf" data-shelf="{escape(shelf_id)}" data-label="{escape(label)}" hidden></div>'
            '<script src="/assets/shelf.js" defer></script>')


def build_files(site_dir: Path, cfg: dict) -> dict[str, str]:
    """The files a site with shelves ships: api/shelf.php and assets/shelf.js (none for a site without shelves.json)."""
    if not load_shelves(site_dir):
        return {}
    cfg = dict(cfg, _site_name_key=Path(site_dir).name)
    return {"api/shelf.php": shelf_php(cfg), "assets/shelf.js": shelf_js()}


# ---------------------------------------------------------------- the private store on the server (one SSH connection, a tar stream; like sites/yorokobu/privatedata.py, for any site)
def _conn():
    key, host, user = (os.environ.get(k, "") for k in ("XSERVER_SSH_KEY", "XSERVER_HOST", "XSERVER_USER"))
    return (key, host, user) if key and host and user else None


def push(site: str, db: dict, run=subprocess.run, sleep=time.sleep) -> bool:
    """The db into ~/<site>-private/shelves_db.json (the folder 700, the file 600, moved into place so a reader never sees half a file).  False when there is no connection."""
    c = _conn()
    if not c:
        print("mallstore: the server secrets are not set; nothing pushed")
        return False
    key, host, user = c
    data = json.dumps(db, ensure_ascii=False).encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tf:
        ti = tarfile.TarInfo(DB_NAME)
        ti.size = len(data)
        ti.mtime = int(time.time())
        tf.addfile(ti, io.BytesIO(data))
    d = f"~/{site}-private"
    remote = f"mkdir -p {d} && chmod 700 {d} && cd {d} && rm -rf .in && mkdir .in && cd .in && tar xf - && chmod 600 * && mv -f * .. && cd .. && rmdir .in"
    with tempfile.TemporaryDirectory() as td:
        kf, kh = Path(td) / "key", Path(td) / "known_hosts"
        kf.write_text(key.strip() + chr(10), encoding="utf-8")
        kf.chmod(0o600)
        ssh = ["ssh", "-i", str(kf), "-p", PORT, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={kh}", "-o", "ConnectTimeout=20", f"{user}@{host}"]
        for attempt in range(3):
            sleep(WAIT[attempt])
            p = run(ssh + [remote], input=buf.getvalue(), capture_output=True)
            if p.returncode == 0:
                print(f"mallstore: pushed {site} ({len(data) // 1024 or 1} KB, {len(db['shelves'])} shelves)")
                return True
            print(f"mallstore: the connection failed ({p.returncode}) attempt {attempt + 1}")
    return False


# ---------------------------------------------------------------- the daily run
def refresh(rows: list[dict], client_for, today: str, push_fn=push, root: Path = ROOT, log=print) -> int:
    """Every site in turn (one application ID allows one request a second).  Returns the number of sites that could not be pushed."""
    failed = 0
    for r in rows:
        shelves = load_shelves(root / "sites" / r["name"])
        client = client_for(r)
        db = build_db(shelves, client, today, log)
        if not db["shelves"]:
            log(f"mallstore: {r['name']}: no shelf has a product; nothing pushed (the old data stays)")
            failed += 1
            continue
        if not push_fn(r["name"], db):
            failed += 1
    return failed


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not a or a[0] not in ("plan", "refresh"):
        print(__doc__)
        return 2
    only = None
    if "--sites" in a:
        only = set(a[a.index("--sites") + 1].split(","))
    rows = [r for r in sites_with_shelves() if not only or r["name"] in only]
    if a[0] == "plan":
        for r in rows:
            print(f"{r['name']}: {len(load_shelves(ROOT / 'sites' / r['name']))} shelves (one search each)")
        print(f"{sum(len(load_shelves(ROOT / 'sites' / r['name'])) for r in rows)} calls, about {1.1 * sum(len(load_shelves(ROOT / 'sites' / r['name'])) for r in rows):.0f} seconds")
        return 0
    app, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app and key):
        print("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY are not set; nothing to do")
        return 0
    from sokuhou import rakuten

    def client_for(r):
        return rakuten.Client(app_id=app, access_key=key, referer="https://" + r["domain"] + "/")
    today = datetime.now(JST).strftime("%Y-%m-%d")
    return 1 if refresh(rows, client_for, today) else 0


if __name__ == "__main__":
    sys.exit(main())
