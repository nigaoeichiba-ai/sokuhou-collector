"""Wording and heading rules the desk and the owner found by reading (2026-11-04), as machine checks. Every finding here is a mark for a
person (never blocking in light mode); the writer's one fix call names the sentences. The goal is to prevent each by rule/template, so a
text needs no AI to be right: each rule says which kind of slip it catches.

S01 並べる/並んでいる (things or numbers)      S02 商品・案内を「置く」          S03 「扱う」(the content of the article)
S04 forcing: てみてください / しなさい / べき / しないと (the dictionary) and ください / ましょう in the wrong place (ask_placement: lead, tldr, stacked, after an assurance)
S05 a title/heading that ends on an abstract verb alone (数えてみよう …) or uses 〜てみよう/みましょう
S06 a heading ending on a verb with no object (を)   S07 a heading ending on 「へ」   S08 a list of nouns standing as a sentence
S09 「数」「目安」「量」 with nothing before it saying what     S10 a range that does not match the count (0〜7 / 8 types)
S11 a table/checklist intro with 「〜の行」 or a bare 「見てください」   S12 「家族の人」「人数の行」(unclear)   S13 数える/確かめる without 「を」   S14 stops on a particle
Not yet by rule (needs parsing): subject-predicate agreement ('携帯トイレは…備える'), dropped subject/object inside a long sentence.
"""
from __future__ import annotations

import re

from . import doc as D
from . import lexicon

LABELS = {"S01": "「並べる」の言い方", "S02": "「置く」(商品・案内)", "S03": "「扱う」の言い方", "S04": "強い言い方・「ください」の多さ",
          "S05": "題・見出しの抽象的な動詞", "S06": "動詞止めの見出しに目的語がない", "S07": "「へ」止めの見出し", "S08": "名詞の列挙が文になっていない",
          "S09": "何の数・目安・量か分からない", "S10": "数の範囲と種類数が合わない", "S11": "表の案内文(「〜の行」・命令形)", "S12": "「家族の人」「人数の行」", "S13": "「数える」に「何を」がない", "S14": "助詞で終わる文・見出し", "S15": "「所」「ところ」(場所でないもの)", "S16": "「見つけてみませんか」", "S17": "「どこ」(場所でないもの)", "S18": "個数でないものを「数える」", "S19": "「埋める」の言い方", "S20": "回りくどい言い方・長い題", "S21": "AIに多い言い回し(調査より)", "S37": "同じ動詞の見出しが続く", "S43": "導入に□", "S45": "別々の話を並べている", "S49": "見出しが「〜から選ぶ」", "S53": "導入と同じ文が3行まとめにある", "S44": "3行まとめの文末がそろっていない", "S54": "「額が出ます」型の「出る・出す」", "S56": "主語と述語が合わない(量・結果が「〜します」)", "S57": "前の文とつながっていない文", "S58": "狙う語が題・導入・descriptionにない(SEO)", "S59": "「〜ます」で終わる文が続く", "S60": "同じ趣旨の文がページのあちこちにある", "S61": "結び(まとめと次の1手)がない", "S63": "同じ名詞止めの説明がくり返される", "S77": "物が主題なのに、述語が量・期間・回数(「食料は日数分です」)", "S79": "理由が省かれた連用中止(「足り、〜ません」)", "S80": "囲みの文末が「〜します」(呼びかけ形がよい)", "S81": "ページを開く・読むことを勧める文", "S82": "1つの数が2つの物に続く(誤読)", "S83": "専門語の初出に定義がない", "S85": "主題の時間語と述語の時間語が食い違う"}

ABSTRACT_HEAD = re.compile(r"(?:数え|確かめ|確認し|調べ|見直し|考え|見)(?:て(?:み)?)?(?:よう|ましょう)|数えて|確かめて|てみよう|てみましょう|てみる[!?！？]?$")
SUBJ_TOPIC = r"(?:量|数|額|幅|目安|結果|値|金額|総額|費用|料金|回数|日数|人数|必要数|グッズ|もの|項目|商品|期間|割合|費)"
SUBJ_DOING = re.compile(r"^(?:[^。、は]{0,14}、)?[^。、は]{0,16}" + SUBJ_TOPIC + r"は、[^。]*?((?:計算|確認|用意|見直)し|決め|買い足し|買い|増やし|そろえ|比べ|調べ|選び|出し|足し|引き|集め|加え|考え)ます。?$")
SUBJ_FIX = {"計算": "計算できます", "買い足し": "買い足せばOKです / 買い足していきます", "買い": "買えば足ります / 買っていきます", "増や": "増やしていきます",
            "確認": "確認できます / 分かります", "決め": "決まります / 決められます", "出し": "分かります"}
LATER_DOING = re.compile(r"(?:あとから|そのあと|その後|のちに|のちほど|少しずつ|だんだん|徐々に|いずれ)[^。]{0,30}(?:増やし|買い足し|そろえ|用意し|足し|加え)ます。?$")
VERB_END = re.compile(r"(?:[るうくすつぬぶむぐ]|ます|ましょう|ください)[。!！]?$")
NOUN_LIST = re.compile(r"^[^。、]{2,16}(?:、[^。、]{2,16}){2,}。?$")


def _sents(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[。!?！？])", text) if s.strip()]


def check(doc: dict) -> list[dict]:
    """[{code, msg, detail}] — detail is the sentence (so the writer's fix can name it)."""
    out: list[dict] = []

    def add(code: str, msg: str, sent: str) -> None:
        out.append({"code": code, "msg": msg, "detail": sent[:90]})

    heads = [("題", doc["title"])] + [("見出し", s["heading"]) for s in doc["sections"]]
    body: list[str] = []
    for s in doc["sections"]:
        body += s["paras"] + s["bullets"] + [b["text"] for b in s["boxes"]]
    body = [doc["lead"]] + doc["tldr"] + body
    sents = [x for t in body for x in _sents(t)]

    for kind, h in heads:
        if not h:
            continue
        if ABSTRACT_HEAD.search(h):
            add("S05", f"{kind}が「数える・確かめる・見る」やの「〜てみよう」だけで、何のために何をするかが分かりません。「何を・どうする」を言ってください。", h)
        last = re.split(r"[?？、「」:：]", h)[-1].strip() if not h.rstrip().endswith(("?", "？")) else ""
        if kind == "見出し" and last and VERB_END.search(last) and "を" not in h and not re.search(r"に参加|に行|へ行|に入|に出", last) and not last.endswith(("ください", "ましょう")):
            add("S06", "見出しが動詞で終わっていて、何を・どうするかの「何を」がありません。名詞止めか「〜を〜する」の形にしてください。", h)
        if kind == "題" and re.search(r"ください|ましょう", h):
            add("S20", "題の「〜してください」「〜しましょう」は強いる言い方です。直球の言い方(問いかけ・約束)にしてください。", h)
        if kind == "題" and (len(h.rstrip("?？!！")) > 28 or re.search(r"[:：]", h)):
            add("S20", "題が長い、または「:」で副題が続いています。主題の語+問いかけか約束で、15〜25字ぐらいの直球にしてください。", h)
        if kind == "見出し" and re.search(r"から選ぶ$", h):
            add("S49", "見出しが「〜から選ぶ」で、何をするかが抽象的です。「どれから始める？」のように、直球の問いや動作にしてください。", h)
        if h.rstrip().endswith("へ"):
            add("S07", "見出しが「へ」で終わっています。動詞まで言い切るか、名詞止めにしてください。", h)

    # S43 a □ in the lead (the checklist has not appeared yet); S44 the 3-line summary mixes endings (です/ます and plain or noun endings)
    if "□" in doc["lead"]:
        add("S43", "導入に「□」が出ています。チェックリストの前なので、意味が通りません。", doc["lead"][:90])
    ends = [bool(re.search(r"(?:です|ます|でした|ました|ません)[。]?$", x)) for x in doc["tldr"]]
    if len(ends) >= 3 and 0 < sum(ends) < len(ends):
        add("S44", "3行まとめの文末がそろっていません(「です・ます」と、そうでない終わり方が混ざっています)。", "/".join(x[-8:] for x in doc["tldr"]))

    # S45 two separate stories side by side: the typhoon and the 防災庁 call in one lead, paragraph or sentence (the owner, 2026-11-04)
    for label, unit in [("導入", doc["lead"])] + [("段落", q) for sec in doc["sections"] for q in sec["paras"]]:
        if "台風" in unit and "防災庁" in unit:
            add("S45", f"{label}で「台風」と「防災庁」を並べています。別の話なので、どちらか一方を主役にして、もう一方は別の節で一度だけ出してください。", unit[:90])

    # S53 a sentence of the lead repeated in the 3-line summary (the desk, 2026-11-04: it reads as a repetition on a phone)
    def _norm(x):
        return re.sub(r"[\s、。「」()（）!?！？・]", "", x)
    lead_s = [_norm(x) for x in _sents(doc["lead"]) if len(_norm(x)) >= 8]
    for line in doc["tldr"]:
        for x in _sents(line):
            nx = _norm(x)
            if len(nx) >= 8 and any(nx == l or (len(set(nx[i:i + 3] for i in range(len(nx) - 2)) & set(l[i:i + 3] for i in range(len(l) - 2))) >= 0.85 * max(1, min(len(nx), len(l)) - 2)) for l in lead_s):
                add("S53", "導入の文と同じ(ほぼ同じ)文が、3行まとめに入っています。3行まとめは、導入と重ならない3点にしてください。", x)

    # S37 the same verb in three headings or more
    hs = [h for k, h in heads if k == "見出し" and h]
    for stem in ("確かめ", "確認", "見直", "チェック", "数え", "そろえ", "増や", "備え"):
        if sum(stem in h for h in hs) >= 3:
            add("S37", f"見出しに「{stem}」が{sum(stem in h for h in hs)}つあります。言い換えて、見出しの形を変えてください。", "、".join(h for h in hs if stem in h)[:90])

    for s in sents:
        if NOUN_LIST.match(s) and not re.search(r"です|ます|ない|した|する|ある", s):
            add("S08", "名詞を並べただけで、文として終わっていません。「〜の七つです」のように言い切ってください。", s)
        if re.search(r"(?:^|[、。 　はをにがでとも])(?:その|この|あの)?(?:数|目安)(?:を|は|が|と|に|で)", s) or re.search(r"(?:必要な|いまある|今ある|そろっている|それぞれの)(?:数|量)(?!の|だけ)", s):
            add("S09", "「数」「目安」「量」が、何の数かを言っていません。対象を入れてください。", s)
        if re.search(r"の行", s) and re.search(r"見て|探して|確かめて", s):
            add("S11", "「〜の行」は何の人数・何の行か分かりにくく、「見てください」は何が分かるかを言っていません。「自分の家の人数の行を見ると、〜が分かります」の形に。", s)

    # S13 数える/確かめる without an object in the same sentence; S14 a sentence or heading that stops on a particle
    for s in sents + [h for _, h in heads if h]:
        if re.search(r"数え(?:る|て|ます|られます|ておきます|ておく)", s) and not re.search(r"を[^。、]{0,40}数え", s) and not re.search(r"(?:数|量|回数|在庫)が", s):
            add("S13", "「数える」に、何を、がありません。「〜を数える」の形にしてください(題・見出しの「数える」だけは、S05)。", s)
        if re.search(r"[でにをはがもとのへ][。!！]?$", s.strip()) and not re.search(r"(?:ので|ため|とも|のに)[。]?$", s.strip()):
            add("S14", "文や見出しが助詞で終わっていて、述語がありません。", s)

    # S56 subject and predicate do not fit: a quantity / result / thing as the topic, ended by a doing verb ("水の必要量は…計算します");
    # advice to the reader that reads as the writer's own act ("あとから1週間分まで増やします"). S57 a sentence that starts in the middle (no subject, 「その」「これ」
    #「〜も含めて」) when the sentence before does not give the thing it points at.
    for s in sents:
        m = SUBJ_DOING.match(s)
        if m and not re.search(r"(?:でき|いき|行き|分かり|わかり|見え|変わり|決まり|なり)ます。?$", s):
            verb = m.group(1)
            fix = SUBJ_FIX.get(verb) or SUBJ_FIX.get(verb.rstrip("し")) or "〜できます / 〜が分かります"
            add("S56", f"主語が量・結果・物なのに、人がする言い方「{verb}ます」で終わっています。主語に合う述語にしてください(例: {fix})。", s)
        elif LATER_DOING.search(s):
            add("S56", "読者への助言なのに、書き手が行う形で終わっています。「〜していきます」「〜すればOKです」の形にしてください。", s)
    paras = [doc["lead"]] + [q for sec in doc["sections"] for q in sec["paras"]]
    for q in paras:
        ss = _sents(q)
        for i, s in enumerate(ss):
            if s.startswith("#") or s.startswith("[") or s.startswith("|"):
                continue
            starts_ref = re.match(r"^(?:その|この|あの|これ|それ|あれ|そう)(?!から|まで|ため|あと|ページ|記事)", s) and i == 0
            no_subject = re.match(r"^[^。、はが]{0,20}も含めて、", s) and not re.search(r"[はが]", s)
            if (starts_ref or no_subject) and i == 0:
                add("S57", "前の文とつながっていません(段落の最初の文が、「その・これ」や「〜も含めて」で始まっています)。何の話かを主語に入れてください。", s)
            elif no_subject and i > 0:
                key = re.sub(r"[^ぁ-んァ-ン一-龥ー]", "", s.split("も含めて")[0])
                prev = ss[i - 1]
                if not any(w and w in prev for w in re.findall(r"[ァ-ンー]{2,}|[一-龥]{2,}", key)):
                    add("S57", "前の文に、この文が指す話(主語)がありません。いきなり別の話になります。主語を入れるか、前の文とつなげてください。", s)

    # the word dictionary (data/word_rules.json): S01-S04 words, S12, S15-S19 ...  Every point the owner or the desk made is one entry there.
    out += lexicon.scan(sents + [h for _, h in heads if h])

    out += ask_placement(doc)

    # S10: a range of N+1 values (0..N) against a stated count of types
    blob = "\n".join(body)
    rng = re.search(r"0[〜~ー-](\d{1,2})", blob)
    cnt = re.search(r"(\d{1,2})(?:つの種類|種類)", blob + "\n".join(h for _, h in heads))
    if rng and cnt and int(rng.group(1)) != int(cnt.group(1)):
        add("S10", f"数の範囲(0〜{rng.group(1)})と種類の数({cnt.group(1)}種類)が合いません。", rng.group(0))
    out += page_rules(doc)
    out += thing_quantity(doc)
    out += owner_nov5_night(doc)
    out += time_clash(doc)
    return out


def seo_check(doc: dict, m: dict) -> list[dict]:
    """S58 (the owner, 2026-11-05: SEO): one search phrase per page (material 'keyword', words separated by spaces) must be in the title, in the first two
    sentences of the lead (the answer), and the material needs its own 'description' (one or two sentences that are not the lead copied) with the phrase.
    Only for materials that name a keyword; a mark for a person, like every check here."""
    kw = (m.get("keyword") or "").split()
    if not kw:
        return []
    out = []

    def add(msg, detail):
        out.append({"code": "S58", "msg": msg, "detail": detail[:90]})
    title, lead = doc.get("title", ""), doc.get("lead", "")
    if not all(w in title for w in kw):
        add(f"狙う語「{' '.join(kw)}」が題にありません。題の前半に自然に入れてください(直球で、問いかけだけの題にしない)。", title)
    head = "".join(_sents(lead)[:2])
    if not all(w in head for w in kw):
        add(f"狙う語「{' '.join(kw)}」が、導入の最初の2文にありません。検索した人の問いに、最初の2文で答えてください。", head)
    desc = (m.get("description") or "").strip()
    if not desc:
        add("description(ページ固有の1〜2文)がありません。素材の description に、狙う語を入れて書いてください。", title)
    else:
        if not all(w in desc for w in kw):
            add("description に狙う語がありません。", desc)
        g = lambda x: {x[i:i + 3] for i in range(len(x) - 2)}
        if g(desc) and len(g(desc) & g(lead)) >= 0.6 * len(g(desc)):
            add("description が導入の文とほぼ同じです。導入の流用でなく、ページ固有の1〜2文にしてください。", desc)
    return out


# ---- 2026-11-05 (the owner): runs of 「ます」, a thing as the topic with a person's act as the predicate, the same gist said again and again, no closing ----------

MASU_RUN = 3            # sentences in a row ending in ます (not です)
MASU_SHARE = 0.75       # or this share of a section with five sentences or more
THING_TOPIC = (r"(?:水|食料|食事|携帯トイレ|トイレ|ライト|電池|充電|ラジオ|雨具|防水|救急用品|バッテリー|表|早見表|ページ|商品|防災グッズ|グッズ|"
               r"量|数|額|幅|目安|結果|値|金額|総額|費用|料金|回数|日数|人数|必要数|項目|期間|割合|費)")
DOING_END = re.compile(r"(?:(?:計算|確認|用意|見直|保管|備蓄)し|決め|買い足し|買い|増やし|そろえ|比べ|調べ|選び|出し|足し|引き|集め|加え|考え|備え|見|書い|入れ|持ち|しまい|つけ|かけ|にし|届くものにし|"
                       r"(?:そろえ|用意し|入れ|書い|選び|買い|しまい|確かめ|見)て?おき)ます。?$")
THING_FIRST = re.compile(r"^(?:[^。、は]{0,14}、)?[^。、は]{0,12}" + THING_TOPIC + r"は、")


def _ends_masu(s: str) -> bool:
    return bool(re.search(r"ます。?$", s)) and not re.search(r"(?:でし|です)。?$", s)


def _plain(x: str) -> str:
    return re.sub(r"[\s、。「」()（）!?！？・]", "", x)


def page_rules(doc: dict) -> list[dict]:
    out: list[dict] = []

    def add(code, msg, sent):
        out.append({"code": code, "msg": msg, "detail": sent[:90]})
    # S59 ます in a row
    for sec in doc["sections"]:
        seq = [x for p in sec["paras"] if not p.startswith(("[", "|", "#")) for x in _sents(p)]
        run = best = 0
        for x in seq:
            run = run + 1 if _ends_masu(x) else 0
            best = max(best, run)
        masu = sum(_ends_masu(x) for x in seq)
        if best >= MASU_RUN or (len(seq) >= 5 and masu / len(seq) > MASU_SHARE):
            add("S59", f"「〜ます」で終わる文が続いています(節「{sec['heading'][:14]}」: 続き最長{best}文、{masu}/{len(seq)}文)。「です」「〜が目安です」「〜するとよい」「〜が合う」「体言止め」などを混ぜてください。", sec["heading"])
    # S56 (wider): a thing as the topic, the predicate is a person's act; and the sentences after it without a subject
    for sec in doc["sections"]:
        for p in sec["paras"]:
            if p.startswith(("[", "|", "#")):
                continue
            ss = _sents(p)
            first_thing = bool(ss) and bool(THING_FIRST.match(ss[0]))
            for i, x in enumerate(ss):
                if THING_FIRST.match(x) and DOING_END.search(x):
                    add("S56", "主題が物・量なのに、人がする言い方で終わっています(「ライトは、…備えます」)。述語を主題に合わせてください(例: 〜を選びます→〜が合います / 〜するとよいです / 〜が目安です)。", x)
                elif i > 0 and first_thing and not re.match(r"^[^、。]{1,14}[はが]、", x) and not re.search(r"ときは|場合は", x) and re.search(r"(?:そろえ|用意し|入れ|書い|選び|買い|しまい|確かめ|見)て?おきます。?$", x):
                    add("S56", "段落の主題が物・量なのに、主語のない文が人がする言い方で終わっています。主語を入れるか、主題に合う述語にしてください。", x)
    # S60 the same gist in several places (tldr, paragraphs, boxes, closing)
    units = [("3行まとめ", t) for t in doc["tldr"]]
    for sec in doc["sections"]:
        units += [("本文", p) for p in sec["paras"] if not p.startswith(("[", "|", "#"))]
        units += [("囲み", b["title"] + "。" + b["text"]) for b in sec["boxes"]]
    sl = []
    for ui, (kind, t) in enumerate(units):
        for x in _sents(t):
            n = _plain(x)
            if len(n) >= 12:
                sl.append((ui, kind, x, n, {n[i:i + 3] for i in range(len(n) - 2)}))
    lead_n = [_plain(x) for x in _sents(doc["lead"]) if len(_plain(x)) >= 8]
    seen = set()
    for a in range(len(sl)):
        for b in range(a + 1, len(sl)):
            ua, ka, xa, na, ga = sl[a]
            ub, kb, xb, nb, gb = sl[b]
            if ua == ub or (xa, xb) in seen:
                continue
            if len(ga & gb) >= 0.6 * min(len(ga), len(gb)):
                seen.add((xa, xb))
                add("S60", f"ほぼ同じ趣旨の文が、{ka}と{kb}にあります。どちらか一方にしてください。(もう一方: {xb[:30]})", xa)
    # S61 the closing (the desk, 2026-11-05): the last section is headed with 「まとめ」, starts 「このページのまとめです」, goes answer -> points -> the next one step,
    # and does not end on a box, a link or a bullet list
    if doc["sections"]:
        last = doc["sections"][-1]
        flow = last.get("flow", [])
        end = flow[-1] if flow else None
        step = re.compile(r"まず|次に|今日|今夜|今から|はじめ|始め|最初|ここから|1つ|ひとつ|あとは|すぐ")
        if "まとめ" not in last["heading"]:
            add("S61", "最後の節の見出しに「まとめ」がありません。「まとめ: 〜」のように、まとめの節だと分かる見出しにしてください。", last["heading"])
        elif not (last["paras"] and last["paras"][0].startswith("このページのまとめです")):
            add("S61", "まとめの節の最初が「このページのまとめです」で始まっていません。結論(答え)→要点→次の1手の順に書いてください。", last["paras"][0] if last["paras"] else last["heading"])
        if end is None or end[0] in ("x", "m", "b") or not step.search(end[1]):
            add("S61", "結びがありません。最後は、結論をもう一度言い、次にやる1つを書くまとめで終えてください(ライフハックの囲み・案内のリンク・箇条書きで終わらせない)。", (end[1] if end else last["heading"]))
    # S63 the same noun-ending explanation again and again ("〜の用意です" for each item): two in a row with the same ending
    for sec in doc["sections"]:
        firsts = [(_sents(q) or [""])[0] for q in sec["paras"] if not q.startswith(("[", "|", "#"))]
        ends = [re.search(r"([^、。は]{1,6}(?:の用意|のための用意|の役目|の手段|のひとつ|のこと))です。?$", x) for x in firsts]
        for i in range(1, len(firsts)):
            if ends[i] and ends[i - 1] and ends[i].group(1)[-3:] == ends[i - 1].group(1)[-3:]:
                add("S63", f"「{ends[i].group(1)[-3:]}です」と終わる説明が、続けて出ています。項目ごとに同じ型にせず、主語の中身に合う述語(「〜の役目は…です」「〜が中心です」「〜が目安です」)にしてください。", firsts[i])
    ncnt = sum(1 for sec in doc["sections"] for q in sec["paras"] for x in _sents(q) if re.search(r"の用意です。?$", x))
    if ncnt >= 3:
        add("S63", f"「〜の用意です」が{ncnt}回あります。同じ言い方をくり返さず、主語の中身に合う述語にしてください。", "の用意です")
    return out

# S77 (the owner, 2026-11-05: "食料は日数分です" / "携帯トイレは7日分です" — a thing as the topic, a quantity or a period as the predicate): read the sentence as
# [topic]は[predicate] only; it must hold.  The predicate is a quantity (日分・週間分・リットル・回・ロール ...) with です at the end.
QTY_END = re.compile(r"(?:日分|週間分|か月分|ヶ月分|日数分|人数分|回分|リットル)です。?$")      # 「4本です」「1箱です」は成り立つ(4人の判定)。成り立たないのは、期間・分量
QTY_OK = re.compile(r"目安|基準|必要|理想|ほど|くらい|約|最低|できれば|以上|以内|までです|からです|だけです")


def thing_quantity(doc: dict) -> list[dict]:
    out = []
    sents = [x for t in [doc["lead"]] + doc["tldr"] + [q for sec in doc["sections"] for q in sec["paras"]] for x in _sents(t) if not x.startswith(("[", "|", "#"))]
    for x in sents:
        m = re.match(r"^(?:[^。、は]{0,14}、)?([^。、は]{0,10}" + THING_TOPIC + r")は、(.*)$", x)
        if m and QTY_END.search(x) and not QTY_OK.search(m.group(2)):
            pred = re.search(r"([^、。]{0,12}" + QTY_END.pattern[:-3] + ")", x)
            out.append({"code": "S77", "msg": f"「{m.group(1)}は{(pred.group(1) if pred else '')}です」と主題と述語だけにすると成り立ちません(物が主題なのに、述語が量・期間・回数)。述語を主題に合わせてください(例: 「{m.group(1)}は、〜分が必要です」「〜が目安です」「〜が理想です」)。", "detail": x[:90]})
    return out


# ---- 2026-11-05 night (the owner, on the bousai parent) -----------------------------------------------------------------------------------------------------
KATA_OK = {"ライフハック", "チェックリスト", "モバイルバッテリー", "パーソナルトレーニング", "パーソナルジム", "クーリング・オフ", "ホットライン", "カウンセリング", "アンケート", "トイレットペーパー",
           "ウェットティッシュ", "レインコート", "ランタン", "ショッピング", "インターネット", "スマートフォン", "コンビニエンスストア", "カセットコンロ", "カセットボンベ", "ポリ袋", "パンフレット", "エステティック", "ティッシュ", "トレーナー", "ペットボトル", "バッテリー", "サプリメント", "パスワード", "クレジットカード", "ブックマーク", "ヘクトパスカル", "スプレータイプ", "ハザードマップ", "トイレットペーパー・ウェットティッシュ", "ウェットティッシュ"}
DEF_MARK = re.compile(r"という|とは|のひとつ|の一つ|のこと|と呼|と言い|を指し|のしくみ|のやり方|方法です|ことです")


def owner_nov5_night(doc: dict) -> list[dict]:
    out: list[dict] = []

    def add(code, msg, sent):
        out.append({"code": code, "msg": msg, "detail": sent[:90]})
    paras = [(q, sec["heading"]) for sec in doc["sections"] for q in sec["paras"] if not q.startswith(("[", "|", "#"))]
    sents = [x for t in [doc["lead"]] + doc["tldr"] + [q for q, _ in paras] + [b["text"] for sec in doc["sections"] for b in sec["boxes"]] for x in _sents(t)]
    for x in sents:
        # S79 a "足り、" / "すみ、" / "し、…必要はありません" chain: the reason between the two halves is dropped
        if re.search(r"(?:足り|すみ|済み|そろい|あり|でき)、[^。]*(?:必要は|心配は|ことは|わけでは)?(?:ありません|ません)。?$", x) or re.search(r"し、[^。、]{0,25}必要はありません。?$", x):
            add("S79", "「〜し、〜ません」の形は、間の理由(〜ので)が省かれていて、つながりが読めません。文を分けてください(例: 「まずは、1つずつで足ります。慌てて買い込む必要はありません。」)。", x)
        # S81 the text pushes the reader to open / read a page
        if re.search(r"(?:ページ|記事)を(?:開|読)(?:く|き|い|み|ん)", x):
            add("S81", "ページを開く・読むことを勧める文です。読むこと自体を勧めず、そのページで分かる中身(何が見つかるか)を言ってください。", x)
        # S82 one number after two things ("水と食料は、1人1日3リットルを目安に…": 食料も3リットルに読める)
        if re.search(r"[^、。は]{1,6}と(?!き|こ|い|し|も)[^、。は]{1,6}は、[^。]*[0-9]+(?:リットル|L|本|個|回|ロール|キロ|kg|枚)", x):
            add("S82", "2つの物を並べた主題に、1つの数が続いています(水と食料は3リットル、と読めます)。数が係る相手ごとに文を分けてください(「水は…、食料は…」)。", x)
    # S80 the box (ライフハック / 豆知識): advice ends in the plain 「〜します」, not an invitation
    for sec in doc["sections"]:
        for b in sec["boxes"]:
            if b.get("kind") == "hack":
                for x in _sents(b["text"]):
                    if re.search(r"[^でま]ます。?$", x) and not re.search(r"ましょう|ください|ません|(?:なり|れ|でき|え|分かり|わかり|かり|まり|わり|やすくな|なくな|あり|すみ|済み)ます。?$", x):
                        add("S80", "ライフハックの囲みの文末が「〜します」です。呼びかけ形(「〜しましょう」「〜するとよいです」)にしてください。", x)
    # S83 a katakana term of 5+ characters is used first without any definition near it
    seen: set[str] = set()
    flat = [x for t in [doc["lead"]] + doc["tldr"] + [q for q, _ in paras] for x in _sents(t)]
    for i, x in enumerate(flat):
        for term in re.findall(r"[ァ-ヶー]{5,}(?:・[ァ-ヶー]+)?", x):
            if term in seen or term in KATA_OK:
                continue
            seen.add(term)
            if not DEF_MARK.search(x) and not (i + 1 < len(flat) and DEF_MARK.search(flat[i + 1])) and not (i > 0 and DEF_MARK.search(flat[i - 1])):
                add("S83", f"専門語「{term}」が、定義なしで出ています。初めて出すときは、意味・利点・弱点を1〜2文ずつ添えてください。", x)
    return out


# S85 (the owner, 2026-11-05): 「今日は、…次の買い物のかごに入れましょう」 — the topic says today, the predicate says a later time.  Cut to [time topic]は[predicate time] and it clashes.
TOPIC_TIME = r"(?:今日|今夜|今朝|今は|いまは|今回|いま|今)"
LATER_TIME = re.compile(r"(?:次の(?:買い物|機会|休み|週末|外出|お出かけ|とき|時)|あとで|後で|今度|そのうち|後日|いつか)")      # 「来週の予定」のように目的語を飾る時間語は、成り立つ(4人の判定)


def time_clash(doc: dict) -> list[dict]:
    out = []
    sents = [x for t in [doc["lead"]] + doc["tldr"] + [q for sec in doc["sections"] for q in sec["paras"]] + [b["text"] for sec in doc["sections"] for b in sec["boxes"]] for x in _sents(t) if not x.startswith(("[", "|", "#"))]
    for x in sents:
        m = re.match(r"^(" + TOPIC_TIME + r")は?、(.*)$", x)
        if m and LATER_TIME.search(m.group(2)):
            out.append({"code": "S85", "msg": f"文頭の「{m.group(1)}」と、後ろの「{LATER_TIME.search(m.group(2)).group(0)}」の時間が合いません。「次の買い物では、〜をかごに入れましょう」のように、時間語を述語側にそろえてください。", "detail": x[:90]})
    return out


# ---- 「ください」「しましょう」: judged by where they stand, not by a count (the owner, 2026-11-05: used in the right place they are fine) ----------------------------------
ASK = re.compile(r"ください|ましょう")
ASSURE = re.compile(r"安心|必ず|絶対|大丈夫です|心配ありません")


def ask_placement(doc: dict) -> list[dict]:
    """S04: an invitation is marked when it stands (b) twice in neighbouring sentences, (c) three or more in one section, (d) right after an assurance without a ground ('安心です。…してください').  Kept where it is natural: one concrete step of a procedure, the end of a box, the closing next step."""
    out = []

    def add(msg, sent):
        out.append({"code": "S04", "msg": msg, "detail": sent[:90]})
    for sec in doc["sections"]:
        sec_n = 0
        for q in sec["paras"]:
            if q.startswith(("[", "|", "#")):
                continue
            ss = _sents(q)
            idx = [i for i, x in enumerate(ss) if ASK.search(x)]
            sec_n += len(idx)
            if len(idx) >= 2 and idx[-1] - idx[0] <= 1:
                add("「〜してください/〜しましょう」が、隣り合う文で重なっています。促すのは1つにしてください。", ss[idx[1]])
            for i in idx:
                if i > 0 and ASSURE.search(ss[i - 1]):
                    add("根拠のない安心の言い切りのすぐあとに、促す言い方が続いています。理由を言ってから促してください。", ss[i])
        if sec_n >= 3:
            add(f"節「{sec['heading'][:14]}」に、促す言い方(〜してください/〜しましょう)が{sec_n}つあります。重ねず、1節に2つまでにしてください。", sec["heading"])
    return out
