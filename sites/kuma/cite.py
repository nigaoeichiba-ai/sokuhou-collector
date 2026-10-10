"""/cite/ -- where every number on the site comes from, how it is counted, how far it can be trusted, and how to quote it.

Everything on the page is counted from the data the build was given (the stored rows and counts), so it cannot disagree with the other pages.
The comparison with the Ministry of the Environment's published figures uses the same months on both sides (April to the latest month the
ministry has published) and only prefectures that the site covers as a whole (a source that covers only part of a prefecture is left out).
"""
from __future__ import annotations

from collections import Counter

from sites.kuma.fmt import fy_label, jp_date, md, n, table
from sites.kuma.live import LIVE_SOURCES, licensed_sources
from sokuhou import prefectures as pf
from sokuhou.sitekit import crumbs, esc

NO_LICENSE_TEXT = "再利用の許可が明示されていないため、件数と最新の日付だけを載せています"
RATE_LIMIT_TEXT = "取得元ごとの数え方が違うため、取得元どうしの件数は、足したり比べたりしないでください"


def _month_counts(records: list[dict], key: str) -> dict[int, int]:
    c = Counter(int(r["at"][5:7]) for r in records if r["src"] == key)
    return dict(c)


def source_rows(d: dict, lv: dict) -> list[dict]:
    """One dict per source the site shows (records or counts only), north to south."""
    recs = lv["records"]
    per_src = Counter(r["src"] for r in recs)
    out: list[dict] = []
    for k, i in lv["infos"].items():
        meta = LIVE_SOURCES.get(k, {})
        out.append({"key": k, "pref": i["pref"], "name": i["name"], "mode": "records", "count": per_src[k], "latest": i["as_of"],
                    "fetched": i["fetched"], "page": i["page"], "note": i["note"], "scope": meta.get("scope", ""),
                    "license": meta["license"], "months": _month_counts(recs, k)})
    for c in lv["counts"]:
        meta = LIVE_SOURCES.get(c["key"], {})
        out.append({"key": c["key"], "pref": c["pref"], "name": c["name"], "mode": "counts", "count": c["total"], "latest": c["latest"],
                    "fetched": c["fetched"], "page": c["page"], "note": c["note"], "scope": meta.get("scope", ""), "license": NO_LICENSE_TEXT,
                    "months": {int(m): v for m, v in c["monthly"].items()}})
    out.sort(key=lambda r: pf.SHORT.index(r["pref"]))
    return out


def ministry_rows(d: dict, rows: list[dict]) -> tuple[list[list[str]], list[dict], list[int]]:
    """(table rows, compared items, the months compared).  Only whole-prefecture sources, only months the ministry has published."""
    cur, li = d["cur"], d["li"]
    months = d["months"][: li + 1]
    items: list[dict] = []
    for r in rows:
        if r["scope"]:
            continue
        slug = pf.SLUG[r["pref"]]
        mrow = d["by_slug"][slug]
        vals = mrow["monthly"][cur][: li + 1]
        if not mrow["has"] or all(v is None for v in vals):
            continue
        env = sum(v or 0 for v in vals)
        ours = sum(r["months"].get(m, 0) for m in months)
        if not ours:        # the site holds nothing for these months (a source that starts later, or an empty period): there is nothing to compare
            continue
        items.append({"slug": slug, "pref": r["pref"], "name": r["name"], "mode": r["mode"], "env": env, "ours": ours})
    out = []
    for x in items:
        ratio = "同じ" if x["env"] == x["ours"] else (f"{round(x['ours'] / x['env'] * 100)}%" if x["env"] else "-")
        out.append([f'<a href="/live/{x["slug"]}/">{esc(pf.full(x["pref"]))}</a>', esc("記録" if x["mode"] == "records" else "件数のみ"),
                    n(x["env"]), n(x["ours"]), ratio])
    return out, items, months


def covered_prefs(rows: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """(prefectures with records, prefectures with counts only, prefectures with nothing) -- by short name, a part-of-prefecture source counts too."""
    rec = {r["pref"] for r in rows if r["mode"] == "records"}
    cnt = {r["pref"] for r in rows if r["mode"] == "counts"} - rec
    none = [p for p in pf.SHORT if p not in rec and p not in cnt]
    return sorted(rec, key=pf.SHORT.index), sorted(cnt, key=pf.SHORT.index), none


def cite_page(page, d: dict, lv: dict, cfg: dict, base: str) -> str:
    cur, today = d["cur"], lv["today"]
    rows = source_rows(d, lv)
    rec_prefs, cnt_prefs, none_prefs = covered_prefs(rows)
    n_rec = sum(1 for r in rows if r["mode"] == "records")
    n_cnt = sum(1 for r in rows if r["mode"] == "counts")
    src_table = table(
        ["取得元", "載せ方", f"{fy_label(cur)}の件数", "最新の日付", "取得日", "利用条件", "取得元の更新"],
        [[f'<a href="{esc(r["page"])}" rel="noopener" target="_blank">{esc(r["name"])}</a>' + (f"<br><small>{esc(r['scope'])}のみ</small>" if r["scope"] and not r["scope"].endswith("のみ") else (f"<br><small>{esc(r['scope'])}</small>" if r["scope"] else "")),
          "記録(一覧・市町村・CSV)" if r["mode"] == "records" else "件数のみ", n(r["count"]), md(r["latest"]), md(r["fetched"]), esc(r["license"]), esc(r["note"])]
         for r in rows])
    cmp_rows, items, months = ministry_rows(d, rows)
    same = sum(1 for x in items if x["env"] == x["ours"])
    same_text = f"のうち、<strong>{n(same)}都道府県は、1件も違いません</strong>(同じ元データを数えているとみられます)" if same else ""
    m_from, m_to = months[0], months[-1]
    cmp_html = ""
    if cmp_rows:
        cmp_html = f"""<h2>環境省の数字と、当サイトの数字の差(同じ期間で)</h2>
<p>環境省が都道府県から聞き取って公表している出没件数(速報値・{md(d['sight_updated'])}公表)と、当サイトが取得元から数えた件数を、<strong>同じ期間({fy_label(cur)}の{m_from}月〜{m_to}月)</strong>で並べました。比べられる{n(len(items))}都道府県{same_text}。</p>
{table(["都道府県", "当サイトの載せ方", f"環境省({m_from}〜{m_to}月)", "当サイト(同じ期間)", "当サイト÷環境省"], cmp_rows)}
<p class="notice">差が出る主な理由: 取得元が数える対象が違う(青森県の「確認済みの報告のみ」、山口県の「県警が認知した分のみ」など)、環境省の集計の時点と、取得元の更新の時点が違う、取得元が後から追加・修正した、の3つです。環境省の資料は、都道府県ごとに数え方が違うと注記しています。地域の一部だけの取得元(空知管内、大津市など)と、その期間の記録を当サイトが持っていない取得元は、比べていません。</p>
"""
    csv_note = ('<a href="/data/">データのダウンロード(CSV)のページ</a>の CSV には、利用条件が明示されている取得元だけを入れ、行ごとに、取得元と利用条件を書いています。'
                if licensed_sources(lv) else "")
    partial = [f"{pf.full(r['pref'])}は{r['scope'] if r['scope'].endswith('のみ') else r['scope'] + 'のみ'}" for r in rows if r["scope"]]
    partial_text = f"({'、'.join(partial)})" if partial else ""
    covered = f"""<h2>どの地域が載っているか</h2>
<p>取得元があるのは、<strong>{n(len(rec_prefs) + len(cnt_prefs))}都道府県</strong>です(記録まで載せているのは{n(len(rec_prefs))}、件数だけは{n(len(cnt_prefs))}){esc(partial_text)}。記録つき: {esc('・'.join(pf.full(p) for p in rec_prefs))}。件数だけ: {esc('・'.join(pf.full(p) for p in cnt_prefs))}。</p>
<p>載っていない地域({n(len(none_prefs))}都道府県)があります。<strong>「載っていない」は、「出没がない」「安全」という意味ではありません。</strong>当サイトが、使える取得元を、まだ持っていないだけです。その地域は、<a href="/ranking/sightings/">各都道府県のページ</a>から、環境省の公表値と、公式の出没情報へのリンクを見てください。</p>
"""
    example_src = max((r for r in rows if r["mode"] == "records" and not r["scope"]), key=lambda r: r["count"], default=None)
    example = ""
    if example_src:
        slug = pf.SLUG[example_src["pref"]]
        example = (f'<li><strong>数字を引用する例</strong>: 「{esc(pf.full(example_src["pref"]))}の{fy_label(cur)}の記録は{n(example_src["count"])}件'
                   f'({jp_date(example_src["latest"])}の分まで)。出典: {esc(example_src["name"])}の公開データを、クマ出没速報(<a href="/live/{slug}/">{esc(base + "/live/" + slug + "/")}</a>)が加工して作成。'
                   f'{jp_date(today.isoformat())}閲覧」</li>\n')
    body = f"""{crumbs([("全国", "/"), ("データの出典・引用のしかた", None)])}
<h1>データの出典・数え方・引用のしかた</h1>
<p class="lead">このサイトの数字が、どこから来て、どう数えられ、どこまで信頼できるかを、公開します。報道・研究・自治体の資料に、お使いいただいて構いません。使うときは、下の「引用のしかた」のとおり、出典を書いてください。基準日: {jp_date(today.isoformat())}(このページは、データが更新されるたびに作り直します)。</p>
<h2>1. 取得元の一覧({n(len(rows))}か所)</h2>
<p>当サイトは、<strong>自治体・国などの公式の公開データだけ</strong>を使っています。報道・SNS・住民の投稿・他のサイトが集めたデータは、使っていません。再利用の許可が明示されている{n(n_rec)}か所は、詳しい記録(一覧・市町村ページ・地図・CSV)まで載せ、許可が明示されていない{n(n_cnt)}か所は、市町村・月・件数・最新の日付だけを載せています(大津市のように、市のページが公開している情報でも、許可が明示されていなければ、件数だけです)。環境省の出没件数と人身被害の資料(速報値)は、<a href="/ranking/sightings/">都道府県ランキング</a>などで使っています。</p>
{src_table}
<p class="notice">{esc(RATE_LIMIT_TEXT)}。「取得日」は、当サイトが取得元を確認した日です。各取得元の出典の書き方は、各ページの末尾にあります。{csv_note}</p>
{covered}
<h2>2. 更新のしかた</h2>
<ul>
<li>当サイトは、<strong>3時間ごと</strong>に、取得元を確認しています(環境省の資料は、1日1回)。取得元が実際に更新するのは、日次・週次・月次など、取得元によって違います(表の「取得元の更新」)。当サイトの反映は、取得元の更新より、遅れます。</li>
<li>件数だけを載せている取得元は、取得元の規約と robots.txt を確認し、当サイトの識別名を名乗って、間隔をあけて取得します。取得元から止めてほしいと連絡があれば、その取得元の掲載を止めます。</li>
<li>取得したデータは、保存する前に検算します。日付や市町村が読めない行が多い、前回より3割以上減った、取得元の表の形が変わった、といったときは、<strong>保存せずに、前回のデータを使い続けます</strong>(誤った数字を、新しい数字として出さないためです)。</li>
</ul>
<h2>3. 数え方と、加工したこと</h2>
<ul>
<li><strong>1件</strong>は、取得元の表の<strong>1行</strong>です。取得元が「目撃」「痕跡」「人身被害」などを区別している場合は、その区分のまま載せ、件数には、取得元が載せている全部が入ります(区分ごとの内訳は、各ページの表にあります)。</li>
<li>年度は、4月から翌年3月です(令和8年度=2026年4月〜2027年3月)。月別の件数は、取得元の日付から数えています。</li>
<li>市町村名は、郡の名前を除いてそろえています(「阿武郡阿武町」は「阿武町」)。市町村が読めない行は、市町村別の表から除き、除いた割合が大きいときは、そのデータを保存しません。</li>
<li>別々の行として載っている報告を、1件にまとめることは、していません(同じ出没が重ねて通報されていれば、重ねて数えています)。</li>
<li>各ページの数字は、保存した行・件数から、そのつど数えています(文章に、手で数字を書いていません)。個別の記録を、市町村名のそろえ(郡の名前の除去)のほかに、人や AI が書き換えることは、していません。</li>
<li>地図に点を出すのは、取得元が座標を公表している記録だけです(小数点以下4桁に丸めています)。座標がない記録は、一覧と件数だけです。</li>
</ul>
{cmp_html}<h2>4. 既知の制約</h2>
<ul>
<li>{esc(RATE_LIMIT_TEXT)}。</li>
<li>通報から取得元の公表まで、日がかかります。当サイトの「最新の日付」は、取得元が公表した最新の日で、「いま」ではありません。</li>
<li>山の奥の出没は、通報されにくく、住宅地や道路の近くの出没が、多く見えます。</li>
<li>クマ以外の動物の見間違いが、含まれることがあります。</li>
<li>取得元が、過去の記録を直したり、消したりすることがあります。当サイトは、取得のたびに、最新の状態に置き換えます。</li>
</ul>
<h2>5. 引用のしかた</h2>
<ul>
<li><strong>ページを引用する例</strong>: 「クマ出没速報『最新のクマの目撃情報(自治体の公式)』({esc(base)}/live/)、{jp_date(today.isoformat())}閲覧」</li>
{example}<li><strong>基準日を書いてください</strong>。数字は、日々変わります(このページの基準日は、{jp_date(today.isoformat())}です)。</li>
<li>元の取得元の利用条件が、先に適用されます。CSV を再利用するときは、行ごとの「取得元・ライセンス」に従ってください(多くは、出典の表示)。件数だけを載せている取得元の記録は、各県の公式ページを、お使いください。</li>
<li>当サイトは、環境省・自治体が公表した情報を、加工して作成したもので、環境省・自治体が作成したものではありません。「環境省の発表」「県の発表」のように、書き換えないでください。</li>
<li>取材・研究のためのご質問は、<a href="/contact/">お問い合わせ</a>へ(個別のデータの提供は、していません)。</li>
</ul>
<h2>6. 誤りの連絡・掲載の中止</h2>
<p>数字や記録に誤りを見つけたとき、取得元の方が、掲載の中止をご希望のときは、<a href="/contact/">お問い合わせ</a>の「データの誤りのご指摘」または「掲載内容に関するご連絡」から、お知らせください。確認のうえ、速やかに直す、または掲載を取りやめます。</p>
<h2>7. 運営</h2>
<p>運営者は、<a href="/about/">運営者情報</a>のとおりです。広告と、商品のリンク(PR と表示)から、収入を得ています。広告やリンクの有無で、データの載せ方を変えることは、していません。</p>"""
    return page(path="/cite/", title="データの出典・数え方・引用のしかた(クマ出没速報)",
                description=f"クマ出没速報の数字の取得元({n(len(rows))}か所)・更新のしかた・数え方・既知の制約と、環境省の数字との差、引用のしかたを公開しています。", body=body)
