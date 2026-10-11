"""atomou: three 特集 pages under /kyou/ - 祝日と連休 (/kyou/holidays-YYYY/), 季節の便り (/kyou/season/), 12月の日めくり (/kyou/december/).

All three are made when the site is built, from our own counts (calendar_data.py), the Observatory's solar terms (data/atomou/solar_terms.json) and the catalogue of official days.
Nothing is copied from another page.  Each says where its facts come from and how they were processed ("加工して作成").  The page is the same for everybody; "あと○日" is filled in
by the visitor's own clock (data-cd), and the term / day of today is marked by the script (pageSpecial in assets/app.js).  The pages are not in the menu: they hang under /kyou/."""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

from sites.atomou import calendar_data as cal

CAO = "https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html"
OPERATOR = "株式会社MACS"
SPECIAL_KIND = "special"


def _b():
    from sites.atomou import build   # the page helpers live in build.py (it imports this module): taken when a page is made
    return build


def md(d: date) -> str:
    return f"{d.month}月{d.day}日({cal.wd(d)})"


def cd(d: date) -> str:
    return f'<span class="cd" data-cd="{d.isoformat()}"></span>'


def years_for(today: date) -> list[int]:
    """The years that get a holiday page: this year and the next (the next one is what people plan for from autumn on)."""
    return [today.year, today.year + 1]


def holiday_page(c, y: int) -> str:
    B = _b()
    esc = B.esc
    hol = cal.holidays(y)
    runs = cal.runs(y, 3)
    br = [x for x in cal.bridges(y) if x["start"].year == y or x["end"].year == y]
    st = cal.year_stats(y)
    rows = "".join(f'<tr><th scope="row">{md(d)}</th><td>{esc(n)}</td><td>{cd(d)}</td></tr>' for d, n in hol.items())
    run_li = "".join(
        f'<li><b>{md(r["start"])}〜{md(r["end"])}</b> {r["days"]}連休 <span class="muted">({esc("・".join(dict.fromkeys(r["holidays"])))})</span> {cd(r["start"])}'
        f' <a class="small" href="/add/?title={quote(str(r["start"].month) + "月の" + str(r["days"]) + "連休")}&amp;date={r["start"].isoformat()}">予定に入れる</a></li>' for r in runs)
    br_li = "".join(
        f'<li>{md(b["take"])}を休むと、{md(b["start"])}〜{md(b["end"])}の<b>{b["days"]}連休</b>になります。</li>' for b in br) or "<li>この年は、1日休んで5連休以上になる所は、ありません。</li>"
    mc = cal.month_counts(y)
    months = "".join(f"<tr><th scope=\"row\">{m}月</th><td>{n}日</td></tr>" for m, n in mc.items())
    wdc = {i: 0 for i in range(7)}
    for d in cal.base_holidays(y):
        wdc[d.weekday()] += 1
    weekdays = "".join(f"<tr><th scope=\"row\">{cal.WD[i]}曜日</th><td>{n}日</td></tr>" for i, n in wdc.items())
    cmp_rows = "".join(
        f'<tr><th scope="row">{s["year"]}年</th><td>{s["days_off_by_holiday"]}日</td><td>{s["overlap"]}日</td><td>{s["runs3"]}回</td><td>{s["longest"]}日</td></tr>'
        for s in (cal.year_stats(x) for x in range(2020, y + 1)))
    body = B.crumbs([("トップ", "/"), ("今日は何の日", "/kyou/"), (f"{y}年の祝日と連休", None)]) + f"""
<h1>{y}年の祝日と連休</h1>
<p class="lead muted">{y}年の祝日と、3連休以上になる所、1日休むと連休が長くなる所を、まとめました。日付は、祝日法のきまりから数え直しています。</p>
<div class="figures"><p><b>{len(hol)}</b><span>日の休み(祝日・振替休日)</span></p><p><b>{st["runs3"]}</b><span>回の3連休以上</span></p><p><b>{st["longest"]}</b><span>日の最長連休(土日・祝日だけ)</span></p><p><b>{st["overlap"]}</b><span>日の祝日が、土曜か日曜と重なる</span></p></div>
<h2>{y}年の祝日</h2>
<div class="tablewrap"><table class="info-table"><thead><tr><th scope="col">日付</th><th scope="col">名前</th><th scope="col">あと何日</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>3連休以上</h2>
<p class="hint">土曜・日曜・祝日がつづく日数です。勤め先や学校の休みは、人によって違います。</p>
<ul class="kyou-rows special-rows">{run_li}</ul>
<h2>1日休むと、連休が長くなる所</h2>
<p class="hint">有給休暇などで休める場合の例です。休めるかどうかは、勤め先の決まりによります。</p>
<ul class="kyou-rows special-rows">{br_li}</ul>
<h2>月ごと・曜日ごとの祝日</h2>
<div class="twocol"><div class="tablewrap"><table class="info-table"><caption>月ごと(振替休日をふくむ)</caption><tbody>{months}</tbody></table></div>
<div class="tablewrap"><table class="info-table"><caption>曜日ごと(祝日そのもの。振替休日は数えない)</caption><tbody>{weekdays}</tbody></table></div></div>
<h2>2020年からくらべる</h2>
<div class="tablewrap"><table class="info-table"><thead><tr><th scope="col">年</th><th scope="col">休みの日数</th><th scope="col">土日と重なる祝日</th><th scope="col">3連休以上</th><th scope="col">最長の連休</th></tr></thead><tbody>{cmp_rows}</tbody></table></div>
<p class="hint">2020年と2021年は、東京オリンピックにあわせて、海の日・スポーツの日・山の日が動いた年です。</p>
<h2>日付のもとになったもの</h2>
<p class="small muted">国民の祝日は、「国民の祝日に関する法律」で決まっています。内閣府の<a href="{CAO}" rel="noopener nofollow" target="_blank">「国民の祝日について」</a>で公表されている内容をもとに、{OPERATOR}が、きまり(日付、月の第○月曜日、春分・秋分、振替休日、国民の休日)から数え直し、集計して作成しました。内閣府の発表と食いちがいがあるときは、内閣府の発表が正しいものです。</p>"""
    title = f"{y}年の祝日と連休 3連休以上・休みの取りどころ | {B.NAME}"
    desc = f"{y}年の祝日は{len(hol)}日、3連休以上は{st['runs3']}回。1日休むと連休が長くなる所と、あと何日かも分かります。"[:150]
    return c.page(f"/kyou/holidays-{y}/", title, desc, body, SPECIAL_KIND)


def season_page(c, entries: list[dict]) -> str:
    B = _b()
    esc = B.esc
    today = c.today
    ys = [y for y in (today.year, today.year + 1) if cal.terms_of(y)]
    pool = [e for e in entries if e["precision"] == "day" and not e["quiet"] and not e.get("estimated") and e["status"] != "ended"]
    blocks = []
    for y in ys:
        terms = cal.terms_of(y)
        z = cal.solar_terms()["zassetsu"].get(str(y)) or []
        nxt_all = terms[1:] + [cal.terms_of(y + 1)[0] if cal.terms_of(y + 1) else None]
        li = []
        for t, nx in zip(terms, nxt_all):
            if t["date"] + timedelta(days=60) < today:
                continue            # long past: not listed
            end = nx["date"] if nx else date(y, 12, 31)
            near = [e for e in pool if t["date"] <= date.fromisoformat(e["date"]) < end and not e["title"].startswith(t["name"])][:3]   # the term's own day is not "a day near it"
            near_html = "".join(f'<li><a href="/e/{e["id"]}/">{esc(e["title"])}</a> <span class="muted">{esc(B.fmt_date(e["date"]))}</span></li>' for e in near)
            li.append(f'<article class="term" data-d="{t["date"].isoformat()}"><h3>{esc(t["name"])} <span class="muted">{md(t["date"])} {t["time"]}ごろ</span> {cd(t["date"])}</h3>'
                      f'<p>{esc(cal.TERM_MEANING[t["name"]])}</p>' + (f'<p class="small muted">この頃にある日</p><ul class="kyou-rows">{near_html}</ul>' if near_html else "") + "</article>")
        zr = "".join(f'<li><b>{esc(n)}</b> {md(date(y, int(d[:2]), int(d[3:])))} {cd(date(y, int(d[:2]), int(d[3:])))}</li>' for n, d in z if date(y, int(d[:2]), int(d[3:])) >= today - timedelta(days=30))
        blocks.append(f'<h2>{y}年の二十四節気</h2>{"".join(li)}' + (f'<h3>{y}年の雑節</h3><ul class="kyou-rows special-rows">{zr}</ul>' if zr else ""))
    body = B.crumbs([("トップ", "/"), ("今日は何の日", "/kyou/"), ("季節の便り", None)]) + f"""
<h1>季節の便り 二十四節気</h1>
<p class="lead muted">二十四節気は、1年を24に分けた、季節の目安です。約15日ごとに、次の節気に替わります。</p>
<section class="season-now" id="season-now" aria-live="polite"><p class="muted">いまの節気を調べています…</p></section>
{"".join(blocks)}
<h2>日付のもとになったもの</h2>
<p class="small muted">二十四節気と雑節の日付は、国立天文台 暦計算室の「暦要項」(<a href="{cal.solar_terms()['pages']['2026']}" rel="noopener nofollow" target="_blank">令和8年</a>・<a href="{cal.solar_terms()['pages']['2027']}" rel="noopener nofollow" target="_blank">令和9年</a>)をもとに、{OPERATOR}が整理して作成しました(時刻は中央標準時)。説明の文は、当サイトで書いたものです。来年の分は、国立天文台が2月に発表したあとに足します。</p>"""
    return c.page("/kyou/season/", f"季節の便り 二十四節気の日付と、あと何日 | {B.NAME}", "二十四節気の日付と、次の節気まであと何日か。その頃にある公式の日も、あわせて見られます。", body, SPECIAL_KIND)


def december_page(c, entries: list[dict]) -> str:
    B = _b()
    esc = B.esc
    y = c.today.year
    hol = cal.holidays(y) if y >= 2020 else {}
    terms = {t["date"]: t["name"] for t in cal.terms_of(y)}
    pool = [e for e in entries if e["precision"] == "day" and not e["quiet"] and not e.get("estimated")]
    days = []
    for n in range(1, 32):
        d = date(y, 12, n)
        its = sorted((e for e in pool if e["date"] == d.isoformat()), key=lambda e: e["title"])
        tags = ([hol[d]] if d in hol else []) + ([terms[d]] if d in terms else [])
        lis = "".join(f'<li><a href="/e/{e["id"]}/">{esc(e["title"])}</a> <span class="badge">{esc(e["kind"])}</span></li>' for e in its)
        inner = (f'<ul class="kyou-rows">{lis}</ul>' if lis else '<p class="small muted">この日の公式の日は、まだ載せていません。</p>')
        days.append(f'<article class="day" data-d="{d.isoformat()}"><h3>{n}日({cal.wd(d)}) {"".join(f"<span class=badge>{esc(t)}</span> " for t in tags)}{cd(d)}</h3>{inner}</article>')
    total = sum(1 for e in pool if e["date"].startswith(f"{y}-12"))
    body = B.crumbs([("トップ", "/"), ("今日は何の日", "/kyou/"), (f"{y}年12月の日めくり", None)]) + f"""
<h1>{y}年12月の日めくり</h1>
<p class="lead muted">12月1日から31日まで、1日ごとに、その日が期限・開始・節目の公式の日を並べました。いまは{total}件です。</p>
<section class="day-now" id="day-now" aria-live="polite"></section>
{"".join(days)}
<h2>ご利用の前に</h2>
<p class="small muted">各日の詳しいページに、出典の公式ページと確認日があります。税や制度の期限は、申し込みや手続きの前に、出典の公式ページで確かめてください。祝日と二十四節気の日付は、それぞれ<a href="/kyou/holidays-{y}/">{y}年の祝日と連休</a>、<a href="/kyou/season/">季節の便り</a>のもとと同じです。</p>"""
    return c.page("/kyou/december/", f"{y}年12月の日めくり 1日ごとの公式の日 | {B.NAME}", f"{y}年12月1日から31日まで、期限・開始・節目の公式の日を、1日ごとに。あと何日かも分かります。", body, SPECIAL_KIND)


def special_pages(c, entries: list[dict]) -> dict[str, str]:
    out = {}
    for y in years_for(c.today):
        out[f"kyou/holidays-{y}/index.html"] = holiday_page(c, y)
    out["kyou/season/index.html"] = season_page(c, entries)
    out["kyou/december/index.html"] = december_page(c, entries)
    return out


def special_links(today: date) -> str:
    """The 特集 block of /kyou/: the way into the three pages."""
    ys = years_for(today)
    items = "".join(f'<li><a href="/kyou/holidays-{y}/"><b>{y}年の祝日と連休</b><span>3連休以上と、休みの取りどころ</span></a></li>' for y in ys[::-1])
    items += '<li><a href="/kyou/season/"><b>季節の便り</b><span>二十四節気まで、あと何日</span></a></li>'
    items += f'<li><a href="/kyou/december/"><b>{today.year}年12月の日めくり</b><span>1日ごとの公式の日</span></a></li>'
    return f'<h2>特集</h2><ul class="special-links">{items}</ul>'
