"""福島県内の、複数の公開情報で一致を確認できたクマの目撃(福島市の公開ページと、福島テレビの記事の2媒体だけを使う)。

福島県は、広告つきのサイトでの県の目撃データ(ArcGIS)の利用を許可しなかった(2026-11)。このアダプタは、県のデータ・県の公開ページ・県の担当者の情報を、一切読まない。
読むのは次の2つだけ:
  1. 福島市の公開ページ(クマの出没情報の表)。日付・場所・種類。
  2. 福島テレビの「【熊出没】」の記事(警察の発表をまとめたもの。直近 TV_DAYS 日分)。日付・市町村・地名。
同じ市町村・同じ日の目撃が、2つの媒体の両方にあるときだけ、「複数の公開情報で一致した」ものとして、出典を示さずに、日付・場所・種類を保存する(オーナーの方針 2026-10-13。
基準は、これまでの `corroborated.confirm` と同じ: 同じ市町村・同じ日、1つの記事の行は1件としか対応しない)。
2媒体のどちらかにしかない目撃(福島テレビにだけある福島市以外の市町村、福島市のページにあっても福島テレビの期間より前のもの)は、保存しない。
福島テレビの記事は直近 TV_DAYS 日分しか読めないので、一致を確認できた目撃は、前回までに保存したものに足していく(`accumulate`)。
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import date

from sokuhou.sources import corroborated as co
from sokuhou.sources import kumacounts, kumalib

CREDIT = ("複数の公開情報で一致を確認できた目撃を、公開されている情報から、当サイトが集計して作成(福島県・福島市・福島テレビが作成したものではありません)")
UPDATE_NOTE = ("1日1回更新します。最新の記録は、更新時点から遅れます。件数は、複数の公開情報で一致を確認できた目撃だけで、福島県内の目撃の全体の件数ではありません。"
               "目撃のほか、痕跡の報告を含みます")
PAGE = co.FUKUSHIMA_CITY_PAGE
MIN_CONFIRMED = 1
TV_DAYS = 35               # the station keeps its day lists for about a month (2026-11-12: the oldest story was of 10-14)


class FukushimaMediaSourceError(ValueError):
    pass


def pair(city_rows: list[dict], tv_rows: list[dict]) -> tuple[list[dict], dict]:
    """The records of the city page that the television stories also hold (same municipality, same day), newest first, and the counts of what was left out.

    One story line confirms one record only (a multiset match), so two sightings on one day need two lines on each side."""
    have = Counter((r["observed_at"], r["city"]) for r in tv_rows)
    kept, left_city = [], 0
    for r in sorted(city_rows, key=lambda r: (r["observed_at"], r["place"]), reverse=True):
        key = (r["observed_at"], r["city"])
        if have[key] > 0:
            have[key] -= 1
            kept.append(r)
        else:
            left_city += 1
    return kept, {"city_only": left_city, "tv_only": sum(have.values()), "city_rows": len(city_rows), "tv_rows": len(tv_rows)}


def package(records: list[dict], today: date) -> dict:
    return kumalib.package_counts(source="fukushima_media", credit=CREDIT, update_note=UPDATE_NOTE, as_of=today, rows=records, page=PAGE, files=[PAGE]) | {
        "corroborated": sorted(records, key=lambda r: (r["observed_at"], r["place"]), reverse=True),
        "corroborated_on": {city: today.isoformat() for city in sorted({r["city"] for r in records})}}


def collect(fetch=None, sleep=None, now=None) -> dict:
    fetch = fetch or kumacounts.fetch
    nap = sleep or time.sleep
    today = kumacounts.today_jst(now)
    pause = lambda: nap(kumacounts.PAUSE)  # noqa: E731
    city_rows = co.html_reader(co.FUKUSHIMA_CITY_PAGE, co.parse_fukushima_city)(fetch, pause)       # a page that cannot be read raises: nothing is stored
    pause()
    tv_rows = co.ftv_reader(today, days=TV_DAYS)(fetch, pause)
    kept, _ = pair(co.current_year(city_rows, today), co.current_year(tv_rows, today))
    if len(kept) < MIN_CONFIRMED:
        raise FukushimaMediaSourceError("no sighting is held by both the city page and the television stories")
    return package(kept, today)


def accumulate(old: dict | None, new: dict) -> dict:
    """The stories reach back only TV_DAYS days: the sightings confirmed earlier in the fiscal year stay (a confirmed fact does not change)."""
    if not old or not old.get("corroborated"):
        return new
    today = date.fromisoformat(new["fetched_at"][:10])
    seen = {(r["observed_at"], r["city"], r["place"]) for r in new["corroborated"]}
    older = [r for r in co.current_year(old["corroborated"], today) if (r["observed_at"], r["city"], r["place"]) not in seen]
    if not older:
        return new
    return {**package(new["corroborated"] + older, today), "fetched_at": new["fetched_at"]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
