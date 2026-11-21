"""相談型モデルケース(記事制作ルール 2026-11-20): the articles written as a consultation, from the manuscripts in consult/*.md.

The manuscript is plain Markdown: `#` the title, `##` the sections, `-` lists, a short line before a list is a list heading, a line in （ ） at the top is the
note of the model case, `（この予定は…画像ファイル：X.png…）` places the schedule picture, `〔アフィリ設置箇所：…〕` marks where an advertisement is planned
(nothing is shown until the partnership of this site is approved; the markers are listed by `affiliate_slots()` for the report) and the closing `（注記）`.
The screen names no source or survey (owner decision D26); a model case is never presented as a real person's story.
"""
from html import escape
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent / "consult"
CHECKED = "2026-11-20"

META = (
    {
        "slug": "case-first-living", "hero": "hero-first-living", "hero_alt": "就職を控えた大学生が実家の食卓で賃貸物件の間取りを確認する様子", "file": "first-living.md", "timeline": "timeline-first-living",
        "theme": "就職・一人暮らし", "household": "単身", "tag": "新社会人・初めての一人暮らし",
        "lead": "来春に就職して一人暮らしを始めるときの初期費用は、契約・引越し・家具家電で合計52万円。貯蓄65万円から初任給までの生活費13万円を残す分け方を、収支のリストと予定表で整理します。",
        "amount": "520,000円（初期費用の合計）", "condition": "家賃7万円・敷金礼金各1か月分の契約条件で、引越しと家具・家電を含む場合",
        "alt": "就職して一人で暮らし始めるまでのスケジュール表。2026年12月の住まい探しから2029年3月の賃貸更新まで",
        "related": (("tools.html#savings", "毎月の準備額を計算する"), ("basics-savings.html", "口座を分ける前に確認すること"),
                    ("basics-household.html", "年払いの支出を家計に入れる")),
    },
    {
        "slug": "case-childbirth-leave", "hero": "hero-childbirth-leave", "hero_alt": "出産を控えた夫婦が赤ちゃんの服と準備のノートを確認する様子", "file": "childbirth-leave.md", "timeline": "timeline-childbirth-leave",
        "theme": "出産・育休", "household": "子どもが生まれる世帯", "tag": "共働き・第1子の出産前",
        "lead": "出産費用の自己負担は8万円の見込み。出産手当金と育児休業給付金は入金が後になるため、生活費2か月分ほどの手元資金で給付を待つ家計計画を、予定表と収支のリストで整理します。",
        "amount": "80,000円（出産費用の自己負担の見込み）", "condition": "出産育児一時金を差し引いた自己負担の見込み",
        "alt": "出産と育休の予定表。2026年12月の積立開始から2028年5月の復職まで",
        "related": (("tools.html#savings", "出産までの毎月の準備額を計算する"), ("basics-protection.html", "保険を選ぶ前に確認すること"),
                    ("basics-household.html", "年払いの支出を家計に入れる")),
    },
    {
        "slug": "case-parent-care", "hero": "hero-parent-care", "hero_alt": "母と息子が玄関先で段差と手すりの取り付け場所を相談する様子", "file": "parent-care.md", "timeline": "timeline-parent-care",
        "theme": "親の介護", "household": "夫婦と親", "tag": "50代夫婦・親が要介護2",
        "lead": "親が要介護2と認定されたとき、毎月の自己負担は約1万8千円、住宅改修は最終的な自己負担が8万円の見込みで、償還払いなら支払い時に26万円が必要です。親御さんの家計と子世帯の家計を分ける考え方を、予定表と収支のリストで整理します。",
        "amount": "約18,000円（毎月の介護サービスの自己負担）", "condition": "要介護2・負担割合1割のケアプランの場合",
        "alt": "親の介護の予定表。2026年11月の認定から2027年4月の積立開始まで",
        "related": (("tools.html#annual", "年ごとの積立計画を作る"), ("basics-protection.html", "保険を選ぶ前に確認すること"),
                    ("events.html?event=care", "介護に必要なお金のテーマを見る")),
    },
    {
        "slug": "case-deposit-types", "hero": "hero-deposit-types", "hero_alt": "中学生のお子さまとご夫婦が食卓で進学に向けたお金について話す様子", "file": "deposit-types.md", "timeline": "timeline-deposit-types",
        "theme": "貯蓄・預金", "household": "共働き・子どもが中学生", "tag": "計算・比較型",
        "lead": "使う時期が決まっているお金は、普通預金と定期預金のどちらに置くか。300万円を1年預けた場合の利息の差は税引前で6千円です。使う時期で分ける目安と注意点を、利息の計算つきで整理します。",
        "amount": "300万円を1年預けた利息の差は税引前6千円",
        "alt": "使う時期と預金の置き場所の一覧。3か月以内は普通預金、1年後は定期預金1年、3年後は定期預金3年",
        "related": (("tools.html#deposit", "預金の利息を比較する"), ("basics-savings.html", "口座を分ける前に確認すること"),
                    ("tools.html#savings", "毎月の準備額を計算する")),
        "kind": "比較",
    },
)

LABEL = re.compile(r"^[^。]{1,20}$")
IMAGE_LINE = re.compile(r"^（この予定は|^（この分け方は")
AFFILIATE = re.compile(r"^〔アフィリ設置箇所：(.*)〕$")
BUDGET_ROW = re.compile(r"^(.+?)(?:　+| {2,})([^（]+?)(（.+）)?$")
BUDGET_SUMMARIES = {"合計", "残り", "月の残り"}


def _blocks(text):
    """Markdown -> [(kind, payload)] with kind in h1 note h2 p ul ol image slot footnote."""
    out, para, items, ordered = [], [], [], False
    def flush_list():
        nonlocal items
        if items:
            out.append(("ol" if ordered else "ul", items)); items = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            flush_list(); continue
        if line.startswith("# "):
            out.append(("h1", line[2:]))
        elif line.startswith("## "):
            flush_list(); out.append(("h2", line[3:]))
        elif line.startswith("- "):
            ordered = False; items.append(line[2:])
        elif re.match(r"^\d+\. ", line):
            ordered = True; items.append(re.sub(r"^\d+\. ", "", line))
        elif IMAGE_LINE.match(line):
            flush_list(); out.append(("image", line))
        elif AFFILIATE.match(line):
            flush_list(); out.append(("slot", AFFILIATE.match(line)[1]))
        elif line.startswith("（注記）"):
            flush_list(); out.append(("footnote", line[4:]))
        elif line.startswith("（") and line.endswith("）") and not any(k == "note" for k, _ in out):
            flush_list(); out.append(("note", line[1:-1]))
        else:
            flush_list(); out.append(("p", line))
    flush_list()
    # a short line right before a list is that list's heading
    fixed = []
    for i, (k, v) in enumerate(out):
        nxt = out[i + 1][0] if i + 1 < len(out) else ""
        if k == "p" and nxt in ("ul", "ol") and LABEL.match(v):
            fixed.append(("h3", v))
        else:
            fixed.append((k, v))
    return fixed


def parse(meta):
    blocks = _blocks((HERE / meta["file"]).read_text(encoding="utf-8"))
    title = next(v for k, v in blocks if k == "h1")
    note = next((v for k, v in blocks if k == "note"), "")
    sections, cur = [], None
    for k, v in blocks:
        if k == "h2":
            cur = {"h": v, "blocks": []}; sections.append(cur)
        elif cur is not None and k not in ("h1", "note"):
            cur["blocks"].append((k, v))
    footnote = ""
    for s in sections:
        s["blocks"] = [(k, v) for k, v in s["blocks"] if k != "footnote" or not (footnote := v)]
    points = []
    for s in sections:
        if "結論" in s["h"]:
            points = [v for k, items in s["blocks"] if k == "ul" for v in items]
    return {"title": title, "note": note, "sections": sections, "footnote": footnote, "points": points}


def affiliate_slots():
    """The planned advertisement places of every manuscript (not shown on the page): [(slug, text)]."""
    return [(m["slug"], v) for m in META for k, v in _blocks((HERE / m["file"]).read_text(encoding="utf-8")) if k == "slot"]


def _budget_list(items):
    rows = []
    for item in items:
        match = BUDGET_ROW.fullmatch(item)
        if not match:
            rows.append(f"<li>{escape(item)}</li>")
            continue
        label, amount, note = match.groups()
        row_class = ' class="budget-summary"' if label in BUDGET_SUMMARIES else ""
        detail = f'<span class="budget-note">{escape(note)}</span>' if note else ""
        rows.append(
            f'<li{row_class}><span>{escape(label)}</span>'
            f'<span class="budget-amount">{escape(amount.strip())}</span>{detail}</li>'
        )
    return '<ul class="budget-list" role="list">' + "".join(rows) + "</ul>"


def _render_section(section, meta):
    is_budget = section["h"].startswith("現在の収支")
    return "".join(
        _budget_list(value) if is_budget and kind == "ul" else _render_block(kind, value, meta)
        for kind, value in section["blocks"]
    )


def _render_block(kind, value, meta):
    if kind == "p":
        return f"<p>{escape(value)}</p>"
    if kind == "h3":
        return f"<h3>{escape(value)}</h3>"
    if kind in ("ul", "ol"):
        return f"<{kind}>" + "".join(f"<li>{escape(x)}</li>" for x in value) + f"</{kind}>"
    if kind == "image":
        return (f'<figure class="schedule-figure"><img src="assets/{meta["timeline"]}.webp" alt="{escape(meta["alt"], quote=True)}" '
                f'width="1240" height="{625 if meta["slug"] == "case-deposit-types" else 948}" loading="lazy"></figure>')
    return ""     # slot: nothing is shown before an approved partnership


def build(meta):
    """CASES-compatible dict, with the whole body rendered in `body_html`."""
    d = parse(meta)
    toc = "".join(f'<li><a href="#part-{i}">{escape(s["h"])}</a></li>' for i, s in enumerate(d["sections"], 1))
    body = "".join(
        f'<section class="guide-section consult-section" id="part-{i}"><h2>{escape(s["h"])}</h2>'
        + _render_section(s, meta) + "</section>"
        for i, s in enumerate(d["sections"], 1))
    foot = f'<p class="consult-footnote">{escape(d["footnote"])}</p>' if d["footnote"] else ""
    note = f'<p class="consult-note">{escape(d["note"])}</p>' if d["note"] else ""
    return {
        "slug": meta["slug"], "image": f'{meta["hero"]}-card', "theme": meta["theme"], "household": meta["household"], "tag": meta["tag"],
        "title": d["title"], "lead": meta["lead"], "amount": meta["amount"], "condition": meta.get("condition", ""), "checked": CHECKED, "alt": meta["alt"],
        "related": meta["related"], "hero": meta["hero"], "hero_alt": meta["hero_alt"], "points": tuple(d["points"]), "sections": (),
        "consult": True, "kind": meta.get("kind", "相談型モデルケース"), "toc_html": toc,
        "body_html": note + body + foot,
    }


CONSULT = tuple(build(m) for m in META)
