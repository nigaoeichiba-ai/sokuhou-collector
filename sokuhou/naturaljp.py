"""naturaljp: a resident checker for Japanese that reads like a machine wrote it (stock phrases, stiff nominal style, flat rhythm, over-hedging).

Shared by every site and every session.  It reads the text a visitor would see (a built site folder, an html/json/md/txt file, or a string) and lists the places
that read stiff, with the rule, WHY it reads that way and which DIRECTION a fix goes.  It never rewrites anything.

    python -m sokuhou.naturaljp check yorokobu                 # a site name: its built folder (built on first use into out/naturaljp/<site>)
    python -m sokuhou.naturaljp check path/to/page.html path/to/dir --site minna
    python -m sokuhou.naturaljp check yorokobu --source        # the editors' source text (sites/<site>/content/**.json|md|txt) instead of the built pages
    python -m sokuhou.naturaljp text "文章を直接渡す" --site minna
    python -m sokuhou.naturaljp rules [--site NAME]            # every rule: level, why, fix
    python -m sokuhou.naturaljp audit [--builds DIR] [--md FILE]   # all five sites, in the inventory order, as a markdown report

Levels:  high = reads machine-made almost every time (a stock phrase);  mid = usually worth rewriting;  low = a signal worth a look, noisy alone.
Status:  REPORT only.  A rule becomes a publish gate by adding its id to GATE[site] (see the bottom of the rule table); `check --gate` then exits 1 on a hit.
         Promote only a rule with ~no false positives on the site's real text, and agree it with the report desk first.
Legal pages (policy, terms, licence ...) are skipped for style rules: their meaning must not change for style.  Yorokobu's comma gate (sites/yorokobu/commas.py) stays
the authority for its commas; the comma rule here is off for it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
SITES = ("yorokobu", "minna", "atomou", "kuma", "saichin")        # the inventory order (yorokobu first: the owner's strongest complaint)
LEVEL_RANK = {"low": 0, "mid": 1, "high": 2}

JP = r"ぁ-んァ-ヶー一-龥々〆"
KANJI = r"一-龥々〆"
EXEMPT_PATH = re.compile(r"(?:^|[/\\._-])(?:policy|policies|terms|privacy|legal|tokushoho|tokutei|license|licence|disclaimer|kiyaku|riyou-kiyaku|menseki|copyright)(?:[/\\._-]|$)", re.I)

# --------------------------------------------------------------------------------------------------------------------------------- the text model


@dataclass
class Block:
    kind: str        # heading | para | item | label | meta
    text: str
    line: int
    src: str = "html"
    quoted: bool = False   # inside a <blockquote>: an example text (a greeting, a sample message), not the site's own voice


@dataclass
class Hit:
    path: str
    line: int
    rule: str
    level: str
    sentence: str
    note: str = ""   # e.g. "3 on this page"


@dataclass
class Rule:
    id: str
    level: str
    why: str
    fix: str
    pattern: re.Pattern | None = None
    scope: str = "body"                  # body = para/item/meta/label sentences;  heading = headings only;  any;  block = the whole block's text
    min_ratio: float = 0.0               # ... and also at least this share of the page's sentences
    min_per_page: int = 1                # a density rule: reported only when it occurs this often on one page
    sites: tuple[str, ...] | None = None  # only these sites (None = all)
    off_sites: tuple[str, ...] = ()
    fn: Callable | None = None           # a programmatic rule: fn(block, sentences, prof) -> list[str] (the excerpts)
    bad: str = ""                        # an example of the problem (docs and tests use it)
    good: str = ""                       # the same thing, fixed


def rx(p: str, flags: int = 0) -> re.Pattern:
    return re.compile(p, flags)


# --------------------------------------------------------------------------------------------------------------------------------- site profiles
# long: a sentence over this many characters (spaces not counted) is worth splitting; very_long: it is hard to read.  core: the site's own words, which may repeat.
PROFILES: dict[str, dict] = {
    "default": dict(long=90, very_long=130, core=(), skip=(), hira=0.0),
    # adults who want to choose a gift calmly and quickly: calm, natural Japanese (STYLE_GUIDE_YOROKOBU_CODEX_2026-10-09.md).  Commas: sites/yorokobu/commas.py and its gate.
    # message/ holds sample messages for a friend or family (a soft tone and many hiragana are right there)
    "yorokobu": dict(long=90, very_long=125, core=("プレゼント", "ギフト", "贈り物", "贈る", "楽天市場", "ランキング"), skip=("comma_particle",), hira=0.80,
                     path_skip={"child_tone": r"^message/", "hiragana_heavy": r"^message/", "flowery": r"^(?:message|diagnosis)/"}),
    # adults and professionals; ordinary Japanese; few commas; kanji where kanji is normal (docs/MINNA_COPY_STYLE.md)
    "minna": dict(long=80, very_long=120, core=("イラスト", "素材", "画像", "無料", "ダウンロード", "シリーズ", "カテゴリ", "リクエスト"), skip=(), hira=0.76),
    # junior-high reader and up; do not add hiragana, no spaced writing (分かち書き), no feature that does not exist
    "atomou": dict(long=90, very_long=130, core=("カウントダウン", "あと何日", "もう何日", "カレンダー", "予定", "日付"), skip=("child_tone",), hira=0.76),
    # data sites: short facts first
    "kuma": dict(long=75, very_long=110, core=("クマ", "ツキノワグマ", "ヒグマ", "出没", "目撃", "情報", "市町村", "都道府県"), skip=("taigen_run", "noun_chain", "flowery"), hira=0.0),   # flowery: "そっと立ち去る" is meant literally
    "saichin": dict(long=75, very_long=110, core=("最低賃金", "時間額", "改定", "都道府県", "円", "発効日", "全国"), skip=("taigen_run", "noun_chain"), hira=0.0),
}


def profile(site: str | None) -> dict:
    return {**PROFILES["default"], **PROFILES.get(site or "", {})}


# --------------------------------------------------------------------------------------------------------------------------------- reading text out of html / json / md
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dt", "dd", "figcaption", "blockquote", "summary", "div", "section", "article", "header", "footer",
              "nav", "main", "aside", "ul", "ol", "table", "tr", "thead", "tbody", "br", "button", "label", "form", "details", "hr", "pre", "textarea", "caption", "fieldset", "legend"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "select", "code", "pre", "textarea", "iframe", "canvas", "math", "option"}
KIND_OF = {"h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading", "h6": "heading", "p": "para", "blockquote": "para", "dd": "para",
           "li": "item", "td": "item", "th": "item", "dt": "item", "figcaption": "label", "summary": "label", "button": "label", "label": "label", "caption": "label", "legend": "label"}


FIXUPS = (("Yahoo!", "Yahoo"), ("YAHOO!", "YAHOO"), ("Yahoo！", "Yahoo"))        # a brand name with a "!" is not an exclamation (and does not end a sentence)


LEAD_TAGS = {"b", "strong", "span", "small", "em", "i"}      # inline tags: a title in one of them, followed at once by another, is a separate text


def clean_space(s: str) -> str:
    for a, b in FIXUPS:
        s = s.replace(a, b)
    s = re.sub(rf"([{JP}])\s*\n\s*(?=[{JP}])", r"\1", s)          # a line break inside Japanese text is not a space in a browser
    return re.sub(r"[ \t\r\n\u00a0]+", " ", s).strip()


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.stack: list[str] = []
        self.skip = 0
        self.buf: list[str] = []
        self.kind = "label"
        self.line = 1
        self.in_title = False
        self.after_inline = False       # an inline element (b, span ...) has just closed with no text after it

    def flush(self):
        t = clean_space("".join(self.buf))
        self.buf = []
        if t and re.search(rf"[{JP}]", t):
            self.blocks.append(Block(self.kind, t, self.line, quoted="blockquote" in self.stack))
        self.kind, self.line = "label", self.getpos()[0]
        self.after_inline = False

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            a = dict(attrs)
            if (a.get("name") or "").lower() == "description" and a.get("content"):
                self.blocks.append(Block("meta", clean_space(a["content"]), self.getpos()[0]))
            return
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if tag == "title":
            self.in_title = True
        if tag in BLOCK_TAGS or (tag == "a" and any(t in self.stack for t in ("nav", "footer", "header", "li"))):    # links in a menu are separate labels, not one run of nouns
            self.flush()
            self.kind = KIND_OF.get(tag, "label")
            self.line = self.getpos()[0]
        elif tag in LEAD_TAGS and self.after_inline and self.buf and not SENT_END.search("".join(self.buf).strip()):
            kind = self.kind
            self.flush()                                  # <li><b>Title</b><span>Body</span></li>: the title and the body are two texts
            self.kind = kind
        if tag not in ("br", "hr", "img", "input", "link", "meta"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if tag == "title":
            self.in_title = False
            self.flush()
            return
        if tag in BLOCK_TAGS or (tag == "a" and any(t in self.stack for t in ("nav", "footer", "header", "li"))):
            self.flush()
        elif tag in LEAD_TAGS:
            self.after_inline = True
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self.skip:
            return
        if data.strip():
            self.after_inline = False
        if not self.buf:
            self.line = self.getpos()[0]
            if self.in_title:
                self.kind = "meta"
            elif self.kind == "label" and self.stack:
                for t in reversed(self.stack):                      # inherit the kind of the nearest block tag (a bare <a> inside an <li> is an item)
                    if t in KIND_OF:
                        self.kind = KIND_OF[t]
                        break
        self.buf.append(data)


def blocks_from_html(raw: str) -> list[Block]:
    p = _Html()
    p.feed(raw)
    p.flush()
    return p.blocks


SKIP_KEYS = {"slug", "url", "img", "image", "date", "ref", "id", "verified", "href", "src", "alt_src", "path", "tag", "tags", "kind", "type", "color", "icon", "class", "key", "source_url", "link"}


def blocks_from_json(raw: str) -> list[Block]:
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    out: list[Block] = []

    def walk(o, key=""):
        if isinstance(o, str):
            s = o
            if "<" in s:
                s = re.sub(r"<[^>]+>", "", s)
            s = clean_space(s)
            if len(s) >= 4 and re.search(rf"[{JP}]", s) and not re.match(r"^(https?:|/)", s):
                probe = json.dumps(o, ensure_ascii=False)[1:-1]
                i = raw.find(probe[:60])
                line = raw.count("\n", 0, i) + 1 if i >= 0 else 0
                out.append(Block("para" if len(s) > 30 or "。" in s else "label", s, line, "json"))
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in SKIP_KEYS:
                    walk(v, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, key)

    walk(data)
    return out


def blocks_from_text(raw: str) -> list[Block]:
    out = []
    for i, ln in enumerate(raw.splitlines(), 1):
        t = ln.strip()
        if not t or not re.search(rf"[{JP}]", t):
            continue
        if "✕" in t:                                     # a line that quotes a bad example (the style guide itself)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", t)
        if m:
            out.append(Block("heading", m.group(2), i, "md"))
            continue
        item = bool(re.match(r"^[-*・]\s+", t))
        t = re.sub(r"^[-*・>]\s+", "", t)
        t = re.sub(r"\*\*|`", "", t)
        out.append(Block("item" if item else "para", clean_space(t), i, "md"))
    return out


def sentences(text: str) -> list[str]:
    parts = re.findall(r"[^。！？!?]*[。！？!?]+[」』）)]*|[^。！？!?]+$", text)
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------------------------------------------------------------- rules: stock phrases and wording (a regex per sentence)
R: list[Rule] = []


def add(**kw) -> Rule:
    r = Rule(**kw)
    R.append(r)
    return r


add(id="closing_ikaga", level="high", pattern=rx(r"いかがでし(?:たでしょうか|ょうか|たか)|いかがだったでしょうか|最後までお読みいただき|最後までご覧いただき"),
    why="記事の締めの定型句。読み手に語りかける形だけで、中身がない。ブログ型のAI文章の代表的な癖。",
    fix="削る。言い残した結論や次にすることがあれば、それを一文で書いて終える。",
    bad="いかがでしたでしょうか。ぜひ参考にしてみてください。", good="(削る。または)迷ったときは、まず予算を決めると絞り込みやすくなります。")
add(id="closing_kouei", level="mid", pattern=rx(r"参考になれば幸いです|お役に立てれば幸いです|お役に立てば幸いです|参考になりましたら幸いです"),
    why="結びの定型句。どのページでも同じ形で出てくると、機械的に見える。", fix="削る。または、読んだ人が次にすること(探す・比べる・申し込む)を具体的に書く。",
    bad="この記事がお役に立てれば幸いです。", good="気になる品があれば、候補の一覧から価格を見比べてください。")
add(id="lets_go", level="high", pattern=rx(r"見ていきましょう|解説していきます|紹介していきます|探っていきましょう|掘り下げていきます|迫っていきます|解説していきましょう|詳しく見ていきます|確認していきましょう|ご紹介していきます"),
    why="読者を連れて進む導入・つなぎの定型句。内容を言う前の予告で、字数だけ増える。", fix="予告をやめて、すぐ中身に入る。",
    bad="それでは、さっそく見ていきましょう。", good="(削って、最初の項目に入る)")
add(id="intro_announce", level="mid", pattern=rx(r"(?:本記事|この記事|本稿|本ページ|このページ|ここ)では[^。]{0,70}(?:解説|説明|ご紹介|紹介|まとめ|詳しく|整理|解き明かし)(?:します|いたします|していきます|しています|してまいります|してみます)"),
    why="「これから何を書くか」を宣言する導入。見出しを読めば分かることを繰り返しているだけの場合が多い。", fix="宣言を削り、結論か一番大事な事実から書き出す。",
    bad="本記事では、母の日の贈り物の選び方について詳しく解説します。", good="母の日の贈り物は、予算より先に『相手が毎日使うもの』から絞ると選びやすくなります。")
add(id="hedge_deshou", level="high", pattern=rx(r"と言えるでしょう|といえるでしょう|と言えるのではないでしょうか|と言えそうです|ではないでしょうか|と言っても過言ではあり|と言っても過言ではない|と言えます。?$"),
    why="断定を避けて逃げる文末。書き手の判断が見えず、翻訳調にも読める。", fix="言い切れることは言い切る(「〜です」)。根拠が弱いなら「〜かもしれません」と一度だけ控えめに。",
    bad="この時期の手土産には、個包装が適していると言えるでしょう。", good="この時期の手土産は、個包装が向いています。配る手間がかからないからです。")
add(id="suggest_ka", level="mid", pattern=rx(r"してみてはいかがでしょうか|してみてはいかがですか|みてはいかがでしょう|てはいかがでしょうか"),
    why="提案をぼかす定型の言い回し。押しつけがましくも、頼りなくも聞こえる。", fix="「〜がおすすめです」「〜するとよいです」と、理由を添えて言い切る。",
    bad="まずは一つ試してみてはいかがでしょうか。", good="まず一つ試すのがおすすめです。小さな箱なら失敗しても困りません。")
add(id="academic_hedge", level="mid", pattern=rx(r"を示唆し|を示唆する|を意味している|ことを示している|傾向を示している|ことが示されている|ことが知られている|ことが確認されている|ことが明らかになっている|留意が必要|留意する必要|考慮する必要がある|点に留意"),
    why="英語の論文を直訳したような言い回し(indicates / suggests)。AIが論文を大量に学習した癖で、硬くて回りくどい。", fix="確かさに合わせて「〜でしょう」「〜かもしれません」「〜と思われます」に。事実なら「〜です」と言い切る。",
    bad="この結果は需要が高まっていることを示唆しています。", good="需要は高まっていそうです。")
add(id="hooks_empathy", level="mid", pattern=rx(r"こんなお悩み|お悩みではありませんか|お悩みの方|そんな(?:あなた|方|時)に|お気持ち(?:は)?(?:よく)?(?:わかり|分かり)ます|あなたも[^。]{0,15}ませんか|ありませんか[?？]"),
    why="読者の悩みを先回りして言い当てる導入。どのページでも同じ形で、型に当てはめた印象になる。", fix="読者の状況を、具体的な場面一つで書く(いつ・誰に・何に困るか)。",
    bad="贈り物選びでこんなお悩みはありませんか?", good="来週の金曜までに、取引先へ手土産を用意しなければならない。そんなときの選び方です。")
add(id="opening_kinnen", level="mid", pattern=rx(r"^(?:近年|昨今|現代社会|現代において|今日では)[、,][^。]{0,60}(?:注目|求められ|高まっ|増えて|広がっ|重要)"),
    why="一般論から始める導入の定型。誰にでも当てはまり、そのページ固有の事実がない。", fix="そのページで扱う具体的な事実(日付・数字・出来事)から始める。",
    bad="近年、ギフト市場への注目が高まっています。", good="楽天市場の母の日ランキングでは、今年も花より食品が上位に並びました。")
add(id="importance", level="low", pattern=rx(r"(?:重要|大切|不可欠)(?:です|となります|になります|といえます|と言えます)"), min_per_page=3,
    why="「重要です」は何が・どう重要かを言わずに済ませる万能の締め。ページに何度も出ると中身が薄く見える。", fix="なぜ大事かを、結果や数字で書く(「これを忘れると〜」「〜日までに必要です」)。",
    bad="期限を確認することが重要です。", good="受付は12月20日までです。過ぎると年内に届きません。")
add(id="koto_ga_dekiru", level="low", pattern=rx(r"することができ(?:ます|る|ません|ました|ない)"), min_per_page=2,
    why="「することができます」は「できます」で足りる。冗長で、翻訳調。", fix="「〜できます」「〜れます」(例: 注文することができます→注文できます)。",
    bad="商品は会員登録なしで購入することができます。", good="商品は会員登録なしで購入できます。")
add(id="ga_kanou", level="low", pattern=rx(r"(?:することが|が)可能(?:です|となります|になります|で)"), min_per_page=2,
    why="「可能です」は硬い書き言葉。機械的な文章に多い。", fix="「できます」に。",
    bad="期間中は何度でも変更が可能です。", good="期間中は何度でも変更できます。")
add(id="ni_oite", level="low", pattern=rx(r"において|における"), min_per_page=2,
    why="「において」「における」は法令文の硬さ。説明文で重なると、名詞ばかりの重い文になる。", fix="「で」「の」「では」に。(例: 日本における最低賃金→日本の最低賃金)",
    bad="関東地方における出没状況において、増加が見られます。", good="関東地方の出没状況では、増えています。")
add(id="sahen_okonau", level="low", pattern=rx(rf"[{KANJI}]{{2,}}を(?:行い|行う|行っ|行わ)"), min_per_page=3,
    why="「検討を行う」「確認を行う」のように、名詞+「を行う」にすると動詞が弱くなり、文が重くなる。", fix="名詞を動詞に戻す(検討を行う→検討する、確認を行います→確認します)。",
    bad="毎朝データの更新を行っています。", good="毎朝データを更新しています。")
add(id="expected_required", level="low", pattern=rx(r"が(?:求められ|期待され|必要とされ)(?:ます|る|ている|ています)|することが(?:期待|求め)"),
    why="誰が求めるのか分からない受け身。責任の所在を消す、かたい言い方。", fix="主語を出して能動に。誰かにしてほしいことは「〜してください」。",
    bad="利用前に規約の確認が求められます。", good="利用前に規約を読んでください。")
add(id="double_keigo", level="mid", pattern=rx(r"になられ|おっしゃられ|おられ(?:ます|る)|拝見させて|召し上がりになられ|お越しくださいませ|ご覧くださいませ"),
    why="二重敬語、または過剰な敬語。かえって不自然に聞こえる。", fix="敬語は一つにする(お越しになられる→お越しになる、拝見させていただく→拝見する)。",
    bad="商品をご覧になられた方は、こちらへお進みください。", good="商品をご覧になった方は、こちらへお進みください。")
add(id="sasete_itadaku", level="low", pattern=rx(r"させていただ(?:き|く|け|いて)"), min_per_page=2,
    why="「させていただく」は、許可を得る場面以外で重なると、へりくだりすぎて不自然になる。", fix="「します」「いたします」に。",
    bad="毎日更新させていただいております。", good="毎日更新しています。")
add(id="toiu_hearsay", level="low", pattern=rx(r"と(?:言われ|考えられ|されて|思われ)(?:ています|ている|ます)"), min_per_page=3,
    why="誰が言っているのか不明な伝聞が重なると、根拠のない断定を避けているように見える。", fix="出典を書くか、書き手自身の判断として言い切る。",
    bad="この時期は混雑すると言われています。", good="昨年は12月10日を過ぎると到着が1週間遅れました(店舗の案内による)。")
add(id="hedge_density", level="mid", min_ratio=0.2, pattern=rx(r"場合があります|可能性があります|ことがあります|かもしれません|とは限りません|一概には|人によって(?:異なり|違い)|ケースバイケース|場合によっては|状況によって(?:異なり|変わり)"), min_per_page=4,
    why="あらゆる方向に保険をかけると、結局何も言っていない文になる(全方位への配慮)。", fix="例外は本当に大事なものだけ残す。条件がはっきりしているなら、条件を書く(「〜の場合は〜」)。",
    bad="商品によっては、場合によっては、到着が遅れる可能性があります。", good="離島への配送は、通常より2日ほどかかります。")
add(id="vague_words", level="low", pattern=rx(r"サポート|最適化|シームレス|包括的|多角的|効果的|効率的|総合的|様々な|さまざまな|幅広い|数多くの|多彩な|魅力的|充実した"), min_per_page=4,
    why="何にでも使える抽象語。具体的な中身を言わずに済ませてしまう。", fix="数・名前・条件に置き換える(「幅広い」→「3,000点」、「サポート」→「電話で受け付けます」)。",
    bad="さまざまなシーンで活用できる、幅広いラインアップです。", good="職場への手土産から実家への贈り物まで、3,000円〜1万円の品を揃えています。")
add(id="flowery", level="mid", pattern=rx(r"寄り添[いうえっ]|彩[りるっ]|そっと|ひとときを|特別な(?:時間|ひととき)|想いを(?:届け|伝え)|心温まる|心躍る|ワクワク|わくわく|ドキドキ|どきどき|無限の可能性|新たな一歩|奥深い|魅力に(?:迫|触れ)|かけがえのない|心を込めて|ぬくもり|温もり|ときめき"),
    why="情緒的な飾りことば。どのAI文章にも出てくる決まり文句で、読み手の実感とは結びつかない。", fix="感情をほめる語をやめ、物や場面の事実を書く(素材・大きさ・使う場面・注意点)。",
    bad="大切な方の毎日にそっと寄り添う、心温まるギフトです。", good="毎朝のコーヒーに使える、容量300mlの保温マグです。")
add(id="not_only", level="low", pattern=rx(r"だけでなく[^。]{0,40}も|のみならず"), min_per_page=2,
    why="「〜だけでなく〜も」は、AIが両方を持ち上げるときの型。重なると、何が一番言いたいのかが見えなくなる。", fix="本当に言いたい側だけを書く。",
    bad="見た目だけでなく、使い心地も優れています。", good="持ち手が太く、片手で注げます。")
add(id="this_way", level="low", pattern=rx(r"^このように[、,]"), min_per_page=2,
    why="「このように、」でまとめ直す癖。直前を言い換えるだけの段落末が増える。", fix="言い換えの一文を削る。",
    bad="このように、さまざまな選び方があります。", good="(削る)")
add(id="exclaim", level="low", pattern=rx(r"。.*[!！][^!！]*[!！]|[!！][^!！]*[!！].*。"), scope="block", min_per_page=1,
    why="一つの段落に感嘆符が重なると、大げさで幼い印象になる。", fix="事実を書いて、感嘆符は使わない。または一つだけ。",
    bad="今月の売れ筋です。人気です！おすすめです！今すぐチェック！", good="今月の売れ筋です。価格を比べて選べます。")
add(id="emoji", level="mid", pattern=rx("[\U0001F300-\U0001FAFF\u2728\u2757\u203C\u2705\u274C\u2B50]"), scope="any",
    why="絵文字は、AI文章と宣伝文の定番。おとなの読者には軽く見える。", fix="削る。強調したいときは文の置き方で示す。",
    bad="おすすめです✨", good="おすすめです。")
add(id="child_tone", level="mid", off_sites=("atomou",),
    pattern=rx(r"て(?:ね|くださいね)[。！!]?$|(?:ます|です)よね[。！!]|だよ(?:[。！!]|$)|だね[。！!]|してみよう|ちゃいます|ちゃう[。！!]"),
    why="子どもに話しかける口調。おとなの読者を想定するサイトでは、幼く見える。", fix="「です・ます」の説明文に。「〜してね」→「〜してください」。",
    bad="好きなイラストを見つけてね。", good="好きなイラストを探せます。")
add(id="md_leftover", level="high", pattern=rx(r"\*\*[^*]+\*\*|^#{1,6}\s|```|\]\(https?://"), scope="any",
    why="Markdownの記号が本文に残っている。AIの出力をそのまま貼ったときに出る。", fix="記号を取り、見出しはHTMLの見出しにする。", bad="**重要**です", good="重要です")
add(id="dash_heavy", level="low", pattern=rx(r"[—―─]{1,2}"), min_per_page=4,
    why="長いダッシュの多用は、翻訳調・AI調の目印。", fix="読点か、文を分ける。", bad="それは——驚くべきことに——無料です。", good="それは無料です。意外かもしれません。")
add(id="conclusion_heading", level="low", pattern=rx(r"^(?:まとめ|結論|結論として|おわりに|最後に|総括|最後に)$"), scope="heading",
    why="「まとめ」「結論」の見出しは、どの記事にも付ける型。本文を繰り返すだけのまとめになりやすい。", fix="まとめを書くなら、見出しに中身を入れる(「迷ったらこの3つ」)。短い記事なら付けない。",
    bad="見出し: まとめ", good="見出し: 迷ったらこの3品から")
add(id="first_next_last", level="low", pattern=rx(r"(?:まず|はじめに|最初に)[、,][^。]*。.*?(?:次に|つぎに)[、,][^。]*。.*?(?:最後に|そして)[、,]"), scope="block",
    why="「まず・次に・最後に」を機械的に並べる展開。小論文の型で、手順でない説明では不自然。", fix="手順なら番号つきの一覧に。手順でなければ、大事な順に並べて接続語を減らす。",
    bad="まず、予算を決めます。次に、相手を考えます。最後に、日付を確認します。", good="予算と相手を決めたら、届く日だけ確認してください。")
add(id="ordinal_dai", level="low", pattern=rx(r"第[一二三1-3]に[、,]"), min_per_page=2,
    why="「第一に、第二に」の列挙は、論文・小論文の型。web の説明には硬い。", fix="見出しか箇条書きにする。", bad="第一に、価格です。第二に、量です。", good="価格と量を見比べてください。")

# --------------------------------------------------------------------------------------------------------------------------------- rules: structure (a function over a block)
SENT_END = re.compile(r"[。！？!?]+[」』）)]*$")


def _end3(s: str) -> str:
    t = SENT_END.sub("", s)
    return t[-3:]


LINK_SEP = re.compile(r" [/|｜] |　[/|｜]　")


def is_item_run(s: str) -> bool:
    """A run of items, not a sentence: links or names joined by " / " " | " "・", "label: A、B、C…", a date-log entry's list.  Length is not a problem there."""
    n = len(re.sub(r"\s+", "", s))
    if len(LINK_SEP.findall(s)) >= 2 and not s.endswith("。"):                 # a table of contents made of links
        return True
    if s.count("・") >= 6:
        return True
    commas = s.count("、")
    if commas >= 5 and n / (commas + 1) <= 15:
        return True
    return bool(re.match(r"^[^:：。]{1,20}[:：]\s*", s) and commas >= 2)        # "1月3日にある日付: A、B、C…など4件。"


def prose_length(s: str) -> int:
    """Characters that count toward a long sentence: a quoted title or name is one unit, and a log entry's date prefix is not text."""
    s = re.sub(r"^\d{4}年\d{1,2}月\d{1,2}日[:：]\s*", "", s)
    s = re.sub(r"[「『][^」』]*[」』]", "「」", s)
    return len(re.sub(r"\s+", "", s))


def f_long(block: Block, sents: list[str], prof: dict) -> list[str]:
    out = []
    if block.kind not in ("para", "item", "meta"):
        return out
    for s in sents:
        if prose_length(s) > prof["long"] and not is_item_run(s) and not s.startswith(("参考", "出典")) and s.count("「") < 3 and (SENT_END.search(s) or block.kind == "para"):         # a long label without a full stop is a product name or a title, not prose
            out.append(s)
    return out


def _runs(sents: list[str], width: int, need: int) -> list[str]:
    out, run = [], 1
    for i in range(1, len(sents)):
        a, b = SENT_END.sub("", sents[i - 1]), SENT_END.sub("", sents[i])
        run = run + 1 if len(b) >= width and a[-width:] == b[-width:] else 1
        if run == need:
            out.append("".join(sents[i - need + 1:i + 1]))
    return out


def f_monotone(block: Block, sents: list[str], prof: dict) -> list[str]:
    """Four sentences in a row that end with the same three letters (できます。できます。…) in one paragraph."""
    return _runs(sents, 3, 4) if block.kind == "para" else []


def f_polite_run(block: Block, sents: list[str], prof: dict) -> list[str]:
    """Six sentences in a row that all end in です/ます."""
    return _runs(sents, 2, 6) if block.kind == "para" else []


def f_taigen(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind != "para" or len(sents) < 3:
        return []
    out, run = [], 0
    for i, s in enumerate(sents):
        t = SENT_END.sub("", s)
        if len(t) <= 26 and re.search(rf"[{KANJI}ァ-ヶー0-9%％円]$", t) and s.endswith("。"):
            run += 1
            if run == 4:
                out.append("".join(sents[i - 3:i + 1]))
        else:
            run = 0
    return out


CASE_END = ("を", "に", "へ", "と", "や", "の", "も")      # not で: "件で、" is a clause ending, not a case particle


def f_comma(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind not in ("para", "item", "meta"):
        return []
    out = []
    for s in sents:
        if "、" not in s or len(s) < 12:
            continue
        segs = re.split(r"、", SENT_END.sub("", s))
        bad = 0
        for i in range(len(segs) - 1):
            seg, nxt = segs[i], segs[i + 1]
            if seg.endswith(("ても", "でも")):
                continue
            particle = seg.endswith(CASE_END) and len(seg) >= 2 and (not seg.endswith("と") or re.search(rf"[{KANJI}ァ-ヶー]と$", seg))       # ...ていると、 is a condition, not a case particle
            short_te = seg.endswith(("して", "って", "んで", "いて", "きて")) and 4 <= len(seg) <= 8 and len(s) <= 36 and len(segs) <= 3
            if (particle or short_te) and 0 < len(nxt) <= 14:
                bad += 1
        if bad >= 2 or (bad >= 1 and len(s) <= 36):
            out.append(s)
    return out


STOP_TOKENS = {"更新", "公表", "令和", "件数", "場合", "商品", "こちら", "ページ", "情報", "それぞれ", "以下", "以上", "今回", "ほか", "一覧", "対応", "表示", "確認", "利用", "設定", "必要", "可能", "ください", "ありません", "あります"}
TOKEN = re.compile(rf"[{KANJI}]{{2,}}|[ァ-ヴー]{{3,}}")


def f_repeat(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind not in ("para", "item", "meta"):
        return []
    core = set(prof["core"])
    out = []
    for s in sents:
        c = Counter(t for t in TOKEN.findall(s) if t not in STOP_TOKENS and not any(t in k or k in t for k in core))
        if any(n >= 3 for n in c.values()):
            out.append(s)
    return out


def f_stutter(block: Block, sents: list[str], prof: dict) -> list[str]:
    core = set(prof["core"])
    out = []
    for s in sents:
        for m in re.finditer(rf"([{KANJI}ァ-ヴー]{{3,}})[はがをにでともの]{{1,2}}\1(?![ァ-ヴー])", s):
            if m.group(1) not in core:
                out.append(s)
                break
    return out


def f_noun_chain(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind not in ("para", "item", "meta"):
        return []
    out = []
    for s in sents:
        if not s.endswith("。"):                                    # labels and glued menu items are not prose
            continue
        s = re.sub(r"[「『][^」』]*[」』]", "「」", s)                  # a quoted proper name is what it is
        if re.search(rf"[{KANJI}]{{11,}}", s) or (len(re.findall("の", s)) >= 6 and len(s) <= 70):
            out.append(s)
    return out


def f_same_start(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind != "para" or len(sents) < 3:
        return []
    out, run = [], 1
    for i in range(1, len(sents)):
        a, b = sents[i - 1][:3], sents[i][:3]
        run = run + 1 if a == b and re.match(rf"[{JP}]{{3}}", a) else 1
        if run == 3:
            out.append("".join(sents[i - 2:i + 1]))
    return out


def f_hiragana(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind != "para" or not prof["hira"]:
        return []
    t = block.text
    jp = re.findall(rf"[{JP}]", t)
    if len(jp) < 50:
        return []
    hira = sum(1 for c in jp if "ぁ" <= c <= "ん")
    return [t] if hira / len(jp) > prof["hira"] else []


def f_spaced(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind != "para" or "。" not in block.text:                  # product names and labels legitimately carry spaces
        return []
    n = len(re.findall(rf"[ぁ-ん] [ぁ-ん{KANJI}ァ-ヶ]|[{KANJI}ァ-ヶ] [ぁ-ん]", block.text))        # a space next to hiragana; kanji + kanji is a proper name (東京大学 医学部)
    return [block.text] if n >= 2 else []


def f_list3(block: Block, sents: list[str], prof: dict) -> list[str]:
    if block.kind != "para":
        return []
    return [m.group(0) for m in re.finditer(r"[^、。]{1,12}、[^、。]{1,12}、[^、。]{1,12}(?:など|といった|をはじめ)", block.text)]


for rid, lvl, fn, why, fix, bad, good, mpp in [
    ("long_sentence", "mid", f_long, "一文が長いと、主語と述語が離れて読みにくい。AIは文をつなげて長くする癖がある。(二段階: 規定の長さ超=mid、さらに長い=highに格上げ)", "二つに切る。つなぎの「〜であり、〜で、〜が」を句点に。主語と動詞を近づける。",
     "楽天市場のランキングをもとにしながら、ジャンル別・世代別に売れている商品を毎日自動で更新して、贈る相手や予算に合わせて探せるようにしていて、さらに価格の変化もすぐ確かめられるようにしています。", "楽天市場のランキングをもとに、売れている商品を毎日更新しています。ジャンルや世代、予算で絞り込めます。", 1),
    ("monotone_ending", "mid", f_monotone, "同じ文末(〜できます。〜できます。…)が4文以上(です/ますだけなら6文以上)続くと、単調で機械的に聞こえる。", "文末を変える。言い切り・体言・問いかけを混ぜるより、文の順序や主語を入れ替えるほうが自然。",
     "画像を保存できます。一覧を印刷できます。設定を変更できます。履歴を確認できます。", "画像は保存でき、一覧は印刷もできます。設定の変更と履歴の確認もここからです。", 1),
    ("polite_run", "low", f_polite_run, "六文続けて「〜ます。」「〜です。」で終わる。文末の形がそろい、一本調子に読める(丁寧な文章では自然に起きるので、弱い目印)。", "文の順序を入れ替える。理由を先に置く、条件を前に出す、短く言い切る文を混ぜる。",
     "選びます。確かめます。見直します。伝えます。整えます。添えます。", "まず予算を決め、相手の好みを確かめる。日付が近いなら早めに手配する。短い一言を添えれば十分です。", 1),
    ("taigen_run", "low", f_taigen, "体言止めの短文が4つ以上続く。キャッチコピー調で、中身が薄く見える。", "一文にまとめ、動詞で終える。", "毎日更新。ジャンル別。価格順。全638点。", "ジャンル別に全638点を載せ、毎日更新します。価格順にも並べられます。", 1),
    ("comma_particle", "low", f_comma, "短い語句ごとに読点を打つと、息継ぎだらけで幼い文になる。(読点は意味の切れ目だけ。yorokobu は commas.py が担当)", "助詞のあとの読点を取る。長い文は、読点を足さずに文を分ける。",
     "ダウンロードして、すぐに使えます。クレジット表示も、点数の制限も、ありません。", "ダウンロードしてすぐに使えます。クレジット表示も点数の制限もありません。", 1),
    ("word_repeat", "low", f_repeat, "同じ語が一文に3回以上。言い換えるか、省けるのに繰り返している。", "二回目以降を「それ」「この」に、または省く。", "素材を探すとき、素材の名前や素材の種類で素材を絞り込みます。", "素材を探すときは、名前や種類で絞り込みます。", 1),
    ("word_stutter", "low", f_stutter, "「AのA」のように、同じ語が助詞をはさんで続く。", "どちらかを削るか、言い換える。", "贈るプレゼントのプレゼント選び", "贈り物の選び方", 1),
    ("noun_chain", "low", f_noun_chain, "漢字の名詞を11字以上つなぐ、または「AのBのCのD」と「の」をつなぐ。意味の切れ目が見えず、読みにくい。", "動詞を使って分ける。「の」を「で」「を」に。",
     "全国最低賃金改定状況推移確認表を掲載しています。", "全国の最低賃金がどう変わったかを一覧にしています。", 1),
    ("same_start", "low", f_same_start, "三文続けて同じ書き出し(この商品は〜。この商品は〜。)。リズムが単調。", "主語を省くか、順序を変える。", "この品は軽いです。この品は丈夫です。この品は安いです。", "軽くて丈夫で、価格も抑えめです。", 1),
    ("hiragana_heavy", "mid", f_hiragana, "ひらがなの割合が高い段落。読みにくく、幼い印象になる(漢字にできる語は漢字に)。", "漢字にできる語は漢字に(補助動詞・形式名詞・接続語はひらがなのままでよい)。",
     "しぼりこんで、すきなものをえらべるようになっています。", "絞り込んで、好きな物を選べます。", 1),
    ("spaced_writing", "mid", f_spaced, "日本語の語の間に空白(分かち書き)がある。読みやすさのためのつもりでも、おとなの文章としては不自然。", "空白を取り、漢字とかなの区別で読ませる。", "あと 何日 で 来るか 調べる", "あと何日で来るか調べる", 1),
    ("list3", "low", f_list3, "「A、B、Cなど」の三点列挙。AIはなんでも三つ並べる癖がある。ページに重なると、中身を選んでいない印象になる。", "一番大事な一つか二つに絞る。残りは削る。",
     "仕事、家族、友人といった場面で…", "仕事の場面では…", 4),
]:
    add(id=rid, level=lvl, fn=fn, why=why, fix=fix, bad=bad, good=good, min_per_page=mpp, scope="block")

# Heading shape is checked over the whole page, not per block (see check_blocks): four or more headings that end alike are a template.
add(id="heading_template", level="low", fn=None, scope="page",
    why="見出しが同じ語尾でそろう(〜のポイント、〜のコツ、〜について)。機械的に作った構成に見える。", fix="見出しを内容で書き分ける。結論を見出しに入れる。",
    bad="見出し: 選び方のポイント/予算のポイント/包装のポイント/日付のポイント", good="見出し: 予算は3,000円から/包装は店に頼む/日付は1週間前に")

add(id="pet_verb", level="mid", fn=None, scope="page",
    why="同じ「万能の動詞・形容」が一ページに3回以上(整える・押さえる・見極める・無理なく・扱いやすい・寄り添う)。AIが具体的な動作の代わりに使う口ぐせで、読むとぼんやりする。",
    fix="何をするのかを具体的な動作に置き換える(「相手の家や職場で無理なく扱える形に整える」→「冷蔵庫に入る大きさにする」)。同じ語は一度だけ残す。",
    bad="時期、量、保存性を整え、無理なく扱える形に整えます。", good="7月上旬に届くよう、冷蔵庫に入る大きさの品を手配します。")
add(id="pet_abstract", level="low", fn=None, scope="page",
    why="同じ抽象語が一ページに5回以上(負担・安心・自然な・丁寧に・気持ち・印象・目安・控えめ・気をつかう・〜しやすい)。便利な語だが、重なると中身が見えない。",
    fix="具体的な場面・数字・条件に言い換える。同じ語は多くて2回。", bad="負担にならず、安心して、自然に渡せます。", good="1,000円以内なので、お返しに気を使わせません。")
PET_VERB = {"整える": r"整(?:え|い|う)", "押さえる": r"押さえ", "見極める": r"見極め", "無理なく": r"無理(?:なく|のない)", "扱いやすい": r"扱い(?:やす|にく)", "寄り添う": r"寄り添"}
PET_ABSTRACT = {"負担": r"負担", "安心": r"安心", "自然": r"自然(?:な|に)", "丁寧": r"丁寧(?:な|に)", "気持ち": r"気持ち", "印象": r"印象", "目安": r"目安", "控えめ": r"控えめ", "気をつかう": r"気(?:を)?(?:つか|づか|遣|使)",
                "しやすい": r"(?:選び|使い|渡し|食べ|持ち運び|探し|比べ|読み|分け)(?:やす|にく)い"}


def check_pets(blocks: list[Block], path: str, rule_id: str, words: dict[str, str], need: int) -> list[Hit]:
    out: list[Hit] = []
    found: dict[str, list[Hit]] = defaultdict(list)
    for b in blocks:
        if b.quoted or b.kind in ("heading", "meta") or (b.kind in ("label", "item") and not SENT_END.search(b.text)):
            continue
        for sent in sentences(mask_quotes(b.text)) or [b.text]:
            for name, pat in words.items():
                if re.search(pat, sent):
                    found[name].append(Hit(path, b.line, rule_id, RULES[rule_id].level, sent if len(sent) <= 110 else sent[:107] + "…"))
    for name, lst in found.items():
        uniq = {h.sentence: h for h in lst}
        if len(lst) >= need:
            for h in list(uniq.values())[:3]:
                h.note = f"「{name}」がこのページに{len(lst)}回"
                out.append(h)
    return out


TEMPLATE_END = re.compile(r"(?:のポイント|のコツ|について|とは[?？]?|の方法|のやり方|の理由|の注意点|のメリット|のデメリット|の選び方|のおすすめ|の特徴|の違い)$")
RULES: dict[str, Rule] = {r.id: r for r in R}
LONG_HIGH = "long_sentence"

# Promotion to a publish gate: add the rule ids a site's real text passes with no false positive.  Empty = everything is a warning (report only).  Agree changes with the report desk.
GATE: dict[str, set[str]] = {s: set() for s in SITES}


def rule_active(r: Rule, site: str | None, prof: dict) -> bool:
    if r.id in prof["skip"]:
        return False
    if r.sites is not None and site not in r.sites:
        return False
    return site not in r.off_sites


# --------------------------------------------------------------------------------------------------------------------------------- the check
_sent_cache: dict[tuple, list[tuple[str, str]]] = {}


def _sentence_hits(kind: str, sent: str, site: str | None, prof: dict) -> list[tuple[str, str]]:
    key = (kind, sent, site)
    got = _sent_cache.get(key)
    if got is not None:
        return got
    out = []
    for r in R:
        if r.pattern is None or r.scope in ("block", "page", "any") or not rule_active(r, site, prof):
            continue
        if r.scope == "heading" and kind != "heading":
            continue
        if r.scope == "body" and kind == "heading":
            continue
        if kind in ("label", "item") and not SENT_END.search(sent) and r.scope == "body":     # a label, a button or a product name is not prose
            continue
        if r.pattern.search(sent):
            out.append((r.id, sent))
    if len(_sent_cache) > 200000:
        _sent_cache.clear()
    _sent_cache[key] = out
    return out


def mask_quotes(text: str) -> str:
    return re.sub(r"[「『][^」』]{8,}[」』]", "「…」", text)


def check_blocks(blocks: list[Block], path: str, site: str | None = None, min_level: str = "low", only: Iterable[str] | None = None, md: bool = False) -> list[Hit]:
    prof = profile(site)
    only = set(only or ())
    exempt = bool(EXEMPT_PATH.search(path))
    hits: list[Hit] = []
    per_rule: dict[str, list[Hit]] = defaultdict(list)

    def want(r: Rule) -> bool:
        if only and r.id not in only:
            return False
        if LEVEL_RANK[r.level] < LEVEL_RANK[min_level] and r.id != LONG_HIGH:         # a long sentence is mid, or high when it is very long: filtered per hit below
            return False
        if exempt and r.id != "md_leftover":
            return False
        pat = prof.get("path_skip", {}).get(r.id)
        return not (pat and re.search(pat, path))

    def record(rule: Rule, block: Block, sent: str, level: str | None = None):
        per_rule[rule.id].append(Hit(path, block.line, rule.id, level or rule.level, sent if len(sent) <= 110 else sent[:107] + "…"))

    for orig in blocks:
        # a long quoted example (a greeting, a sample sentence) is not the writer's own prose: its words are not judged; a blockquote is not judged at all
        b = Block(orig.kind, mask_quotes(orig.text), orig.line, orig.src, orig.quoted)
        sents = sentences(b.text) or [b.text]
        # regex rules per sentence
        for s in sents:
            for rid, _ in ([] if orig.quoted else _sentence_hits(b.kind, s, site, prof)):
                r = RULES[rid]
                if r.scope == "body" and b.kind == "heading":
                    continue
                if rid == "md_leftover" and b.src == "md":
                    continue
                if want(r):
                    record(r, b, s)
        for r in R:
            if not want(r) or not rule_active(r, site, prof):
                continue
            if r.scope == "any":
                if r.pattern.search(orig.text) and not (r.id == "md_leftover" and orig.src == "md"):
                    record(r, orig, orig.text)
            elif orig.quoted:
                continue
            elif r.pattern is not None and r.scope == "block":
                if r.pattern.search(b.text):
                    record(r, b, b.text)
            elif r.fn is not None:
                for ex in r.fn(b, sents, prof):
                    level = "high" if r.id == LONG_HIGH and prose_length(ex) > prof["very_long"] else None
                    record(r, b, ex, level)
    if not exempt:
        for rid, words, need in (("pet_verb", PET_VERB, 3), ("pet_abstract", PET_ABSTRACT, 5)):
            r = RULES[rid]
            if (not only or rid in only) and rule_active(r, site, prof) and LEVEL_RANK[r.level] >= LEVEL_RANK[min_level] and want(r):
                hits += check_pets(blocks, path, rid, words, need)
    # heading template: four or more headings (h2/h3) that end with the same 3+ letters
    if (not only or "heading_template" in only) and not exempt and rule_active(RULES["heading_template"], site, prof) and LEVEL_RANK["low"] >= LEVEL_RANK[min_level]:
        heads = [b for b in blocks if b.kind == "heading" and len(b.text) >= 6]
        ends = Counter(m.group(0) for h in heads if (m := TEMPLATE_END.search(h.text)))
        for end, n in ends.items():
            if n >= 4:
                first = next(h for h in heads if h.text.endswith(end))
                per_rule["heading_template"].append(Hit(path, first.line, "heading_template", "low", f"…{end}（{n}本の見出しが同じ終わり方）: {first.text[:60]}"))
    n_sent = max(1, sum(len(sentences(b.text) or [b.text]) for b in blocks if b.kind != "heading"))
    for rid, lst in per_rule.items():
        r = RULES[rid]
        if len(lst) < r.min_per_page or len(lst) / n_sent < r.min_ratio:
            continue
        note = f"このページに{len(lst)}件" if len(lst) > 1 else ""
        for h in lst[:3 if r.min_per_page > 1 else 50]:
            h.note = note
            hits.append(h)
    hits = [h for h in hits if LEVEL_RANK[h.level] >= LEVEL_RANK[min_level]]
    hits.sort(key=lambda h: (h.line, h.rule))
    return hits


def check_file(path: Path, site: str | None, rel: str | None = None, **kw) -> list[Hit]:
    ext = path.suffix.lower()
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if ext in (".html", ".htm"):
        blocks = blocks_from_html(raw)
    elif ext == ".json":
        blocks = blocks_from_json(raw)
    elif ext in (".md", ".txt"):
        blocks = blocks_from_text(raw)
    else:
        return []
    return check_blocks(blocks, rel or str(path), site, **kw)


def check_text(text: str, site: str | None = None, path: str = "<text>", **kw) -> list[Hit]:
    """Plain text (one paragraph per line)."""
    blocks = [Block("para", ln.strip(), i, "txt") for i, ln in enumerate(text.splitlines(), 1) if ln.strip()]
    return check_blocks(blocks, path, site, **kw)


def walk_files(root: Path, exts: tuple[str, ...]) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts and not any(part in ("node_modules", "__pycache__", ".git") for part in p.parts):
            yield p


def check_path(root: Path, site: str | None, exts: tuple[str, ...] = (".html", ".htm"), **kw) -> tuple[list[Hit], int]:
    hits: list[Hit] = []
    n = 0
    base = root if root.is_dir() else root.parent
    for f in walk_files(root, exts):
        n += 1
        hits += check_file(f, site, rel=str(f.relative_to(base)).replace("\\", "/"), **kw)
    return hits, n


# --------------------------------------------------------------------------------------------------------------------------------- sites: where the published text is
BUILD_ARGS = {"saichin": ["--release"], "kuma": ["--release"], "minna": ["--release"], "atomou": ["--release"], "yorokobu": []}


def site_of(path: Path) -> str | None:
    parts = [p.lower() for p in path.resolve().parts]
    for s in SITES:
        if s in parts:
            return s
    return None


def built_dir(site: str, rebuild: bool = False, base: Path | None = None) -> Path:
    out = (base or ROOT / "out" / "naturaljp") / site
    if rebuild or not (out / "index.html").exists():
        cmd = [sys.executable, str(ROOT / "sites" / site / "build.py"), *BUILD_ARGS[site], "--out", str(out)]
        if site == "yorokobu":                      # the products come from the Rakuten fetch (not in the repo); an older fetch is enough to read the editors' text
            for name in ("yorokobu_items.json", "yorokobu_items_big2.json", "yorokobu_items_big.json", "yorokobu_items_cand.json", "yorokobu_items_sample.json"):
                if (ROOT / "out" / name).exists():
                    cmd += ["--items", str(ROOT / "out" / name)] + (["--release"] if name == "yorokobu_items.json" else [])
                    break
        print(f"building {site} → {out}", file=sys.stderr)
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not (out / "index.html").exists():
            raise SystemExit(f"build of {site} failed (no built folder to read): {(r.stdout + r.stderr)[-400:]}")
    return out


def source_dir(site: str) -> Path:
    return ROOT / "sites" / site / "content"


# --------------------------------------------------------------------------------------------------------------------------------- reports
def summarize(hits: list[Hit]) -> dict:
    uniq: dict[tuple[str, str], set[str]] = defaultdict(set)
    for h in hits:
        uniq[(h.rule, h.sentence)].add(h.path)
    by_rule: dict[str, dict] = {}
    for (rule, sent), paths in uniq.items():
        d = by_rule.setdefault(rule, {"unique": 0, "occurrences": 0, "examples": []})
        d["unique"] += 1
        d["occurrences"] += len(paths)
        d["examples"].append((len(paths), sent, sorted(paths)[0]))
    for d in by_rule.values():
        d["examples"].sort(key=lambda x: (-x[0], x[1]))
    return by_rule


def levels_of(hits: list[Hit]) -> Counter:
    return Counter(h.level for h in {(h.rule, h.sentence): h for h in hits}.values())


def format_hits(hits: list[Hit], limit: int = 60, verbose: bool = False) -> str:
    groups: dict[tuple[str, str], list[Hit]] = defaultdict(list)
    for h in hits:
        groups[(h.rule, h.sentence)].append(h)
    rows = sorted(groups.values(), key=lambda g: (-LEVEL_RANK[g[0].level], g[0].rule, g[0].path, g[0].line))
    lines = []
    for g in rows[:limit]:
        h = g[0]
        more = f"  （ほか{len({x.path for x in g}) - 1}ページにも）" if len({x.path for x in g}) > 1 else ""
        lines.append(f"{h.path}:{h.line}  [{h.level}] {h.rule}  「{h.sentence}」{('  ' + h.note) if h.note else ''}{more}")
        if verbose:
            r = RULES[h.rule]
            lines.append(f"    なぜ: {r.why}\n    直し方: {r.fix}")
    if len(rows) > limit:
        lines.append(f"… ほか {len(rows) - limit} 件(--limit で増やす)")
    return "\n".join(lines)


def format_summary(hits: list[Hit], pages: int | None = None) -> str:
    s = summarize(hits)
    lv = levels_of(hits)
    lines = [f"件数(重複する同じ文は1件): high {lv['high']} / mid {lv['mid']} / low {lv['low']}" + (f"   読んだページ: {pages}" if pages is not None else "")]
    for rid, d in sorted(s.items(), key=lambda kv: (-LEVEL_RANK[RULES[kv[0]].level], -kv[1]["unique"])):
        r = RULES[rid]
        lines.append(f"  [{r.level}] {rid}: {d['unique']}件({d['occurrences']}か所)  — 直し方: {r.fix}")
    return "\n".join(lines)


def gate_hits(hits: list[Hit], site: str | None) -> list[Hit]:
    rules = GATE.get(site or "", set())
    return [h for h in hits if h.rule in rules]


def audit_markdown(results: dict[str, tuple[list[Hit], int]], today: str) -> str:
    out = [f"# 文章チェック(naturaljp)棚卸し {today}", "", "公開されている(ビルドした)ページの文章を `python -m sokuhou.naturaljp audit` で読んだ結果。文章は直していない。直しは各サイトの担当セッションへ。",
           "件数は『同じ文は1件』に数えた数。『か所』は同じ文が出るページの延べ数(フッターなどの共通文は1件で多数か所になる)。", ""]
    out += ["| サイト | 読んだページ | high | mid | low | 計 |", "|---|---|---|---|---|---|"]
    for site, (hits, pages) in results.items():
        lv = levels_of(hits)
        out.append(f"| {site} | {pages} | {lv['high']} | {lv['mid']} | {lv['low']} | {sum(lv.values())} |")
    for site, (hits, pages) in results.items():
        out += ["", f"## {site}", ""]
        s = summarize(hits)
        if not s:
            out.append("検出なし。")
            continue
        out += ["| 規則 | レベル | 件 | か所 | 代表例 |", "|---|---|---|---|---|"]
        for rid, d in sorted(s.items(), key=lambda kv: (-LEVEL_RANK[RULES[kv[0]].level], -kv[1]["unique"])):
            ex = " / ".join(f"{path}:「{sent[:60]}」" for n, sent, path in d["examples"][:2]).replace("|", "\\|").replace("\n", " ")
            out.append(f"| {rid} | {RULES[rid].level} | {d['unique']} | {d['occurrences']} | {ex} |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------------------------------------------- command line
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="naturaljp", description="Japanese that reads machine-made: a report (never a rewrite)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="files, folders or a site name")
    c.add_argument("targets", nargs="+")
    c.add_argument("--site", help="the style profile (default: guessed from the path)")
    c.add_argument("--source", action="store_true", help="a site name: read sites/<site>/content (json/md/txt) instead of the built pages")
    c.add_argument("--rebuild", action="store_true", help="a site name: build again before reading")
    c.add_argument("--min-level", default="low", choices=list(LEVEL_RANK))
    c.add_argument("--rule", action="append", help="only this rule id (repeatable)")
    c.add_argument("--limit", type=int, default=60)
    c.add_argument("--summary", action="store_true", help="counts per rule only")
    c.add_argument("--verbose", "-v", action="store_true", help="print why / how to fix under each hit")
    c.add_argument("--format", default="text", choices=["text", "json"])
    c.add_argument("--gate", action="store_true", help="exit 1 when a rule promoted to GATE[site] has a hit (report-only otherwise)")
    t = sub.add_parser("text", help="check a string")
    t.add_argument("text")
    t.add_argument("--site")
    t.add_argument("--min-level", default="low", choices=list(LEVEL_RANK))
    t.add_argument("-v", "--verbose", action="store_true")
    r = sub.add_parser("rules", help="list the rules")
    r.add_argument("--site")
    a = sub.add_parser("audit", help="all five sites → a markdown report")
    a.add_argument("--builds", help="a folder with one built folder per site (default: out/naturaljp, built on first use)")
    a.add_argument("--md", help="write the report here")
    a.add_argument("--sites", nargs="*", default=list(SITES))
    a.add_argument("--rebuild", action="store_true")
    a.add_argument("--date", default="")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "rules":
        prof = profile(args.site)
        for x in R:
            if args.site and not rule_active(x, args.site, prof):
                continue
            print(f"[{x.level}] {x.id}{'  (同一ページに' + str(x.min_per_page) + '回以上で報告)' if x.min_per_page > 1 else ''}\n   なぜ: {x.why}\n   直し方: {x.fix}\n   例: {x.bad}  →  {x.good}")
        return 0
    if args.cmd == "text":
        hits = check_text(args.text, args.site, min_level=args.min_level)
        print(format_hits(hits, verbose=args.verbose) or "検出なし(誤検出を含め、規則に当たる箇所はありません)")
        return 0
    if args.cmd == "audit":
        base = Path(args.builds) if args.builds else None
        results = {}
        for s in args.sites:
            d = built_dir(s, args.rebuild, base) if not (base and (base / s).exists()) else base / s
            results[s] = check_path(d, s)
            print(f"{s}: {sum(levels_of(results[s][0]).values())} findings in {results[s][1]} pages", file=sys.stderr)
        md = audit_markdown(results, args.date or "")
        if args.md:
            Path(args.md).write_text(md, encoding="utf-8")
        else:
            print(md)
        return 0

    all_hits: list[Hit] = []
    pages = 0
    gate_fail: list[Hit] = []
    for tgt in args.targets:
        site = args.site
        if tgt in SITES:
            site = site or tgt
            if args.source:
                root, exts = source_dir(tgt), (".json", ".md", ".txt")
            else:
                root, exts = built_dir(tgt, args.rebuild), (".html", ".htm")
        else:
            root = Path(tgt)
            site = site or site_of(root)
            exts = (".html", ".htm", ".json", ".md", ".txt") if root.is_file() or args.source else (".html", ".htm", ".md", ".txt")
            if not root.exists():
                print(f"not found: {tgt}", file=sys.stderr)
                return 2
        hits, n = check_path(root, site, exts, min_level=args.min_level, only=args.rule)
        pages += n
        all_hits += hits
        gate_fail += gate_hits(hits, site)
    if args.format == "json":
        print(json.dumps([h.__dict__ for h in all_hits], ensure_ascii=False, indent=1))
    else:
        if not args.summary:
            print(format_hits(all_hits, args.limit, args.verbose))
        print(format_summary(all_hits, pages))
        print("(警告です。公開は止まりません)" if not args.gate else f"(ゲート対象の規則: {sum(1 for _ in gate_fail)} 件)")
    return 1 if args.gate and gate_fail else 0


if __name__ == "__main__":
    sys.exit(main())
