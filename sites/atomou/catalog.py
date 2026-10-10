"""The catalogue of dated topics: data/atomou/seed_*.json (dates read from official primary pages and checked) -> validated entries.

Only verified items with an https source URL, a valid date and a check date are accepted; everything else is counted in `rejects` and never reaches a page.
An entry's id comes from the source URL, the date and the kind (never from the title), so an edited title does not move its page.

Public fields only: the catalogue is published as assets/catalog.json and never carries personal data, user history or permission notes.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "data" / "atomou"
WEEKDAYS = "月火水木金土日"
STALE_DAYS = 90        # a date checked longer ago than this is shown as "確認日が古い"
KEEP_AFTER_DAYS = 30   # a finished event keeps its page (as "もう○日") this long; after that it is hidden and not indexed
LEAD = {"締切": 45, "試験日": 45, "施行": 45, "改定": 45}
LEAD_DEFAULT = 60       # days before the date that the page may be indexed
QUIET = ("grief", "disaster", "medical", "legal")

GROUPS = ["お金・税金・制度", "買い物・料金・セール", "スポーツ", "学校・資格", "天文・暦", "おでかけ・旅行", "通信・IT・アプリ", "趣味・ゲーム・アニメ", "エンタメ・音楽・賞", "暮らし・健康・グルメ"]
# Named after the big portals' own words (Yahoo!, Rakuten, ぴあ, じゃらん, 食べログ, 価格.com): the position of a genre fixes its colour and shape, so a rename keeps the position.
# 2026-10-10 (owner): "手続き" alone is vague, "サービス" and "空・季節" are not portal words, a race is not always a vehicle -> races went to スポーツ, vehicle shows to 趣味, trains to おでかけ・旅行.
G_MONEY, G_SHOP, G_SPORT, G_SCHOOL, G_SKY, G_TRIP, G_IT, G_HOBBY, G_SHOW, G_LIFE = GROUPS
GROUP_OF_CATEGORY = {
    "税": G_MONEY, "年金・保険": G_MONEY, "給付": G_MONEY, "制度": G_MONEY, "料金": G_MONEY, "ふるさと納税": G_MONEY,
    "セール": G_SHOP, "年賀状": G_SHOP, "ポイント": G_SHOP, "料金改定": G_SHOP,
    "サービス終了": G_IT,
    "大学入試": G_SCHOOL, "高校入試": G_SCHOOL, "資格": G_SCHOOL, "就活": G_SCHOOL, "奨学金": G_SCHOOL, "公務員": G_SCHOOL,
    "野球": G_SPORT, "サッカー": G_SPORT, "駅伝・マラソン": G_SPORT, "相撲": G_SPORT, "フィギュア": G_SPORT,
    "番組": G_SHOW, "音楽": G_SHOW, "ライブ": G_SHOW,
    "天文": G_SKY,
    "鉄道": G_TRIP, "キャンプ": G_TRIP, "乗り物": G_HOBBY,
    "即売会": G_HOBBY, "ゲーム・アニメ": G_HOBBY, "ホビー": G_HOBBY,
    "祭り": G_TRIP, "花火": G_TRIP, "イルミネーション": G_TRIP, "紅葉・花": G_TRIP, "スキー": G_TRIP,
    "初詣・初日の出": G_TRIP, "施設": G_TRIP,
    "健康": G_LIFE, "結婚": G_LIFE,
}
# a few topics sit under the catch-all category "その他" (or a neighbour's category) in the seeds; the topic decides the genre
GROUP_OF_SUBJECT = {
    "ラグビー": G_SPORT, "マラソン": G_SPORT, "女子マラソン": G_SPORT,
    "競馬": G_SPORT, "F1": G_SPORT, "カーレース": G_SPORT, "バイクレース": G_SPORT,
    "将棋": G_HOBBY, "コミックマーケット": G_HOBBY,
    "食べ歩き": G_LIFE, "スイーツ": G_LIFE, "日本酒": G_LIFE, "カニ": G_LIFE, "カニ漁": G_LIFE, "蟹騒動": G_LIFE,
    "ノーベル賞": G_SHOW, "アカデミー賞": G_SHOW, "映画祭": G_SHOW, "映画賞": G_SHOW,
    "宝くじ": G_SHOP, "年金(iDeCo)": G_MONEY, "住宅の補助金": G_MONEY, "共通テスト": G_SCHOOL, "ゆうちょ銀行": G_MONEY,
    "新幹線": G_TRIP, "燃油サーチャージ": G_TRIP,
    "ahamo": G_IT, "WiMAX": G_IT, "IIJmio": G_IT, "SoftBank光": G_IT, "ドコモ": G_IT, "NTT東日本": G_IT, "NTT西日本": G_IT,
}
GROUP_OF_FILE = {"seed_tax_law": G_MONEY, "seed_consumer": G_SHOP, "seed_exams": G_SCHOOL, "seed_sports_culture": G_SPORT,
                 "seed_otaku_astro": G_HOBBY, "seed_regional": G_TRIP}
def _load_taxonomy() -> dict:
    return json.loads((SEED_DIR / "taxonomy.json").read_text(encoding="utf-8"))


TAXONOMY = _load_taxonomy()   # 大(group) -> [中 {name, categories, subjects}]; 小 is the subject of a day
MID_OTHER = "ほか"
MID_OF_SUBJECT = {(g, s): m["name"] for g, mids in TAXONOMY.items() if g in GROUPS for m in mids for s in m["subjects"]}
MID_OF_CATEGORY = {(g, c): m["name"] for g, mids in TAXONOMY.items() if g in GROUPS for m in mids for c in m["categories"]}


def mid_for(group: str, subject: str, category: str) -> str:
    """The 中 category of a day: its subject (小) decides first, then its category; a day that fits none is "ほか" (the tests keep that at zero)."""
    return MID_OF_SUBJECT.get((group, subject)) or MID_OF_CATEGORY.get((group, category)) or MID_OTHER


SYNONYMS = {  # words a visitor may type -> tags, so "時給" finds a minimum-wage item and "はがき" finds the New Year cards
    "最低賃金": ["時給", "賃金", "バイト", "パート"], "年賀": ["年賀状", "はがき", "お正月"], "ふるさと納税": ["寄附", "返礼品"],
    "共通テスト": ["大学入試", "センター試験", "受験"], "TOEIC": ["英語", "資格", "試験"], "流星群": ["星", "天体観測", "天文"],
    "コミックマーケット": ["コミケ", "同人誌", "即売会"], "ゲームマーケット": ["ボードゲーム", "即売会"], "ドラフト": ["野球", "プロ野球", "NPB"],
    "日本シリーズ": ["野球", "プロ野球"], "箱根駅伝": ["駅伝", "お正月"], "紅白": ["大みそか", "NHK", "歌合戦"], "プライム": ["Amazon", "セール", "買い物"],
    "雪まつり": ["雪", "北海道", "札幌"], "ルミナリエ": ["イルミネーション", "神戸", "光"],
}
REQUIRED = ("title", "date", "kind", "category", "source_url", "checked_on")


def _d(s) -> date | None:
    try:
        y, m, dd = str(s).split("-")
        return date(int(y), int(m), int(dd))
    except Exception:
        return None


def entry_id(item: dict) -> str:
    key = f"{item.get('source_url', '')}|{item.get('date', '')}|{item.get('kind', '')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def shown_kind(item: dict) -> str:
    """The word a card or page shows for the kind.  The id keeps the stored kind, so a page does not move when this word changes:
    a horse race is held (not a 'final'), and Jupiter's opposition is not a 'peak'."""
    kind = item.get("kind", "")
    if kind == "決勝" and item.get("subject") == "競馬":
        return "開催"
    if kind == "極大" and "衝" in str(item.get("title", "")):
        return "衝"
    return kind


def labels_for(item: dict, group: str) -> tuple[str, str, str]:
    """(subject, what, place) for a card: what the topic is, what the day is, where.  A seed item that has no such fields falls back
    to its category ("その他" -> the group), its kind and its region ("地域" says nothing, so it becomes empty)."""
    category = item.get("category") or ""
    subject = str(item.get("subject") or "").strip() or (group if category in ("", "その他") else category)
    what = str(item.get("what") or "").strip() or str(item.get("kind") or "")
    if item.get("place") is not None:
        place = str(item["place"]).strip()
    else:
        region = item.get("region") or ""
        place = "" if region == "地域" else region
    return subject, what, place


def tags_for(item: dict, group: str) -> list[str]:
    subject, what, _ = labels_for(item, group)
    tags = [group, item.get("category") or "", item.get("region") or "", subject, what]
    title = item.get("title", "")
    for key, extra in SYNONYMS.items():
        if key in title:
            tags += extra
    out, seen = [], set()
    for t in tags:
        if t and t != "全国" and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def load_seeds(seed_dir: Path = SEED_DIR) -> list[tuple[str, dict]]:
    out = []
    for path in sorted(seed_dir.glob("seed_*.json")):
        base = path.name.rsplit("_2026", 1)[0] if "_2026" in path.name else path.stem
        for it in json.loads(path.read_text(encoding="utf-8")):
            out.append((base, it))
    return out


def build_catalog(today: date, seed_dir: Path = SEED_DIR, blocklist: dict | None = None) -> tuple[list[dict], Counter]:
    block = blocklist if blocklist is not None else (json.loads((seed_dir / "blocklist.json").read_text(encoding="utf-8"))
                                                       if (seed_dir / "blocklist.json").exists() else {"keywords": []})
    entries, rejects, seen, seen_days = [], Counter(), set(), set()
    for base, it in load_seeds(seed_dir):
        if not it.get("verified"):
            rejects["未確認"] += 1
            continue
        if any(not it.get(k) for k in REQUIRED):
            rejects["必須の項目なし"] += 1
            continue
        if not str(it["source_url"]).startswith("https://"):
            rejects["出典が https でない"] += 1
            continue
        d, checked = _d(it["date"]), _d(it["checked_on"])
        if d is None or checked is None or checked > today:
            rejects["日付が不正"] += 1
            continue
        if any(k in it["title"] for k in block.get("keywords", [])):
            rejects["除外リスト"] += 1
            continue
        end = _d(it.get("date_end")) if it.get("date_end") else None
        last = end or d
        if last < today - timedelta(days=KEEP_AFTER_DAYS):
            rejects["終了して30日超"] += 1
            continue
        group = (it.get("group") if it.get("group") in GROUPS else None) or GROUP_OF_SUBJECT.get(str(it.get("subject") or "").strip()) or GROUP_OF_CATEGORY.get(it["category"]) or GROUP_OF_FILE.get(base)
        if not group:
            rejects["ジャンル不明"] += 1
            continue
        eid = entry_id(it)
        if eid in seen:
            rejects["重複"] += 1
            continue
        seen.add(eid)
        same_day = (str(it["title"]).strip(), it["date"])        # the same event listed in two seed files (a marathon in the regional and the sports file): the first file's entry stays
        if same_day in seen_days:
            rejects["重複(同名同日)"] += 1
            continue
        seen_days.add(same_day)
        sens = it.get("sensitivity") or "none"
        quiet = sens in QUIET
        lead = LEAD.get(it.get("kind"), LEAD_DEFAULT)
        it = {**it, "kind": shown_kind(it)}
        subject, what, place = labels_for(it, group)
        entries.append({
            "id": eid, "title": it["title"].strip(), "date": it["date"], "date_end": it.get("date_end") or None,
            "precision": it.get("precision") if it.get("precision") in ("day", "month") else "day",
            "weekday": WEEKDAYS[d.weekday()], "kind": it["kind"], "category": it["category"], "group": group, "mid": mid_for(group, subject, it["category"]), "region": it.get("region") or None,
            "subject": subject, "what": what, "place": place,
            "tags": tags_for(it, group), "sensitivity": sens, "quiet": quiet, "ad_ok": bool(it.get("ad_ok", True)) and not quiet,
            "son_toku": bool(it.get("son_toku")), "source_url": it["source_url"], "source_quote": (it.get("source_quote") or "")[:60] or None,
            "checked_on": it["checked_on"], "status": ("ended" if last < today else ("old_checked" if (today - checked).days > STALE_DAYS else "active")),
            "publish_on": max(date(2000, 1, 1), d - timedelta(days=lead)).isoformat(),
        })
    entries.sort(key=lambda e: (e["date"], e["title"]))
    return entries, rejects


def indexable_ids(entries: list[dict], today: date, launch: date, per_week: int = 6) -> set[str]:
    """Which entries may be indexed by search engines today.  A new domain should not publish hundreds of pages at once:
    an entry is indexable when its lead time has begun, it has not ended, its source check is not stale and the weekly allowance
    (per_week x weeks since launch, soonest date first) has room.  The rest stay usable on the site (noindex, not in the sitemap)."""
    weeks = max(0, (today - launch).days // 7) + 1
    allowed = per_week * weeks
    eligible = [e for e in entries if e["status"] == "active" and e["publish_on"] <= today.isoformat()]
    eligible.sort(key=lambda e: (e["date"], e["title"]))
    return {e["id"] for e in eligible[:allowed]}


def public_json(entries: list[dict]) -> list[dict]:
    """The fields the browser needs (assets/catalog.json)."""
    keys = ("id", "title", "date", "date_end", "precision", "weekday", "kind", "category", "group", "mid", "region", "subject", "what", "place", "tags", "quiet", "ad_ok", "son_toku", "status")
    return [{k: e[k] for k in keys} for e in entries]
