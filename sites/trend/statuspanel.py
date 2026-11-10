"""The status panel of trend-sokuho.com (common part, owner/desk decision 2026-11-10): a title, an "as of" line with the numbers, rows of gauges, a box of key points, one note.
The typhoon page uses it first (the same look as the 防災チェック panel: white ground, red frame, a word for every step, the numbers kept as text).

An article puts its numbers in the content JSON under "status_typhoon" and prepare() in hooks.py turns them into HTML.  The class (the step of the ladder) and the danger
level (the gauge) are worked out here from the maximum wind speed, so a follow-up report only replaces the numbers.  Nothing is sent anywhere: it is plain HTML."""
from __future__ import annotations

import html

# JMA's classes of a typhoon by the maximum wind speed (m/s): (lower bound, name, range shown on the step)
LADDER = [(0, "熱帯低気圧", "17m/s未満"), (17, "台風", "17〜33m/s"), (33, "強い", "33〜44m/s"), (44, "非常に強い", "44〜54m/s"), (54, "猛烈な", "54m/s以上")]
# the site's own reading of the maximum wind speed against JMA's wording of the strength of wind (upper bound exclusive, level, wording)
DANGER = [(15, 1, "やや強い風"), (20, 2, "強い風"), (30, 3, "非常に強い風"), (40, 4, "猛烈な風"), (10 ** 9, 5, "猛烈な風")]
NOTE = "危険度は、最大風速を気象庁の「風の強さ」の表現に当てはめた、このサイトの見方です。階級の名前が「台風」でも、弱いという意味ではありません。"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def klass(wind: float) -> int:
    idx = 0
    for i, (lo, _, _) in enumerate(LADDER):
        if wind >= lo:
            idx = i
    return idx


def danger(wind: float) -> tuple[int, str]:
    for hi, level, word in DANGER:
        if wind < hi:
            return level, word
    raise ValueError(wind)


def ladder_html(now: int) -> str:
    cur = ' aria-current="true"'
    steps = "".join('<div class="step%s"%s>%s<br>%s</div>' % (" now" if i == now else "", cur if i == now else "", esc(n), esc(r)) for i, (_, n, r) in enumerate(LADDER))
    return f'<div class="ladder">{steps}</div>'


def gauge_html(level: int) -> str:
    segs = "".join('<div class="seg%s"></div>' % (" on%d" % i if i <= level else "") for i in range(1, 6))
    return f'<div class="gauge" role="img" aria-label="危険度 5段階の{level}">{segs}</div>'


def typhoon_panel(st: dict) -> str:
    """st: label ("台風32号"), asof ("10日16時現在"), pressure (hPa), wind, gust (m/s), cls (the class JMA names, checked against the wind), impact {area, until, prob},
    extratropical ("10日21時" or null: the typhoon has become an extratropical low)."""
    wind = st["wind"]
    head = (f'<p class="sp-title">{esc(st["label"])}のステータス</p>\n'
            f'<p class="sp-asof">{esc(st["asof"])}（気象庁の発表）／中心気圧 {esc(st["pressure"])}hPa、最大風速 {esc(wind)}m/s、最大瞬間風速 {esc(st["gust"])}m/s</p>\n')
    if st.get("extratropical"):
        body = f'<div class="sp-row"><p class="sp-value">温帯低気圧に変わりました（{esc(st["extratropical"])}、気象庁）</p></div>\n'
    else:
        now = klass(wind)
        if st.get("cls") and st["cls"] != LADDER[now][1]:
            raise SystemExit(f"status panel: JMA's class {st['cls']!r} does not match the wind {wind}m/s ({LADDER[now][1]!r})")
        level, word = danger(wind)
        body = (f'<div class="sp-row">\n<p class="sp-label">気象庁の階級</p>\n<p class="sp-value">{esc(LADDER[now][1])} <span class="num">（最大風速{esc(wind)}m/s）</span></p>\n{ladder_html(now)}\n</div>\n'
                f'<div class="sp-row">\n<p class="sp-label">危険度（風の強さ）</p>\n<p class="sp-value">5段階の {level} <span class="num">「{esc(word)}」に当たる強さです</span></p>\n{gauge_html(level)}\n'
                f'<p class="sp-note">{esc(NOTE)}</p>\n</div>\n')
    im = st.get("impact")
    impact = ""
    if im:
        if not im.get("only_area"):
            raise SystemExit("status panel: the impact box has only the confirmed wording (the area is the only one above 1%); a different case needs a new wording from the desk")
        impact = (f'<div class="sp-impact"><b>影響の見込み：</b>{esc(im["area"])}が暴風域に入る確率は、{esc(im["until"])}までに{esc(im["prob"])}%です。'
                  f'本土に近づく見込みはなく、暴風域に入る確率が1%以上になった区域は{esc(im["area"])}だけです。</div>\n')
    return f'<section class="status-panel">\n{head}{body}{impact}</section>'
