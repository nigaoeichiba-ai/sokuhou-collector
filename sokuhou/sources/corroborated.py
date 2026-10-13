"""Sightings that two independent publications agree on (kuma-sokuho.com).

Rule (owner, 2026-10-13): a fact that is published by two or more media is a widely known fact and may be shown; no source or link is named for it.
So a municipality's own page (medium 1) is read for its records (date, place, kind) and a record is KEPT only if the prefecture's list (medium 2,
already read by the counts adapter) holds a record of the same municipality on the same day.  Each prefecture record can confirm at most one municipal
record (a multiset match), so two sightings on one day need two prefecture rows.  Everything that is not confirmed stays what it was: a count.

The parsers read the municipalities' own pages (static HTML); every request goes through `kumalib.polite_fetch` (robots.txt, identifying User-Agent).
A page that cannot be read raises `CorroboratedError`; the caller then stores no records for that run (the counts are unaffected).
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from collections import Counter
from datetime import date, datetime

from sokuhou.sources import kumalib

ERA_REIWA_OFFSET = 2018      # Reiwa N = 2018 + N
MAX_PLACE = 80


class CorroboratedError(ValueError):
    pass


def decode(body: bytes) -> str:
    m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', body[:4000])
    enc = m.group(1).decode("ascii", "replace") if m else "utf-8"
    try:
        return body.decode(enc, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def clean(text: str) -> str:
    """Tags removed, entities decoded, NFKC (full-width digits and letters become ASCII), spaces squeezed."""
    text = htmllib.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def kind_of(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    if re.search(r"痕跡|足跡|糞|食害|食痕|食べ|破損|爪|唸り声|うなり声|疑い", t) and not re.search(r"目撃", t):
        return "痕跡"
    if re.search(r"捕獲|駆除", t) and not re.search(r"目撃", t):
        return "捕獲"
    if "目撃" in t:
        return "目撃"
    return "その他"


def fy_year_from_heading(html: str) -> int:
    """The fiscal year (calendar year of April) from '令和8年度' in the page; refuses a page that does not say."""
    years = [int(x) for x in re.findall(r"令和\s*(\d+)\s*年度", unicodedata.normalize("NFKC", html))]
    if not years:
        raise CorroboratedError("no '令和N年度' on the page")
    return ERA_REIWA_OFFSET + max(years)       # a link to last year's list must not decide the year


def day_in_fy(fy_start: int, month: int, day: int) -> date:
    try:
        return date(fy_start if month >= 4 else fy_start + 1, month, day)
    except ValueError as e:
        raise CorroboratedError(f"impossible date {month}/{day}") from e


def reiwa_day(era: int, month: int, day: int) -> date:
    try:
        return date(ERA_REIWA_OFFSET + era, month, day)
    except ValueError as e:
        raise CorroboratedError(f"impossible date R{era} {month}/{day}") from e


def _record(day: date, city: str, place: str, kind: str, count: int | None) -> dict:
    place = re.sub(r"\s+", " ", place).strip(" 　,、。")[:MAX_PLACE]
    return {"observed_at": day.isoformat(), "city": city, "place": place, "kind": kind, "count": count}


# ---------------------------------------------------------------- the municipalities' pages

SAKATA_PAGE = "https://www.city.sakata.lg.jp/kurashi/doubutsu/yasei/kankyo0320260415.html"
YAMAGATA_CITY_PAGE = "https://www.city.yamagata-yamagata.lg.jp/kurashi/kankyohozen/1006552/1002384.html"
CHICHIBU_PAGE = "https://www.city.chichibu.lg.jp/10646.html"
OGANO_PAGE = "https://www.town.ogano.lg.jp/industry-bid-business/industry/kumanosyutubotujyouhou/"


def parse_sakata(html: str) -> list[dict]:
    """Sakata City: one table per month (No., date, time, area, place, summary)."""
    fy = fy_year_from_heading(html)
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        m = re.fullmatch(r"(\d{1,2})月(\d{1,2})日", cells[1])
        if not m:
            raise CorroboratedError(f"Sakata: unreadable date {cells[1]!r}")
        summary = cells[5]
        detail = re.match(r"(字[^\s、。()（）]{1,10}?地内)", summary)
        place = cells[4] + (detail.group(1) if detail else "")
        count = kumalib.fullwidth_to_int(summary)
        out.append(_record(day_in_fy(fy, int(m.group(1)), int(m.group(2))), "酒田市", place, kind_of(summary), count))
    if not out:
        raise CorroboratedError("Sakata: no rows")
    return out


def parse_yamagata_city(html: str) -> list[dict]:
    """Yamagata City: lines 'No.108  10月3日(土曜)  午前11時00分頃  大字柏倉地内の山林にてクマ1頭を目撃' under a '令和8年度' heading."""
    fy_now = None                    # the fiscal year of the section a line is in: '【令和8年度クマ出没状況】' starts one
    out = []
    for line in re.split(r"<br\s*/?>|</p>", html):
        text = clean(line)
        head = re.search(r"【令和\s*(\d+)\s*年度", text)
        if head:
            fy_now = ERA_REIWA_OFFSET + int(head.group(1))
            continue
        if fy_now is None:
            continue
        fy = fy_now
        m = re.match(r"No\.\s*\d+\s+(\d{1,2})月(\d{1,2})日\s*\([^)]*\)\s*(?:午[前後]\d{1,2}時\d{1,2}分頃?)?\s*(.+)$", text)
        if not m:
            continue
        rest = m.group(3)
        place, _, tail = rest.partition("にて")
        if not tail:
            place, tail = rest, rest
        out.append(_record(day_in_fy(fy, int(m.group(1)), int(m.group(2))), "山形市", place, kind_of(tail), kumalib.fullwidth_to_int(tail)))
    if not out:
        raise CorroboratedError("Yamagata City: no rows")
    return out


def parse_chichibu(html: str) -> list[dict]:
    """Chichibu City (Arakawa district): numbered lines '9．令和8年10月9日  荒川上田野地内（諸上橋付近）' (a trace is marked '※ 出没痕跡')."""
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
        text = clean(p)
        m = re.match(r"\d+[.．]\s*令和\s*(\d+)年\s*(\d+)月\s*(\d+)日\s*(.+)$", text)
        if not m:
            continue
        rest = m.group(4)
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "秩父市", re.sub(r"※.*$", "", rest),
                           "痕跡" if "痕跡" in rest else "目撃", None))
    if not out:
        raise CorroboratedError("Chichibu: no rows")
    return out


def parse_ogano(html: str) -> list[dict]:
    """Ogano Town: lines '令和８年１０月６日  河原沢  大諸バス停北西１５０ｍ付近' (a two-day line such as '７月１５・１６日' counts for its first day)."""
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
        text = clean(p)
        m = re.match(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)(?:・\d+)*日\s*(.+)$", text)
        if not m:
            continue
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "小鹿野町", m.group(4), "目撃", None))
    if not out:
        raise CorroboratedError("Ogano: no rows")
    return out


JOETSU_PAGE = "https://www.city.joetsu.niigata.jp/soshiki/kankyo/kinkyuzi-bear.html"
JOETSU_HEAD = re.compile(r"^\s*(\d+)\s+(\d{1,2})月(\d{1,2})日\([^)]*\)\s+\S+\s+(\S+?区)\s+(\S+)", re.M)


def joetsu_pdf_url(html: str, page_url: str = JOETSU_PAGE) -> str:
    """The PDF of the newest fiscal year ('令和8年度:90件 [PDFファイル]') on Joetsu City's page; its address changes with every update."""
    from urllib.parse import urljoin, urlparse
    best = None
    for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.S):
        m = re.match(r"令和\s*(\d+)\s*年度", clean(label))
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), urljoin(page_url, href))
    if best is None:
        raise CorroboratedError("no PDF of a fiscal year on the page")
    if urlparse(best[1]).netloc != urlparse(page_url).netloc:
        raise CorroboratedError(f"the PDF is not on the city's host: {best[1]}")
    return best[1]


def parse_joetsu_text(text: str) -> list[dict]:
    """Joetsu City's list (text of its PDF): '№ 月日 時刻 地域自治区 場所 状況' per sighting, the status text running over several lines."""
    text = unicodedata.normalize("NFKC", text)
    fy = fy_year_from_heading(text)
    heads = list(JOETSU_HEAD.finditer(text))
    out = []
    for i, m in enumerate(heads):
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        out.append(_record(day_in_fy(fy, int(m.group(2)), int(m.group(3))), "上越市", m.group(4) + m.group(5), kind_of(body), kumalib.fullwidth_to_int(body)))
    if not out:
        raise CorroboratedError("Joetsu: no rows")
    return out


def pdf_text(body: bytes) -> str:
    import io
    from pypdf import PdfReader
    return chr(10).join(p.extract_text() or "" for p in PdfReader(io.BytesIO(body)).pages)


def joetsu_reader(page_url: str = JOETSU_PAGE):
    def read(fetch, pause):
        pdf = joetsu_pdf_url(decode(fetch(page_url)), page_url)
        pause()
        return parse_joetsu_text(pdf_text(fetch(pdf)))
    read.label = page_url
    return read


# ---------------------------------------------------------------- round 2: more municipalities (2026-10-13)

TSURUOKA_PAGE = "https://www.city.tsuruoka.lg.jp/anzen/kuma/kuma08.html"
NANYO_PAGE = "http://www.city.nanyo.yamagata.jp/saigai/5126"
SHIRATAKA_PAGE = "https://www.town.shirataka.lg.jp/2403.htm"
SANJO_PAGE = "https://www.city.sanjo.niigata.jp/soshiki/keizaibu/nourinka/kumanikannsurukoto/2391.html"
MINANO_PAGE = "https://www.town.minano.saitama.jp/section/kankou/12181/"
HANNO_PAGE = "https://www.city.hanno.lg.jp/kurashi_seikatsukankyo/bosai_saigaiengo_kikikanri/kumanikannsurujoho/8564.html"


def table_rows(html: str) -> list[list[str]]:
    """Every table row of the page as a list of cell texts (header cells included)."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if cells:
            out.append(cells)
    return out


def _month_day(text: str):
    m = re.fullmatch(r"(\d{1,2})月(\d{1,2})日", text.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_tsuruoka(html: str) -> list[dict]:
    """Tsuruoka City: monthly tables (No., date, time, place [PDF link], area, status)."""
    fy = fy_year_from_heading(html)
    out = []
    for c in table_rows(html):
        if len(c) < 6 or not c[0].isdigit() or not _month_day(c[1]):
            continue
        month, day = _month_day(c[1])
        place = re.sub(r"[（(]PDF[：:][^）)]*[）)]", "", c[3]).strip()
        out.append(_record(day_in_fy(fy, month, day), "鶴岡市", place, kind_of(c[5]), kumalib.fullwidth_to_int(c[5])))
    if not out:
        raise CorroboratedError("Tsuruoka: no rows")
    return out


def parse_nanyo(html: str) -> list[dict]:
    """Nanyo City: one table for the calendar year '令和8年' (No., date, time, place, size, sign)."""
    years = [int(x) for x in re.findall(r"令和\s*(\d+)\s*年(?!度)", unicodedata.normalize("NFKC", html))]
    if not years:
        raise CorroboratedError("Nanyo: no '令和N年' on the page")
    year = ERA_REIWA_OFFSET + max(years)
    out = []
    for c in table_rows(html):
        if len(c) < 4 or not c[0].isdigit() or not _month_day(c[1]):
            continue
        month, day = _month_day(c[1])
        try:
            out.append(_record(date(year, month, day), "南陽市", c[3], "目撃", None))
        except ValueError as e:
            raise CorroboratedError(f"Nanyo: impossible date {c[1]}") from e
    if not out:
        raise CorroboratedError("Nanyo: no rows")
    return out


def parse_shirataka(html: str) -> list[dict]:
    """Shirataka Town: one table (No., 'M/D', time, district, content, map link) under '令和8年度'."""
    fy = fy_year_from_heading(html)
    out = []
    for c in table_rows(html):
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", c[1]) if len(c) >= 5 else None
        if not m or not c[0].isdigit():
            continue
        out.append(_record(day_in_fy(fy, int(m.group(1)), int(m.group(2))), "白鷹町", c[3], kind_of(c[4]), None))
    if not out:
        raise CorroboratedError("Shirataka: no rows")
    return out


def parse_sanjo(html: str) -> list[dict]:
    """Sanjo City: three tables (No., '令和8年9月17日', place, time, number of bears, injury, class, status)."""
    out = []
    for c in table_rows(html):
        if len(c) < 7 or not c[0].replace(" ", "").isdigit():
            continue
        m = re.fullmatch(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)日", c[1])
        if not m:
            continue
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "三条市", c[2], kind_of(c[6]), kumalib.fullwidth_to_int(c[4] + "頭") if c[4].isdigit() else None))
    if not out:
        raise CorroboratedError("Sanjo: no rows")
    return out


def parse_hanno(html: str) -> list[dict]:
    """Hanno City: tables (No., date and time, place, landmark); the page also lists neighbouring areas, which are not Hanno's."""
    out = []
    for c in table_rows(html):
        if len(c) < 3 or not c[0].isdigit():
            continue
        m = re.match(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)日", c[1])
        if not m or not c[2].startswith("飯能市"):
            continue
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "飯能市", " ".join(c[2:]), "目撃", None))
    if not out:
        raise CorroboratedError("Hanno: no rows")
    return out


def parse_minano(html: str) -> list[dict]:
    """Minano Town: areas ('金沢地内') as headings or bold lines, then '令和8年6月13日' with the place on the next line."""
    out = []
    area = None
    after_date = None                      # the date waiting for its place line
    lines = [clean(x) for x in re.split(r"<br\s*/?>|</p>|</h\d>|</li>|</div>", html)]
    for line in lines:
        if not line:
            continue
        m = re.fullmatch(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)日", line)
        if m:
            if after_date:                 # a date with no place line of its own
                out.append(_record(after_date, "皆野町", area or "", "目撃", None))
            after_date = reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            continue
        if after_date:
            if len(line) <= 60:
                out.append(_record(after_date, "皆野町", f"{area} {line}" if area else line, "目撃", None))
            after_date = None
            continue
        if re.fullmatch(r"\S{1,8}地内", line):
            area = line
    if after_date:
        out.append(_record(after_date, "皆野町", area or "", "目撃", None))
    if not out:
        raise CorroboratedError("Minano: no rows")
    return out


PARSERS_ROUND2 = {"tsuruoka": (TSURUOKA_PAGE, parse_tsuruoka), "nanyo": (NANYO_PAGE, parse_nanyo), "shirataka": (SHIRATAKA_PAGE, parse_shirataka),
                  "sanjo": (SANJO_PAGE, parse_sanjo), "minano": (MINANO_PAGE, parse_minano), "hanno": (HANNO_PAGE, parse_hanno)}


# ---------------------------------------------------------------- round 3: Fukushima City, Hirakawa City, Fukushima TV (2026-10-13)

FUKUSHIMA_CITY_PAGE = "https://www.city.fukushima.fukushima.jp/soshiki/6/1025/3/17619.html"
HIRAKAWA_PAGE = "https://www.city.hirakawa.lg.jp/kurashi/sumai/doubutsu/kumasyutsubotsu.html"
FTV_ROOT = "https://www.fukushima-tv.co.jp/localnews/"
FTV_DAYS = 21                 # day lists read per run (the station keeps about a month); older stories of this kind drop out of the table
FTV_MAX_ARTICLES = 40


def parse_fukushima_city(html: str) -> list[dict]:
    """Fukushima City: one table (No., '令和8年9月23日(水曜日) 12時30分', place + a map link, remarks)."""
    out = []
    for c in table_rows(html):
        if len(c) < 3 or not c[0].isdigit():
            continue
        m = re.match(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)日", c[1])
        if not m:
            continue
        note = c[3] if len(c) > 3 else ""
        place = re.sub(r"\s*\(獣マップへリンク\)\s*$", "", c[2]).strip()
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "福島市", place, kind_of(note) if note else "目撃", None))
    if not out:
        raise CorroboratedError("Fukushima City: no rows")
    return out


def parse_hirakawa(html: str) -> list[dict]:
    """Hirakawa City: one table (kind, '令和8年4月15日', time, place, detail); crop damage is a damage record, not a sighting."""
    out = []
    for c in table_rows(html):
        if len(c) < 5:
            continue
        m = re.fullmatch(r"令和\s*(\d+)年\s*(\d+)月\s*(\d+)日", c[1])
        if not m:
            continue
        kind = "目撃" if c[0] == "目撃" else ("被害" if "被害" in c[0] else kind_of(c[0] + c[4]))
        out.append(_record(reiwa_day(int(m.group(1)), int(m.group(2)), int(m.group(3))), "平川市", c[3], kind, kumalib.fullwidth_to_int(c[4])))
    if not out:
        raise CorroboratedError("Hirakawa: no rows")
    return out


def ftv_article_links(day_html: str) -> list[str]:
    """The addresses of the '【熊出没】' stories on one day's list of Fukushima TV."""
    out = []
    for href, inner in re.findall(r'href="(https://www\.fukushima-tv\.co\.jp/localnews/\d{4}/\d{2}/\d+\.html)"[^>]*>(.*?)</a>', day_html, re.S):
        if "【熊出没】" in clean(inner) and href not in out:
            out.append(href)
    return out


def parse_ftv_article(html: str, url: str) -> list[dict]:
    """One story: '【熊出没】10月3日(土)・4日(日)福島県のクマ目撃情報', then '【大玉村】' and bullets '・玉井袖窪 3日午前5時ごろ ...' (the day prefix only in
    a story of several days).  A bullet that cannot be dated is left out."""
    ym = re.search(r"/localnews/(\d{4})/(\d{2})/", url)
    if not ym:
        raise CorroboratedError("Fukushima TV: unexpected address")
    titles = [clean(t) for t in re.findall(r"【熊出没】[^<\n]*", html)]
    title = max(titles, key=len, default="")
    head = re.match(r"【熊出没】(.*?)福島県", title)
    if not head:
        raise CorroboratedError("Fukushima TV: no title")
    days, month = [], None
    for m in re.finditer(r"(?:(\d{1,2})月)?(\d{1,2})日", head.group(1)):
        month = int(m.group(1)) if m.group(1) else month
        if month:
            days.append((month, int(m.group(2))))
    if not days:
        raise CorroboratedError("Fukushima TV: no date in the title")
    year = int(ym.group(1)) - (1 if days[0][0] > int(ym.group(2)) + 6 else 0)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    lines = [clean(x) for x in re.split(r"<br\s*/?>|</p>|</div>|</li>", body)]
    city, out = None, []
    for line in lines:
        m = re.fullmatch(r"【([^】]+[市町村])】", line)
        if m:
            city = m.group(1)
            continue
        if not line.startswith("・") or not city:
            continue
        b = re.match(r"・\s*(\S+)\s+(?:(\d{1,2})日)?(.*)$", line)
        if not b:
            continue
        if b.group(2):
            pick = [md_ for md_ in days if md_[1] == int(b.group(2))]
            when = pick[0] if pick else None
        else:
            when = days[0] if len(days) == 1 else None
        if when is None:
            continue
        try:
            day = date(year, when[0], when[1])
        except ValueError:
            continue
        rest = b.group(3)
        out.append(_record(day, city, b.group(1), "痕跡" if re.search(r"痕跡|足跡|フン|糞", rest) else "目撃", kumalib.fullwidth_to_int(rest)))
    return out


def ftv_reader(today: date | None = None, days: int = FTV_DAYS):
    """Fukushima TV: the day lists of the last `days` days (the stories are dated by their own title), then each '【熊出没】' story once."""
    def read(fetch, pause):
        from datetime import timedelta
        end = today or datetime.now(kumalib.JST).date()
        links: list[str] = []
        for i in range(days):
            d = end - timedelta(days=i)
            pause()
            try:
                page = decode(fetch(f"{FTV_ROOT}{d.year}/{d.month:02d}/{d.day:02d}/"))
            except Exception:  # noqa: BLE001 - a day without a list (or a failed request) is only a missing day
                continue
            links += [u for u in ftv_article_links(page) if u not in links]
        if len(links) > FTV_MAX_ARTICLES:
            raise CorroboratedError(f"Fukushima TV: {len(links)} stories in {days} days (more than {FTV_MAX_ARTICLES}): the page has changed?")
        out: list[dict] = []
        for u in links:
            pause()
            out += parse_ftv_article(decode(fetch(u)), u)
        return out
    read.label = FTV_ROOT
    return read


# ---------------------------------------------------------------- round 5: Fukuchiyama City (Kyoto), monthly pages (2026-10-13)

FUKUCHIYAMA_PAGE = "https://www.city.fukuchiyama.lg.jp/soshiki/27/2615.html"


def fukuchiyama_month_links(top_html: str, era: int, base: str = FUKUCHIYAMA_PAGE) -> list[str]:
    """The monthly pages of fiscal year Reiwa `era` on the city's list page ('令和8年度目撃情報' then '・4月目撃情報' ...), up to the next fiscal year's heading."""
    from urllib.parse import urljoin, urlparse
    text = unicodedata.normalize("NFKC", top_html)
    start = text.find(f"令和{era}年度目撃情報")
    if start < 0:
        raise CorroboratedError(f"Fukuchiyama: no '令和{era}年度目撃情報' on the page")
    nxt = re.search(r"令和\d+年度目撃情報", text[start + 8:])
    block = text[start: start + 8 + nxt.start()] if nxt else text[start:]
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
        if re.search(r"\d{1,2}月目撃情報", clean(label)):
            u = urljoin(base, href)
            if urlparse(u).netloc == urlparse(base).netloc and u not in out:
                out.append(u)
    if not out:
        raise CorroboratedError("Fukuchiyama: no monthly pages")
    return out


def parse_fukuchiyama_month(html: str) -> list[dict]:
    """One monthly page: '熊出没情報〔令和8年10月分〕' and a table of ('5日(月曜日)', place with a PDF note)."""
    m = re.search(r"令和\s*(\d+)年\s*(\d+)月分", unicodedata.normalize("NFKC", html))
    if not m:
        raise CorroboratedError("Fukuchiyama: no month in the title")
    era, month = int(m.group(1)), int(m.group(2))
    out = []
    for c in table_rows(html):
        d = re.match(r"(\d{1,2})日", c[0]) if len(c) >= 2 else None
        place = re.sub(r"\s*\[PDF[^\]]*\]", "", c[1]).strip() if d else ""
        if not d or not place:
            continue
        year = ERA_REIWA_OFFSET + era
        out.append(_record(date(year, month, int(d.group(1))), "福知山市", place, "目撃", None))
    return out


def fukuchiyama_reader(era: int):
    """The city's list page, then each monthly page of the fiscal year (a month that cannot be read is skipped)."""
    def read(fetch, pause):
        links = fukuchiyama_month_links(decode(fetch(FUKUCHIYAMA_PAGE)), era)
        out: list[dict] = []
        for u in links:
            pause()
            try:
                out += parse_fukuchiyama_month(decode(fetch(u)))
            except Exception:  # noqa: BLE001 - one month down must not hide the others
                continue
        if not out:
            raise CorroboratedError("Fukuchiyama: no rows in any month")
        return out
    read.label = FUKUCHIYAMA_PAGE
    return read


# ---------------------------------------------------------------- the match

def confirm(prefecture_rows: list[tuple[date | None, object]], records: list[dict], norm_city=lambda c: str(c)) -> list[dict]:
    """The records that the prefecture's list also holds (same municipality, same day), newest first.

    prefecture_rows: (date or None, municipality) as the counts adapter reads them.  A prefecture row confirms one record only."""
    have = Counter((d.isoformat(), norm_city(c)) for d, c in prefecture_rows if d is not None)
    kept = []
    for r in sorted(records, key=lambda r: (r["observed_at"], r["place"]), reverse=True):
        key = (r["observed_at"], r["city"])
        if have[key] > 0:
            have[key] -= 1
            kept.append(r)
    return kept


def current_year(records: list[dict], today: date) -> list[dict]:
    """Only the current fiscal year (the January-March before it is not shown)."""
    start = date(kumalib.fiscal_start(today), 4, 1).isoformat()
    return [r for r in records if start <= r["observed_at"] <= today.isoformat()]


STORED_FIELDS = {"observed_at", "city", "place", "kind", "count"}


def html_reader(url: str, parser):
    """A reader of one static HTML page: read(fetch, pause) -> records."""
    def read(fetch, pause):
        return parser(decode(fetch(url)))
    read.label = url
    return read


def attach(result: dict, prefecture_rows, readers: list, fetch, today: date, pause=lambda: None,
           norm_city=lambda c: str(c)) -> dict:
    """Adds `corroborated` (the confirmed records, newest first) to a counts package.  Nothing is added when nothing could be confirmed;
    the problems of single pages are printed to stderr (the run goes on: the counts do not depend on these pages)."""
    import sys
    records, errors = collect_records(prefecture_rows, readers, fetch, today, pause, norm_city)
    for e in errors:
        print(f"corroborated: {e}", file=sys.stderr)
    if records:
        result["corroborated"] = records
        result["corroborated_on"] = {city: today.isoformat() for city in sorted({r["city"] for r in records})}      # the day each municipality was last read
    return result


CARRY_DAYS = 3


def carry_over(old: dict | None, new: dict) -> dict:
    """If a municipality's page could not be read today, keep its records that were confirmed within the last CARRY_DAYS days.

    (A page that is down for a day must not blank its rows; a page that stays unreadable stops being shown after CARRY_DAYS.)
    The facts do not change, so yesterday's confirmed record is still a confirmed record today."""
    if not old or not old.get("corroborated"):
        return new
    today = date.fromisoformat(new["fetched_at"][:10])
    seen = old.get("corroborated_on") or {}
    fresh = {r["city"] for r in new.get("corroborated", [])}
    kept = [r for r in old["corroborated"]
            if r["city"] not in fresh and r["city"] in seen and 0 <= (today - date.fromisoformat(seen[r["city"]])).days <= CARRY_DAYS]
    if not kept:
        return new
    merged = sorted(new.get("corroborated", []) + kept, key=lambda r: (r["observed_at"], r["place"]), reverse=True)
    on = {**{c: seen[c] for c in {r["city"] for r in kept}}, **(new.get("corroborated_on") or {})}
    return {**new, "corroborated": merged, "corroborated_on": dict(sorted(on.items()))}


def collect_records(prefecture_rows, readers: list, fetch, today: date, pause=lambda: None,
                    norm_city=lambda c: str(c)) -> tuple[list[dict], list[str]]:
    """readers: functions read(fetch, pause) -> records, each with a `label`.  Returns (what the prefecture also lists in the current
    fiscal year, [one message per reader that failed]).

    A reader that fails is skipped (its municipality shows no records that day); if every reader fails the caller stores no records at all."""
    found: list[dict] = []
    errors: list[str] = []
    for i, read in enumerate(readers):
        if i:
            pause()
        try:
            found += read(fetch, pause)
        except Exception as e:  # noqa: BLE001 - a municipality's page may change or be down; the counts must not depend on it
            errors.append(f"{getattr(read, 'label', read)}: {type(e).__name__}: {e}")
    return current_year(confirm(prefecture_rows, found, norm_city), today), errors
