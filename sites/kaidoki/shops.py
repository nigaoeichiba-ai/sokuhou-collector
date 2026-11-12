"""SALEカレンダー: 「いま割引が多いYahoo!ショッピングの店」の欄(/yahoo/)。

データの流れ(オーナー厳命 2026-10-17: モールの API から取ったデータは、リポジトリ・ログ・成果物・キャッシュに入れない):
  毎日の取得(.github/workflows/kaidoki-sale-daily.yml → sites/kaidoki/tools/yahoo_shops.py)
    → サーバーの非公開フォルダ ~/kaidoki-private/yahoo_shops.json (SSH。Web から見えない所)
    → api/yahoo-shops.php が、そのファイルから「いまの欄」を出す(取得日が古ければ空)
    → assets/yahoo-shops.js が、欄に流し込む(データが無い・古い・失敗のときは、欄ごと隠れたまま)
  ビルドの成果物に入るのは、欄の見出し・説明(固定の文章)と、PHP・JS の部品だけ。店名・件数・店のURLは1つも入らない。

出すもの: 店ごとに「割引中 〇件・〇〜〇%引き・最長〇月〇日まで・店の評価」。出さないもの: 商品名・商品の価格・商品画像・順位。並びは、店名の順(おすすめの選び方をしない)。
店へのリンクは、バリューコマースの MyLink(redesign/affiliate.py の形のまま)、PR 表示つき、rel="nofollow sponsored noopener" target="_blank"。
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
DB_NAME = "yahoo_shops.json"
PRIVATE = "kaidoki-private"
MAX_AGE_DAYS = 2                 # 取得日がこれより古ければ、欄を出さない(PHP も JS も、鮮度点検も同じ値を使う)
MIN_SHOP_REVIEWS, MIN_SHOP_RATE = 100, 4.0
MIN_SHOPS_PER_GENRE = 3          # 店が少なすぎるジャンルは、欄に出さない
MAX_SHOPS_PER_GENRE = 24
SLUG = re.compile(r"^[a-z0-9_-]{1,40}$")
SHOP_ID = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")
STORE_URL = "https://store.shopping.yahoo.co.jp/{}/"

# ジャンルの並び・呼び名は、SALEカレンダーの商品ジャンル(/kaden/ ほか)に合わせた当サイトの語。検索語は、割引中の総数が少ないジャンルほど広げる(取得の用)。
GENRES = [
    ("phone", "スマホ", ["スマートフォン", "iPhone"]),
    ("pc", "パソコン・タブレット", ["ノートパソコン", "タブレット"]),
    ("tv", "テレビ", ["液晶テレビ", "テレビ", "4Kテレビ", "有機EL テレビ"]),
    ("kaden", "生活家電", ["掃除機", "洗濯機", "ドライヤー"]),
    ("kitchen", "キッチン家電", ["炊飯器", "電子レンジ", "電気ケトル", "ホットプレート", "コーヒーメーカー"]),
    ("beauty", "美容", ["化粧水", "美容液", "シャンプー"]),
    ("game", "ゲーム", ["ゲームソフト", "Nintendo Switch", "PlayStation", "ゲーム機"]),
    ("camera", "カメラ", ["ミラーレスカメラ", "デジタルカメラ", "一眼レフ", "カメラ レンズ"]),
    ("daily", "日用品", ["洗剤", "トイレットペーパー"]),
    ("food", "食品", ["米 5kg", "ミネラルウォーター", "コーヒー", "お菓子"]),
]
LABELS = {slug: label for slug, label, _ in GENRES}

# 提携プログラムが MyLink を禁じている店(sites/yorokobu/compare.py の Y_BARRED と同じ)
BARRED = ("デルコンピュータ", "n-garden", "喜信堂", "モロゾフ", "園芸ネット", "ディノス", "オットージャパン", "セシール")
# Yahoo! デベロッパーネットワークのクレジット(規定の形のまま)
CREDIT = ('<!-- Begin Yahoo! JAPAN Web Services Attribution Snippet -->\n'
          '<span style="margin:15px 15px 15px 15px"><a href="https://developer.yahoo.co.jp/sitemap/">Web Services by Yahoo! JAPAN</a></span>\n'
          '<!-- End Yahoo! JAPAN Web Services Attribution Snippet -->')


def _num(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def to_seconds(ts) -> int:
    t = int(_num(ts))
    return t // 1000 if t > 10**11 else t


# ------------------------------------------------------------------ 集計(取得側。非公開フォルダに置く形を作る)
def shop_item(h: dict, now: int) -> dict | None:
    """1商品から、店の集計に使う項目だけ(名前・URL・画像・価格そのものは持たない)。割引中でなければ None。"""
    pl, seller = h.get("priceLabel") or {}, h.get("seller") or {}
    default, disc = int(_num(pl.get("defaultPrice"))), int(_num(pl.get("discountedPrice")))
    end = to_seconds(pl.get("periodEnd"))
    sid, name = str(seller.get("sellerId") or ""), str(seller.get("name") or "").strip()
    srev = seller.get("review") or {}
    if not (0 < disc < default) or end < now or not h.get("code") or not SHOP_ID.match(sid) or not name:
        return None
    if any(b in name or b == sid for b in BARRED):
        return None
    count, rate = int(_num(srev.get("count"))), _num(srev.get("rate"))
    if count < MIN_SHOP_REVIEWS or rate < MIN_SHOP_RATE:
        return None
    return {"code": str(h["code"]), "id": sid, "name": name, "pct": round(100 * (default - disc) / default), "end": end, "rc": count, "rr": round(rate, 2)}


def aggregate(hits_by_genre: dict[str, list[dict]], now: int, today: str) -> dict:
    """{"updated": "2026-11-12", "genres": {slug: [{"id","n","c","lo","hi","e","r","rc"}, ...]}}  店名の順。店が少ないジャンルは入れない。"""
    genres: dict[str, list[dict]] = {}
    for slug, _, _ in GENRES:
        shops: dict[str, dict] = {}
        seen: set[str] = set()
        for h in hits_by_genre.get(slug, []):
            it = shop_item(h, now)
            if it is None or it["code"] in seen:
                continue
            seen.add(it["code"])
            s = shops.setdefault(it["id"], {"id": it["id"], "n": it["name"], "c": 0, "lo": 100, "hi": 0, "end": 0, "r": it["rr"], "rc": it["rc"]})
            s["c"] += 1
            s["lo"], s["hi"], s["end"] = min(s["lo"], it["pct"]), max(s["hi"], it["pct"]), max(s["end"], it["end"])
        if len(shops) < MIN_SHOPS_PER_GENRE:
            continue
        top = sorted(shops.values(), key=lambda s: (-s["c"], s["n"]))[:MAX_SHOPS_PER_GENRE]     # 件数の多い店を選び、見せる順は店名順にする
        rows = []
        for s in sorted(top, key=lambda s: s["n"]):
            rows.append({"id": s["id"], "n": s["n"], "c": s["c"], "lo": s["lo"], "hi": s["hi"],
                         "e": datetime.fromtimestamp(s["end"], JST).strftime("%Y-%m-%d"), "r": s["r"], "rc": s["rc"]})
        genres[slug] = rows
    return {"updated": today, "genres": genres}


# ------------------------------------------------------------------ 答え(api/yahoo-shops.php と同じ作りの Python 版。テストが使う。PHP はこれと同じことをする)
def age_days(updated: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(updated)).days
    except (TypeError, ValueError):
        return None


def store_href(shop_id: str) -> str:
    """バリューコマースの MyLink(redesign/affiliate.py の vc_href と同じ形。提供された形のまま)。"""
    from sites.kaidoki.redesign import affiliate
    return affiliate.vc_href(affiliate.VC_PID["yahoo"], STORE_URL.format(shop_id))


def answer(db: dict | None, today: date) -> dict:
    """欄に出す中身。データが無い・古い・読めないときは genres が空(欄は出ない)。"""
    empty = {"u": "", "genres": []}
    if not isinstance(db, dict):
        return empty
    age = age_days(db.get("updated", ""), today)
    if age is None or age < 0 or age > MAX_AGE_DAYS:
        return empty
    out = []
    for slug, label, _ in GENRES:
        rows = [r for r in (db.get("genres") or {}).get(slug, []) if SHOP_ID.match(str(r.get("id", ""))) and str(r.get("e", "")) >= today.isoformat()]      # 終わった店は出さない
        if len(rows) < MIN_SHOPS_PER_GENRE:
            continue
        out.append({"s": slug, "shops": [{"n": r["n"], "c": int(r["c"]), "lo": int(r["lo"]), "hi": int(r["hi"]), "e": r["e"], "r": r["r"], "rc": int(r["rc"]), "h": store_href(r["id"])}
                                         for r in rows[:MAX_SHOPS_PER_GENRE]]})
    return {"u": db["updated"], "genres": out} if out else empty


# ------------------------------------------------------------------ ページの部品(ビルドに入る。固定の文章と、PHP・JS)
HEADING = "いま割引が多いYahoo!ショッピングの店"
INTRO = "Yahoo!ショッピングで割引中の商品が見つかった店を、ジャンルごとに店名の順で並べています。おすすめの店を選んだ並びではありません。"
NOTE = "件数・割引率・終了日は、検索で確認できた割引中の商品の範囲です。割引は途中で変わることがあるので、買う前に店のページでもう一度見ておきましょう。"
PR_TEXT = "Yahoo!ショッピングの店へのリンクを含みます(バリューコマース)。"

CSS = """<style>
.shops-box[hidden]{display:none}
.shops-box{margin:24px 0}
.shops-box h3{font-size:16px;margin:22px 0 6px}
.shops-list{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
.shops-list li{margin:0;display:flex;flex-wrap:wrap;gap:2px 14px;align-items:baseline;padding:9px 2px;border-bottom:1px solid var(--line)}
.shops-list .shop-name{font-weight:700;min-width:10em;overflow-wrap:anywhere}
.shops-list .shop-facts{color:var(--muted);font-size:13px;overflow-wrap:anywhere}
.shops-date,.shops-note,.shops-pr{font-size:12.5px;color:var(--muted)}
.shops-pr{margin:10px 0 0}
.shops-pr .pr-chip{margin-right:6px}
</style>"""


def php() -> str:
    from sites.kaidoki.redesign import affiliate
    t = (HERE / "yahoo_shops.php.tpl").read_text(encoding="utf-8")
    return (t.replace("__SITE_URL__", json.loads((HERE / "config.json").read_text(encoding="utf-8"))["site_url"].rstrip("/")).replace("__PRIVATE__", PRIVATE)
            .replace("__DB__", DB_NAME).replace("__MAX_AGE__", str(MAX_AGE_DAYS)).replace("__MAX_SHOPS__", str(MAX_SHOPS_PER_GENRE)).replace("__MIN_SHOPS__", str(MIN_SHOPS_PER_GENRE))
            .replace("__VC_SID__", affiliate.VC_SID).replace("__VC_PID__", affiliate.VC_PID["yahoo"]).replace("__GENRES__", json.dumps([s for s, _, _ in GENRES])))


def js() -> str:
    from sites.kaidoki.redesign import affiliate
    t = (HERE / "yahoo_shops.js").read_text(encoding="utf-8")
    return (t.replace("__LABELS__", json.dumps(LABELS, ensure_ascii=False)).replace("__MAX_AGE__", str(MAX_AGE_DAYS))
            .replace("__VC_SID__", affiliate.VC_SID).replace("__VC_PID__", affiliate.VC_PID["yahoo"]))


def section_html(version: str) -> str:
    """/yahoo/ に入れる欄。固定の文章だけ(店のデータは1つも入らない)。欄ごと hidden で、JS がデータを持ってきたときだけ出る。"""
    return (f'<section class="content-block shops-box" id="shops" hidden>\n{CSS}\n<h2>{escape(HEADING)}</h2>\n<p>{escape(INTRO)}</p>\n<div id="shops-body"></div>\n'
            f'<p class="shops-date" id="shops-date"></p>\n<p class="shops-note">{escape(NOTE)}</p>\n'
            f'<p class="shops-pr"><span class="pr-chip">PR</span>{escape(PR_TEXT)}</p>\n{CREDIT}\n</section>\n'
            f'<script src="/assets/yahoo-shops.js?v={version}" defer></script>\n')


def version() -> str:
    import hashlib
    return hashlib.sha1((HERE / "yahoo_shops.js").read_bytes()).hexdigest()[:8]


FINAL = re.compile(r"(?:<section[^>]*>)?<h2>最終確認は公式で</h2>")      # 新しいデザインでは、見出しごとに <section> に包まれる(その前に差し込む)


def add_shops(pages: dict) -> dict:
    """/yahoo/ に欄を差し込み、api/yahoo-shops.php と assets/yahoo-shops.js を足す(hooks.post から)。"""
    html = pages.get("yahoo/index.html")
    assert html, "kaidoki shops: no /yahoo/ page"
    html, n = FINAL.subn(lambda m: section_html(version()) + m.group(0), html, count=1)
    assert n == 1, "kaidoki shops: the /yahoo/ page has no 最終確認は公式で section"
    pages["yahoo/index.html"] = html
    pages["api/yahoo-shops.php"] = php()
    pages["assets/yahoo-shops.js"] = js()
    return pages
