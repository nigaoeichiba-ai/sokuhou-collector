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

GROUPS = ["手続き・お金", "買い物・サービス", "スポーツ", "学校・資格", "空・季節", "おでかけ・地域", "乗り物・レース", "趣味・ゲーム・アニメ", "エンタメ・音楽・賞", "暮らし・健康・グルメ"]
# The first six keep their place (and so their colour and shape); the last three were split out of "マニア・天文" and "大会・番組" on 2026-10-10.
GROUP_OF_CATEGORY = {
    "税": "手続き・お金", "年金・保険": "手続き・お金", "給付": "手続き・お金", "制度": "手続き・お金", "料金": "手続き・お金",
    "セール": "買い物・サービス", "ふるさと納税": "買い物・サービス", "年賀状": "買い物・サービス", "ポイント": "買い物・サービス",
    "サービス終了": "買い物・サービス", "料金改定": "買い物・サービス",
    "大学入試": "学校・資格", "高校入試": "学校・資格", "資格": "学校・資格", "就活": "学校・資格", "奨学金": "学校・資格", "公務員": "学校・資格",
    "野球": "スポーツ", "サッカー": "スポーツ", "駅伝・マラソン": "スポーツ", "相撲": "スポーツ", "フィギュア": "スポーツ",
    "番組": "エンタメ・音楽・賞", "音楽": "エンタメ・音楽・賞", "ライブ": "エンタメ・音楽・賞",
    "天文": "空・季節",
    "鉄道": "乗り物・レース", "乗り物": "乗り物・レース",
    "即売会": "趣味・ゲーム・アニメ", "ゲーム・アニメ": "趣味・ゲーム・アニメ", "ホビー": "趣味・ゲーム・アニメ",
    "祭り": "おでかけ・地域", "花火": "おでかけ・地域", "イルミネーション": "おでかけ・地域", "紅葉・花": "おでかけ・地域", "スキー": "おでかけ・地域",
    "初詣・初日の出": "おでかけ・地域", "施設": "おでかけ・地域",
}
# a few topics sit under the catch-all category "その他" (or a neighbour's category) in the seeds; the topic decides the genre
GROUP_OF_SUBJECT = {
    "ラグビー": "スポーツ", "競馬": "乗り物・レース", "将棋": "趣味・ゲーム・アニメ", "食べ歩き": "暮らし・健康・グルメ", "スイーツ": "暮らし・健康・グルメ", "日本酒": "暮らし・健康・グルメ", "カニ": "暮らし・健康・グルメ", "マラソン": "スポーツ", "女子マラソン": "スポーツ",
    "F1": "乗り物・レース",
    "ノーベル賞": "エンタメ・音楽・賞", "アカデミー賞": "エンタメ・音楽・賞", "映画祭": "エンタメ・音楽・賞", "映画賞": "エンタメ・音楽・賞",
    "コミックマーケット": "趣味・ゲーム・アニメ",
    "宝くじ": "買い物・サービス", "年金(iDeCo)": "手続き・お金", "住宅の補助金": "手続き・お金", "共通テスト": "学校・資格",
}
GROUP_OF_FILE = {"seed_tax_law": "手続き・お金", "seed_consumer": "買い物・サービス", "seed_exams": "学校・資格", "seed_sports_culture": "スポーツ",
                 "seed_otaku_astro": "趣味・ゲーム・アニメ", "seed_regional": "おでかけ・地域"}
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
            "weekday": WEEKDAYS[d.weekday()], "kind": it["kind"], "category": it["category"], "group": group, "region": it.get("region") or None,
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
    keys = ("id", "title", "date", "date_end", "precision", "weekday", "kind", "category", "group", "region", "subject", "what", "place", "tags", "quiet", "ad_ok", "son_toku", "status")
    return [{k: e[k] for k in keys} for e in entries]
