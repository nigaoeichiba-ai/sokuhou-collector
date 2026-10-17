"""The server side of the product lists that the pages ask for (気になるリスト, 共有リスト, おまかせガチャ, the product tips of the answer pages): api/items.php, made from items_receiver.php.tpl.

The shops' data is not a public file.  The build leaves it in three private files (build.PRIVATE; the deploy copies them to ~/yorokobu-private/ on the server) and this script gives out a few
products at a time for the purpose of the page that asks (Rakuten Web Service terms, Article 10 (1) (9): no storage where many people can read it).

`answer()` is the same logic in Python: the test server and the unit tests use it, so that what the PHP does is written down once in a form that runs here (there is no PHP in the test machine)."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAILY_LIMIT = 600           # requests per sender and day (a page of favourites asks once; a gacha spin once)
PRIVATE_FILES = {"items": "yorokobu_items_db.json", "gacha": "yorokobu_gacha_db.json", "rec": "yorokobu_rec_db.json"}
CODE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
SLUG = re.compile(r"^[a-z0-9_-]{1,40}$")


def items_php(cfg: dict) -> str:
    url = cfg["site_url"].rstrip("/")
    return (HERE / "items_receiver.php.tpl").read_text(encoding="utf-8").replace("__SITE_URL__", url).replace("__LIMIT__", str(DAILY_LIMIT))


def _int(v) -> int | None:
    return int(v) if isinstance(v, str) and re.fullmatch(r"\d{1,9}", v) else None


def answer(query: dict, db: dict, rnd: random.Random | None = None) -> tuple[int, object]:
    """(status, JSON) for a query string already parsed into {name: first value}; `db` = {"items": ..., "gacha": ..., "rec": ...} (the three private files, parsed)."""
    rnd = rnd or random
    if "c" in query:
        codes = [c for c in str(query["c"]).split(",") if CODE.match(c)][:24]
        items = db["items"]
        return 200, {c: items[c] for c in codes if c in items}
    if "r" in query and "t" in query:
        r, t = query["r"], query["t"]
        if not (SLUG.match(r) and SLUG.match(t)):
            return 400, None
        pool = ((db["gacha"].get("rec") or {}).get(r) or {}).get("tiers", {}).get(t) or []
        x = query.get("x") or ""
        cand = [row for row in pool if not (x and len(pool) > 1 and len(row) > 3 and row[3] == x)]
        return 200, {"row": rnd.choice(cand) if cand else None}
    if "g" in query:
        g = query["g"]
        if not SLUG.match(g):
            return 400, None
        lo, hi = _int(query.get("min")), _int(query.get("max"))
        gender = query.get("gender") if isinstance(query.get("gender"), str) and len(query["gender"]) <= 8 else ""
        try:
            n = max(1, min(12, int(query.get("n") or 4)))
        except ValueError:
            n = 4
        out = []
        for it in db["rec"].get(g) or []:
            if gender and it.get("g") and it["g"] != gender:
                continue
            if hi is not None and it["p"] > hi:
                continue
            if lo is not None and it["p"] < lo:
                continue
            out.append(it)
            if len(out) >= n:
                break
        return 200, {"items": out}
    return 400, None


def load_private(folder: Path) -> dict:
    return {k: json.loads((folder / name).read_text(encoding="utf-8")) for k, name in PRIVATE_FILES.items()}
