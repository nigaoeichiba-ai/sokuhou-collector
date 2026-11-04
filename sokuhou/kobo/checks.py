"""Machine checks applied after writing (the writer never sees the rule list; a blocking finding goes back to the writer as a note to fix).

K01 the same ending / opening / phrase three times or more, hedge formulas, pet constructions
K02 the same content twice (a table that repeats a paragraph, two sentences that say the same thing)
K03 a number that is not in the material
K04 a name (organisation, Latin word) that is not in the material; katakana words not in the material are listed (advisory)
K05 words not in the material (advisory: candidates for the support judge)
K06 a label heading (事実 / 考察 / まとめ …)
K07 an advertising note in the writer's text (the tool adds it next to the product card, never the writer)
K08 a 豆知識 that is not a confirmed story of the material, or that is the news itself
K09 source talk / 'not known' in the body (sites whose card says so)
K10 shape: lead in two sentences, 3-line summary, long sentences and paragraphs
plus sokuhou.naturaljp (high = blocking) and, for wadai, sokuhou.wadaipost's reading checks (text-level codes only).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from . import doc as D
from .material import numbers, source_text, usable_tips


@dataclass
class Finding:
    code: str
    block: bool          # True: goes back to the writer and stops the output
    msg: str             # Japanese, as the writer reads it
    detail: str = ""

    def as_dict(self):
        return asdict(self)


FORMULAS = ["一つの手", "ひとつの手", "のも手です", "も手です", "選択肢です", "選択肢もあります", "選択肢になります", "方法もあります", "のもありです"]
PETS = [(r"という", 3, "「という」"), (r"ことができ", 0, "「することができます」"), (r"になります", 3, "「になります」"), (r"ておきま", 3, "「ておきます」"),
        (r"ください", 4, "「ください」"), (r"大切です|重要です|大事です", 1, "「大切です/重要です」")]
LABEL_HEAD = re.compile(r"^(?:まとめ|概要|結論|ポイント|注意点|背景|はじめに|おわりに|事実|考察|解説|基本情報|ニュースの概要|今回のポイント)$|確認できた事実|考察|編集部の見方|備え・選び方|豆知識|ライフハック|^【")
# an advertising NOTE, not the word 広告 in a sentence ('契約のきっかけになった広告やパンフレット' is about the shop's adverts; 2026-11-04)
AD_RE = re.compile(r"(?:^|[【\[［(（])\s*(?:広告|ＰＲ|PR)\s*(?:[】\]］)）]|$)|広告を含|広告が含|広告リンク|広告です|(?<![A-Za-z])PR(?![A-Za-z])を含"
                   r"|プロモーションを含|アフィリエイト|提携リンク", re.M)
ORG_RE = re.compile(r"[一-龥ァ-ヴー]{2,}(?:庁|省|県|府|都|市|区|町|村|社|会社|銀行|センター|協会|機構|委員会|大学|研究所)")
LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.&-]{1,}")
KATA_RE = re.compile(r"[ァ-ヴー]{3,}")
KANJI_RE = re.compile(r"[一-龥々]{2,}")
COUNTER_RE = re.compile(r"(?<![\d,.])(\d{1,2})(?=\s*(?:つ|点|行|個|本|枚|回|段|案|人|分|か所|カ所|項目|ステップ))")
# katakana words used in everyday writing: not names
COMMON_KATA = set("""ライト ヘッドライト ランタン スマホ スマートフォン スイッチ バッテリー モバイルバッテリー メール パスワード アカウント ログイン リンク アプリ
ブックマーク ニュース タイプ サイト ページ ポイント チェック リスト メモ カード トイレ ティッシュ ストック スーパー コンビニ スケジュール ジム トレーニング
トレーナー プラン コース カウンセリング サプリ エステ サービス セキュリティ キー セキュリティキー ライフハック スピード レインコート スニーカー テープ
ペットボトル ボトル ケース バッグ ポーチ ハンドル ベッド テーブル カーテン ドア スペース タイミング ルール メッセージ チャンス イメージ シーン ステップ
ショップ ネット インターネット ブラウザ パソコン データ サイズ グッズ ライン メーカー モード マーク カバー スタッフ オンライン レシート コピー""".split())
# wadaipost.UNKNOWN_RE misses the polite negative ('分かっていません'): added here
UNKNOWN_MORE = re.compile(r"(?:分か|わか)っていません|明らかになっていません|明らかではありません|はっきりしていません")
SENT_BLOCK, SENT_WARN, PARA_WARN = 100, 80, 130
# situations that belong to one story; seen in a text whose story does not have them, they came from another material (K12)
SITUATIONS = ["停電", "台風", "地震", "断水", "大雨", "浸水", "避難", "津波", "猛暑", "大雪", "感染", "流出", "漏えい", "不正アクセス", "詐欺"]


NEAR = 6        # sentences: three alike inside this span read as monotonous


def _close(v: list) -> bool:
    """Blocking for a repeated ending/opening: four or more anywhere, or three inside NEAR consecutive sentences."""
    if len(v) >= 4:
        return True
    idx = [i for i, _ in v]
    return any(idx[j + 2] - idx[j] < NEAR for j in range(len(idx) - 2))


def _core(sent: str) -> str:
    s = sent.rstrip()
    while s and s[-1] in "。！？!?　 …~〜」』)）":
        s = s[:-1]
    return s


def _stem_in(w: str, src: str) -> bool:
    """'千葉県' is fine when the material says '千葉'."""
    for suf in ("県", "府", "都", "市", "区", "町", "村", "東部", "西部", "南部", "北部"):
        if w.endswith(suf) and len(w) - len(suf) >= 2 and w[: -len(suf)] in src:
            return True
    return False


def _grams(s: str) -> set:
    s = re.sub(r"[\s、。・「」()（）:：!?！？]", "", s)
    return {s[i:i + 3] for i in range(max(0, len(s) - 2))}


def _jac(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    return len(ga & gb) / max(1, min(len(ga), len(gb))) if ga and gb else 0.0


def _jac_max(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    return len(ga & gb) / max(1, max(len(ga), len(gb))) if ga and gb else 0.0


def _body_sentences(doc: dict) -> list[tuple[int, str]]:
    """(section index, sentence) for the lead (-1) and the sections' paragraphs, bullets and boxes."""
    out = [(-1, s) for s in D.sentences(doc["lead"])]
    for i, s in enumerate(doc["sections"]):
        for t in s["paras"] + s["bullets"] + [b["text"] for b in s["boxes"]]:
            out += [(i, x) for x in D.sentences(t)]
    return out


def check(doc: dict, m: dict, card: dict, kind: str = "article") -> list[Finding]:
    rules = card.get("rules", {})
    src = source_text(m)
    out: list[Finding] = []

    def add(code, block, msg, detail=""):
        out.append(Finding(code, block, msg, detail))

    texts = D.all_texts(doc)
    blob = "\n".join(t for _, t in texts)
    sents = _body_sentences(doc)
    # K01 rhythm
    # monotony is local: three alike within a few sentences (or four anywhere) stop the text; three spread over a long article are a note
    # (2026-11-04: three '…ておきます' across 40 sentences of a preparation article stopped page after page; the reader never marked them)
    ends: dict = {}
    for i, (_, s) in enumerate(sents):
        c = _core(s)
        if len(c) >= 8 and not re.search(r"\d", c[-5:]):
            ends.setdefault(c[-5:], []).append((i, s))
    for k, v in ends.items():
        if len(v) >= 3:
            add("K01", _close(v), f"同じ終わり方(…{k})の文が{len(v)}回あります。言い方を変えるか、文をまとめてください。", " / ".join(x[:20] for _, x in v))
    starts: dict = {}
    for i, (_, s) in enumerate(sents):
        k = re.sub(r"[、。]", "", s)[:6]
        if len(k) == 6:
            starts.setdefault(k, []).append((i, s))
    for k, v in starts.items():
        if len(v) >= 3:
            add("K01", _close(v), f"同じ書き出し({k}…)の文が{len(v)}回あります。", " / ".join(x[:20] for _, x in v))
    body = "".join(t for r, t in texts if r not in ("title", "tldr"))
    seen, reps = set(), {}
    for i in range(len(body) - 8):
        g = body[i:i + 8]
        if g in seen or re.search(r"[\d、。()（）:：\s・「」]", g):
            continue
        seen.add(g)
        n = body.count(g)
        if n >= 3 and g not in src:
            reps[g] = n
    kept: list = []
    for g in sorted(reps, key=lambda x: -reps[x]):
        if any(g[1:] in k or g[:-1] in k or k[1:] in g for k in kept):      # overlapping windows of one phrase count once
            continue
        kept.append(g)
    for g in kept[:3]:
        # three times is a note (filling an omission often names the thing again), four stops the text
        add("K01", reps[g] >= 4, f"「{g}」という言い回しが{reps[g]}回出ます。2回目からは言い換えるか、削ってください。", g)
    n_f = sum(blob.count(f) for f in FORMULAS)
    if n_f:
        # the owner's complaint was the formula used again and again: once is a note, twice stops the text
        add("K01", n_f >= 2, f"「一つの手です」「選択肢です」のような逃げの言い方が{n_f}回あります。ふつうに勧める言い方にしてください。")
    for pat, limit, label in PETS:
        n = len(re.findall(pat, blob))
        if n > limit:
            add("K01", n > limit + 1, f"{label}が{n}回あります(多くて{limit}回まで)。", label)
    # K02 the same content twice
    tables = [ln for ln in "\n".join(t for _, t in texts).split("\n") if ln.strip().startswith("|")]
    if tables:
        cells = "".join(tables)
        if _jac(cells, "".join(t for s in doc["sections"] for t in s["paras"])) > 0.4:
            add("K02", True, "表が、段落と同じことを言っています。表は、数字がたくさんあるときだけにしてください。")
    pairs = 0
    for a in range(len(sents)):
        for b in range(a + 1, len(sents)):
            (ia, sa), (ib, sb) = sents[a], sents[b]
            # both ways: a summary sentence followed by its detail ('見るのは、A、B、C' / 'ふたつめは、B') is not a repeat
            if ia != ib and len(sa) >= 15 and len(sb) >= 15 and _jac(sa, sb) >= 0.6 and _jac_max(sa, sb) >= 0.45 and pairs < 3:
                pairs += 1
                add("K02", True, "ほぼ同じことを、別の所でもう一度言っています。どちらか一方にしてください。", f"{sa[:25]} / {sb[:25]}")
    # K03 numbers not in the material
    srcnum = numbers(src)
    counts = {n for _, t in texts for n in COUNTER_RE.findall(t)}
    for n in sorted(numbers(blob) - srcnum - counts):
        add("K03", True, f"数字「{n}」が素材にありません。素材の数字だけを使ってください。", n)
    # K04 names not in the material
    for rx_, block in ((ORG_RE, True), (LATIN_RE, True)):
        for w in sorted({x for x in rx_.findall(blob) if x not in src and not _stem_in(x, src)}):
            add("K04", block, f"「{w}」は素材にない名前です。素材にない名前は書かないでください。", w)
    kata = sorted({w for w in KATA_RE.findall(blob) if w not in src and w not in COMMON_KATA and not any(w in c for c in COMMON_KATA)})
    if kata:
        add("K04", False, "素材にないカタカナ語(固有名詞なら要確認): " + "、".join(kata[:12]))
    # K05 words not in the material (advisory)
    novel = sorted({w for w in KANJI_RE.findall(blob) if w not in src})
    if novel:
        add("K05", False, "素材にない漢字語(素材外の一言の候補): " + "、".join(novel[:30]))
    # K06 label headings
    for s in doc["sections"]:
        if LABEL_HEAD.search(s["heading"]):
            add("K06", True, f"見出し「{s['heading']}」が分類の札になっています。読者の問いか、中身が分かる短い言い切りにしてください。", s["heading"])
    # K07 advertising note
    m_ad = AD_RE.search("\n".join(t for r, t in texts if r != "reply"))
    if m_ad:
        add("K07", True, "本文に広告の表記があります。広告の表記は、商品カードの横に編集の側で付けるので、本文には書かないでください。", m_ad.group(0))
    # K08 豆知識
    tips = usable_tips(m)
    facts = "".join(f["text"] for f in m.get("facts", []))
    for s in doc["sections"]:
        for b in s["boxes"]:
            if b["kind"] != "tip":
                continue
            t = b["title"] + b["text"]
            if not tips:
                add("K08", True, "素材に豆知識の話がないのに、豆知識の囲みがあります。囲みを消してください。", b["title"])
            elif max(_jac(t, x.get("title", "") + x.get("text", "")) for x in tips) < 0.3:
                add("K08", True, "豆知識の囲みが、素材の「豆知識に使ってよい話」を使っていません。", b["title"])
            elif _jac(t, facts) > 0.5 and max(_jac(t, x.get("title", "") + x.get("text", "")) for x in tips) < 0.5:
                add("K08", True, "豆知識の囲みが、ニュースの事実そのものです。豆知識は「へえ」と思う軽い話だけにしてください。", b["title"])
    # K09 sources / not known
    if rules.get("no_sources") or rules.get("no_unknown"):
        from sokuhou import wadaipost as W
        pub = "\n".join(t for r, t in texts)
        if rules.get("no_sources"):
            # '…と伝えてください / 伝えておく' tells the reader what to say, it is not '…と伝えている' (a report): left out
            talk = [mm.group(0) for mm in W.SOURCE_TALK.finditer(pub)
                    if not (mm.group(0) == "伝えて" and re.match(r"(?:ください|おく|おき|みる|みて|も|、|から)", pub[mm.end():mm.end() + 4]))]
            for x in [n for n in W.MEDIA_NAMES if n in pub] + talk:
                add("K09", True, f"出典の書き方「{x}」があります。媒体の名前や「報道によると」は書かないでください(発表した役所と日付は書いてよい)。", x)
        if rules.get("no_unknown"):
            for mm in list(W.UNKNOWN_RE.finditer(pub)) + list(UNKNOWN_MORE.finditer(pub)):
                add("K09", True, f"「{mm.group(0)}」のような、分からないことを書いた文があります。確かめられたことだけで書いてください。", mm.group(0))
    # K10 shape
    if kind == "article":
        nlead = len(D.sentences(doc["lead"]))
        if nlead == 0 or nlead > 2:
            add("K10", True, f"冒頭が{nlead}文です。2文にしてください。")
        if card.get("parts", {}).get("tldr") and len(doc["tldr"]) != 3:
            add("K10", True, f"3行まとめが{len(doc['tldr'])}行です。ちょうど3行にしてください。")
        if not doc["sections"]:
            add("K10", True, "見出しがありません。")
        for s in doc["sections"]:
            for p in s["paras"]:
                if len(p) > PARA_WARN:
                    add("K10", False, f"{len(p)}字の段落があります(130字以内が目安)。", p[:15])
    for _, s in sents:
        if len(s) > SENT_BLOCK:
            add("K10", True, f"{len(s)}字の長い文があります。2つに分けてください。", s[:20])
        elif len(s) > SENT_WARN:
            add("K10", False, f"{len(s)}字の文があります。", s[:20])
    # K11 the fixed parts of the material: each placed once; their content is not typed out again in the prose
    if kind == "article":
        placed = [mk for s in doc["sections"] for mk in s.get("marks", [])] + doc.get("lead_marks", [])
        prose = "".join(t for s in doc["sections"] for t in s["paras"])
        for p in m.get("parts", []):
            n = placed.count(p["mark"])
            if n != 1:
                add("K11", True, f"決まった部品 {p['mark']} が{n}回置かれています。ちょうど1回、合う場所に置いてください。", p["mark"])
            if p.get("content") and prose and _jac(p["content"], prose) > 0.5 and len(_grams(p["content"])) > 20:
                add("K11", True, f"部品 {p['mark']} の中身を、文でも書いています。文では「下の表で〜」のように指すだけにしてください。", p["mark"])
        for mk in set(placed) - {p["mark"] for p in m.get("parts", [])}:
            add("K11", True, f"素材にない部品 {mk} を置いています。消してください。", mk)
    # K13 a note post carries the AI line near the top (NOTE_DAILY_ROUTINE.md 6) and no product card
    if card.get("_tool") == "note":
        if "AIの支援を受けて作成しています" not in (doc["lead"] + "".join(doc["sections"][0]["paras"] if doc["sections"] else [])):
            add("K13", True, "冒頭の近くに「(この記事は、公開データをもとに、AIの支援を受けて作成しています。)」の1行を入れてください。")
        if any(s.get("slot") for s in doc["sections"]):
            add("K13", True, "note の記事に商品カードは置きません。")
    # K12 a situation from another story (the desk, 2026-11-04: a 停電 box in the data-leak article came from the typhoon article's material):
    # a situation word in the text that is in neither the facts, the reader memo, the topic nor the decided plan
    # the material's confirmed tips and allowed advice belong to the story too (2026-11-04: '避難所のトイレ' from the toilet page's
    # confirmed 豆知識 was stopped as a mix-in)
    story = "\n".join([f["text"] for f in m.get("facts", [])] + [str(v) for v in (m.get("reader_memo") or {}).values()]
                      + [t.get("title", "") + t.get("text", "") for t in usable_tips(m)] + [str(a) for a in m.get("advice", [])]
                      + [m.get("topic", ""), m.get("plan", "")])
    for w in SITUATIONS:
        if w in blob and w not in story:
            add("K12", True, f"「{w}」の話は、この記事の事実にも読者メモにもありません。別の記事の話が混ざっていないか見て、混ざっていれば消してください。", w)
    # naturaljp
    try:
        from sokuhou import naturaljp as NJ
        for h in NJ.check_text("\n".join(t for r, t in texts if r != "heading"), site=rules.get("naturaljp_site")):
            if h.level in ("high", "mid"):
                add("NJ", h.level == "high", f"[{h.rule}] {h.note or ''} 「{(h.full or h.sentence)[:40]}」".replace("  ", " "), h.rule)
    except Exception as e:      # noqa: BLE001
        add("NJ", False, f"naturaljp を実行できませんでした: {e}")
    # wadaipost (reading checks, text-level codes only)
    if rules.get("wadaipost") and kind == "article":
        out += wadai_findings(doc, m)
    return out


WADAI_BLOCK = {"A06", "A07", "A08", "A13", "A15", "A20", "A26", "A28"}
WADAI_ADVISE = {"A02", "A03", "A04", "A05", "A22", "A23"}
WADAI_JA = {"A06": "名前の出た相手を責める言い方があります。", "A07": "あおる言葉・体験を装う言葉・権威を借りる言葉があります。", "A08": "価格・順位・商品名の言葉があります。",
            "A13": "被害を受けた個人の話、または備えの部分にトラブルの相手の名前があります。", "A15": "冒頭が長いか、分からないことから始まっています。",
            "A20": "硬い言い回しがあります。話すときの言い方にしてください。", "A26": "同じ数字を3か所以上で言っています。1〜2か所にしてください。",
            "A28": "読者が引っかかった言葉(作った言葉・あいまいな言葉)があります。"}


def wadai_findings(doc: dict, m: dict) -> list[Finding]:
    from sokuhou import wadaipost as W
    a = D.to_wadai(doc, m)
    a["ads"] = False            # the tool adds the advertising note itself (K07 checks the writer's text)
    fs = W.check_reading(a) + W.check_article(a, {"allowed_phrases": []})
    out, seen = [], set()
    for f in fs:
        if (f.code, f.msg, f.detail) in seen:
            continue
        seen.add((f.code, f.msg, f.detail))
        if f.code in WADAI_BLOCK:
            out.append(Finding("W" + f.code, True, WADAI_JA.get(f.code, "") + f" ({f.msg} {f.detail})".rstrip(), f.detail))
        elif f.code in WADAI_ADVISE:
            out.append(Finding("W" + f.code, False, f"{f.msg} {f.detail}".strip(), f.detail))
    return out


def blocking(fs: list[Finding]) -> list[Finding]:
    return [f for f in fs if f.block]
