"""Search demand for the illustration site: what people type into Google / Bing, and which of it the site does not answer yet.

    python -m sites.minna.demand run [--out DIR] [--months 3] [--no-bing]     fetch suggestions, write demand/<date>.json and demand/QUEUE.md
    python -m sites.minna.demand show [--out DIR]                              print the newest queue

How it works: seed phrases (always-on topics plus the next months' events) are widened with the usual modifiers ("無料", "かわいい", ...) and sent to the
public autocomplete endpoints.  Every suggestion is split into topic words (the filler "イラスト 無料 かわいい ..." is dropped) and counted against the
library (series titles, item titles and tags) and the guides.  A suggestion with no matching illustration is a *gap*, with few (< THIN) a *thin* spot.
The queue is what the daily factory plans from and what the weekly growth routine turns into guides.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBRARY = HERE / "library"
GUIDES = HERE / "content" / "guides.json"
DEFAULT_OUT = HERE.parents[1].parent / "sokuhou-sites" / "docs" / "minna_growth" / "demand"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
THIN = 6          # fewer matching illustrations than this = thin
DELAY = 0.35      # seconds between requests: the endpoints are public, be polite

# Words that describe the kind of thing wanted, not the subject.  A query is reduced to its subject words before it is matched.
FILLER = {
    "イラスト", "いらすと", "無料", "むりょう", "フリー", "ふりー", "素材", "そざい", "かわいい", "可愛い", "手書き", "白黒", "モノクロ", "商用", "商用利用", "透過", "透明", "背景",
    "画像", "ダウンロード", "ダウンロードする", "png", "jpg", "pdf", "ai", "おしゃれ", "シンプル", "簡単", "かんたん", "おすすめ", "まとめ", "サイト", "ない", "なし", "不要", "登録",
    "使える", "使える", "ちびキャラ", "ゆるい", "ゆるかわ", "線画", "テンプレート", "テンプレ", "枠", "ワード", "word", "エクセル", "excel", "パワポ", "パワーポイント", "canva", "キャンバ",
    "2024", "2025", "2026", "2027", "2028", "令和", "とは", "の", "を", "に", "で", "と", "は", "が", "も", "から", "まで", "用", "向け", "風", "する", "できる", "やり方", "方法", "作り方", "つくりかた",
    "印刷", "プリント", "a4", "はがき", "ハガキ", "葉書", "ダウンロード", "保存", "コピー", "貼り付け", "でかい", "大きい", "高画質", "高解像度", "ai生成", "aiイラスト",
}
MODIFIERS = ["", " 無料", " かわいい", " 手書き", " 白黒", " 商用"]

ALWAYS = [
    "犬", "猫", "うさぎ", "くま", "パンダ", "ペンギン", "小鳥", "きつね", "たぬき", "ひつじ", "さかな", "くじら", "カエル", "ハムスター", "恐竜", "昆虫", "ドラゴン", "妖怪",
    "果物", "野菜", "お弁当", "おにぎり", "ラーメン", "スイーツ", "パン", "お茶", "コーヒー",
    "給食", "授業", "先生", "生徒", "部活", "遠足", "卒業", "入学",
    "会議", "営業", "テレワーク", "新入社員", "接客", "サラリーマン", "医者", "看護師", "保育士",
    "おばあさん", "おじいさん", "赤ちゃん", "家族", "男の子", "女の子", "お母さん",
    "花", "木", "雲", "海", "山", "星", "月", "雨", "雪",
    "掃除", "料理", "洗濯", "ゴミ出し", "お風呂", "睡眠", "病院", "防災", "節約",
    "矢印", "チェックマーク", "ハート", "吹き出し", "フレーム", "罫線", "見出し", "リボン", "ライン", "背景", "アイコン", "ピクトグラム",
    "ぬりえ", "カレンダー", "賞状", "名札", "時間割", "ポップ", "メニュー", "チラシ", "ポスター",
]
SEASON = {
    1: ["お正月", "初詣", "成人式", "寒中見舞い", "節分", "雪だるま", "受験", "新年会", "七草", "鏡餅"],
    2: ["節分", "バレンタイン", "梅", "受験", "卒業", "ひな祭り", "恵方巻", "花粉症"],
    3: ["ひな祭り", "卒業式", "桜", "入学準備", "春", "ホワイトデー", "お彼岸", "花粉症", "チューリップ"],
    4: ["入学式", "新年度", "お花見", "春", "新入社員", "ゴールデンウィーク", "桜", "遠足"],
    5: ["こどもの日", "母の日", "こいのぼり", "新緑", "五月人形", "運動会", "梅雨前"],
    6: ["梅雨", "父の日", "あじさい", "衣替え", "かたつむり", "夏至", "ほたる"],
    7: ["七夕", "夏休み", "海水浴", "花火", "夏祭り", "暑中見舞い", "かき氷", "ひまわり", "プール"],
    8: ["夏", "お盆", "花火", "残暑見舞い", "防災", "かき氷", "夏休み", "スイカ"],
    9: ["秋", "敬老の日", "お月見", "お彼岸", "運動会", "防災", "コスモス", "読書", "さんま"],
    10: ["ハロウィン", "紅葉", "運動会", "七五三", "読書の秋", "お月見", "年賀状", "喪中はがき", "秋の味覚", "きのこ"],
    11: ["年賀状", "七五三", "勤労感謝の日", "クリスマス", "紅葉", "大掃除", "お歳暮", "冬支度", "鍋", "いちょう"],
    12: ["クリスマス", "年賀状", "大晦日", "冬至", "餅つき", "お正月", "干支", "冬休み", "忘年会", "大掃除", "ゆず湯"],
}


# Spelling variants that mean the same drawing; applied to queries and to the library alike, so only consistency matters.
SYNONYMS = {
    "塗り絵": "ぬりえ", "塗絵": "ぬりえ", "ぬり絵": "ぬりえ", "ハロウィーン": "ハロウィン", "お化け": "おばけ", "オバケ": "おばけ", "猫": "ねこ", "ネコ": "ねこ", "犬": "いぬ", "兎": "うさぎ",
    "羊": "ひつじ", "熊": "くま", "狐": "きつね", "狸": "たぬき", "蛙": "かえる", "魚": "さかな", "桜": "さくら", "南瓜": "かぼちゃ", "雪だるま": "ゆきだるま", "サンタクロース": "サンタ",
    "オンライン": "online", "ウェブ": "web", "リモート": "テレワーク", "在宅勤務": "テレワーク", "お月見": "おつきみ", "月見": "おつきみ",
    "果物": "フルーツ", "くだもの": "フルーツ", "餅つき": "もちつき", "柚子": "ゆず", "おじいさん": "おじいちゃん", "お爺さん": "おじいちゃん", "おばあさん": "おばあちゃん",
    "お婆さん": "おばあちゃん", "小鳥": "ことり", "大晦日": "大みそか", "おおみそか": "大みそか", "銀杏": "いちょう", "お弁当": "べんとう", "おべんとう": "べんとう", "弁当": "べんとう",
}
SYNONYM_FILE = HERE / "content" / "demand_synonyms.json"   # grown by the weekly routine whenever a "gap" turns out to be spelled differently in the library
# Topics the site answers with a page of its own (printable PDFs, calendars, card maker), not only with illustrations: never reported as a gap.
PAGE_TOPICS = ["賞状", "名札", "時間割", "カレンダー", "ぬりえ", "塗り絵", "年賀状", "はがき", "寒中見舞い", "カード", "おたより", "お便り"]


def _load_synonyms() -> None:
    if SYNONYM_FILE.exists():
        extra = json.loads(SYNONYM_FILE.read_text(encoding="utf-8"))
        SYNONYMS.update({k: v for k, v in extra.items() if isinstance(k, str) and isinstance(v, str) and k and not k.startswith("_")})


_load_synonyms()


def norm(text: str) -> str:
    """NFKC, lower case, spelling variants unified, katakana -> hiragana, no spaces: the form used to compare a query word with the library."""
    t = unicodedata.normalize("NFKC", text).lower()
    for a, b in SYNONYMS.items():
        t = t.replace(a, b)
    t = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in t)
    return re.sub(r"\s+", "", t)


def display_topic(query: str) -> str:
    """The query without its filler words, in the spelling people typed: how a topic is shown in the queue."""
    words = [w for w in unicodedata.normalize("NFKC", query).split() if norm(w) not in _FILLER_N and not re.fullmatch(r"[0-9]+", w)]
    return " ".join(words) or query


_FILLER_N = {norm(f) for f in FILLER}


def topic_words(query: str) -> list[str]:
    """The subject words of a query: split on spaces, drop the filler words and bare numbers."""
    out = []
    for w in unicodedata.normalize("NFKC", query).split():
        n = norm(w)
        if not n or n in _FILLER_N or re.fullmatch(r"[0-9]+", n):
            continue
        # glued filler ("ねこイラスト", "フリー素材"): strip filler words (two characters or more, not Latin) from both ends until nothing changes
        changed = True
        while n and changed:
            changed = False
            for f in sorted(_FILLER_N, key=len, reverse=True):
                if len(f) < 2 or f.isascii():
                    continue
                if n.endswith(f):
                    n, changed = n[: -len(f)], True
                    break
                if n.startswith(f):
                    n, changed = n[len(f):], True
                    break
        if n:
            out.append(n)
    seen, uniq = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def library_blobs(library: Path = LIBRARY, guides: Path = GUIDES) -> tuple[list[str], list[str]]:
    """(one normalised text per illustration: series title + item title + tags, one per guide)."""
    items = []
    for f in sorted(library.glob("*/series.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        head = " ".join([s.get("title", ""), s.get("subject") or "", " ".join(s.get("tags", [])[:4])])
        for it in s.get("items", []):
            items.append(norm(head + " " + it.get("title", "") + " " + " ".join(it.get("tags", []))))
    gl = []
    if guides.exists():
        data = json.loads(guides.read_text(encoding="utf-8"))
        gl = [norm(g.get("title", "") + g.get("description", "")) for g in (data if isinstance(data, list) else data.get("guides", []))]
    return items, gl


def covered(words: list[str], items: list[str]) -> int:
    """How many illustrations match every topic word."""
    if not words:
        return len(items)
    return sum(1 for b in items if all(w in b for w in words))


def suggest_url(engine: str, q: str) -> str:
    qq = urllib.parse.quote(q)
    if engine == "google":
        return f"https://suggestqueries.google.com/complete/search?client=firefox&hl=ja&oe=utf-8&q={qq}"
    return f"https://api.bing.com/osjson.aspx?query={qq}&mkt=ja-JP"


def fetch_suggest(engine: str, q: str) -> list[str]:
    try:
        req = urllib.request.Request(suggest_url(engine, q), headers=UA)
        raw = urllib.request.urlopen(req, timeout=15).read()
        for enc in ("utf-8", "cp932"):
            try:
                data = json.loads(raw.decode(enc))
                break
            except (UnicodeDecodeError, ValueError):
                data = None
        if not data or len(data) < 2:
            return []
        return [s for s in data[1] if isinstance(s, str)]
    except Exception as e:  # network trouble must not stop a weekly run: the seed is just skipped (and counted)
        print(f"  ! {engine} {q!r}: {e}", file=sys.stderr)
        return None


def seeds_for(today: date, months: int = 3) -> list[tuple[str, str]]:
    """[(seed phrase, group)]: the always-on topics and the events of this month and the next `months - 1`."""
    out = [(f"{w} イラスト", "always") for w in ALWAYS]
    for k in range(months):
        m = (today.month - 1 + k) % 12 + 1
        out += [(f"{w} イラスト", f"season-{m}") for w in SEASON[m]]
    return out


def collect(seeds, fetch=fetch_suggest, engines=("google", "bing"), modifiers=MODIFIERS, delay=DELAY) -> tuple[dict, int]:
    """{query: {"seeds": set, "engines": set, "rank": best rank}}, number of failed requests."""
    found: dict[str, dict] = {}
    failed = 0
    for seed, group in seeds:
        for engine in engines:
            for mod in (modifiers if engine == "google" else [""]):
                got = fetch(engine, seed + mod)
                if got is None:
                    failed += 1
                    continue
                for rank, s in enumerate(got):
                    q = unicodedata.normalize("NFKC", s).strip()
                    if not q:
                        continue
                    e = found.setdefault(q, {"seeds": set(), "engines": set(), "rank": rank, "groups": set()})
                    e["seeds"].add(seed)
                    e["engines"].add(engine)
                    e["groups"].add(group)
                    e["rank"] = min(e["rank"], rank)
                if delay:
                    time.sleep(delay)
    return found, failed


def analyse(found: dict, items: list[str], guides: list[str]) -> list[dict]:
    """One row per topic (the subject words of the queries): demand evidence, how many illustrations match, an example query."""
    topics: dict[str, dict] = {}
    page_words = {norm(p) for p in PAGE_TOPICS}
    for q, e in found.items():
        words = topic_words(q)
        if not words or len(words) > 3 or any(len(w) < 2 for w in words):
            continue
        key = " ".join(words)
        t = topics.setdefault(key, {"topic": key, "words": words, "queries": [], "seeds": set(), "engines": set(), "best_rank": 99, "groups": set()})
        t["queries"].append(q)
        t["seeds"] |= e["seeds"]
        t["engines"] |= e["engines"]
        t["groups"] |= e["groups"]
        t["best_rank"] = min(t["best_rank"], e["rank"])
    rows = []
    for t in topics.values():
        n = covered(t["words"], items)
        g = sum(1 for b in guides if all(w in b for w in t["words"]))
        score = len(t["queries"]) + 2 * len(t["seeds"]) + (3 if len(t["engines"]) > 1 else 0) + max(0, 5 - t["best_rank"])
        shown = display_topic(sorted(t["queries"], key=len)[0])
        rows.append({
            "topic": shown, "key": t["topic"], "score": score, "queries": sorted(t["queries"], key=len)[:4], "n_queries": len(t["queries"]), "n_seeds": len(t["seeds"]),
            "engines": sorted(t["engines"]), "groups": sorted(t["groups"]), "illustrations": n, "guides": g,
            "status": "page" if all(w in page_words for w in t["words"]) else ("gap" if n == 0 else ("thin" if n < THIN else "ok")),
        })
    rows.sort(key=lambda r: (-r["score"], r["topic"]))
    return rows


def queue_markdown(rows: list[dict], today: date, failed: int, limit: int = 40) -> str:
    gaps = [r for r in rows if r["status"] == "gap"][:limit]
    thin = [r for r in rows if r["status"] == "thin"][: limit // 2]
    seasonal = [r for r in rows if r["status"] in ("gap", "thin") and any(g.startswith("season-") for g in r["groups"])][: limit // 2]
    out = [f"# 需要キュー {today.isoformat()}", "",
           f"検索サジェストから集めた話題 {len(rows)} 件。うち、サイトに該当する絵が無い=gap {sum(1 for r in rows if r['status'] == 'gap')}、少ない(<{THIN}点)=thin {sum(1 for r in rows if r['status'] == 'thin')}。"
           f"取得に失敗したリクエスト: {failed}。", "",
           "点数(score)は、サジェストに出た回数・出てきた種の数・Google と Bing の両方に出たか・順位から作った目安で、検索数そのものではありません。", ""]

    def table(title, rs):
        out.append(f"## {title}")
        out.append("")
        out.append("| 話題 | score | 絵 | 読みもの | 例 |")
        out.append("|---|---|---|---|---|")
        for r in rs:
            out.append(f"| {r['topic']} | {r['score']} | {r['illustrations']} | {r['guides']} | {' / '.join(r['queries'][:2])} |")
        out.append("")

    table("今の季節で足りない話題(先に描く・書く)", seasonal)
    table("サイトに絵が無い話題(gap)", gaps)
    table("少ない話題(thin: 追加のシリーズ候補)", thin)
    return "\n".join(out)


def _dump(found: dict) -> dict:
    return {q: {"seeds": sorted(e["seeds"]), "engines": sorted(e["engines"]), "rank": e["rank"], "groups": sorted(e["groups"])} for q, e in found.items()}


def _load(raw: dict) -> dict:
    return {q: {"seeds": set(e["seeds"]), "engines": set(e["engines"]), "rank": e["rank"], "groups": set(e["groups"])} for q, e in raw.items()}


def run(out: Path, today: date | None = None, months: int = 3, engines=("google", "bing"), fetch=fetch_suggest, delay=DELAY, reuse: bool = False) -> list[dict]:
    """Fetch (or, with reuse, take the newest saved suggestions) and write demand/<date>.json + QUEUE.md.  `reuse` re-judges the same suggestions after a synonym fix."""
    today = today or date.today()
    items, guides = library_blobs()
    if reuse:
        saved = sorted(p for p in out.glob("20*.json"))
        if not saved:
            raise SystemExit("no saved suggestions to reuse")
        prev = json.loads(saved[-1].read_text(encoding="utf-8"))
        found, failed = _load(prev["found"]), prev.get("failed", 0)
    else:
        found, failed = collect(seeds_for(today, months), fetch=fetch, engines=engines, delay=delay)
    rows = analyse(found, items, guides)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{today.isoformat()}.json").write_text(json.dumps({"date": today.isoformat(), "failed": failed, "found": _dump(found), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "QUEUE.md").write_text(queue_markdown(rows, today, failed), encoding="utf-8")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "show"])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--no-bing", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="judge the newest saved suggestions again instead of fetching (after adding a synonym)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if a.cmd == "show":
        print((out / "QUEUE.md").read_text(encoding="utf-8"))
        return 0
    rows = run(out, months=a.months, engines=("google",) if a.no_bing else ("google", "bing"), reuse=a.reuse)
    print(f"{len(rows)} topics; gap {sum(r['status'] == 'gap' for r in rows)}, thin {sum(r['status'] == 'thin' for r in rows)}, page {sum(r['status'] == 'page' for r in rows)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
