"""Wording and heading rules the desk and the owner found by reading (2026-11-04), as machine checks. Every finding here is a mark for a
person (never blocking in light mode); the writer's one fix call names the sentences. The goal is to prevent each by rule/template, so a
text needs no AI to be right: each rule says which kind of slip it catches.

S01 並べる/並んでいる (things or numbers)      S02 商品・案内を「置く」          S03 「扱う」(the content of the article)
S04 forcing: てみてください / しなさい / べき / しないと, and ください more than 3 times, ましょう more than 2 times
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
          "S09": "何の数・目安・量か分からない", "S10": "数の範囲と種類数が合わない", "S11": "表の案内文(「〜の行」・命令形)", "S12": "「家族の人」「人数の行」", "S13": "「数える」に「何を」がない", "S14": "助詞で終わる文・見出し", "S15": "「所」「ところ」(場所でないもの)", "S16": "「見つけてみませんか」", "S17": "「どこ」(場所でないもの)", "S18": "個数でないものを「数える」", "S19": "「埋める」の言い方", "S20": "回りくどい言い方・長い題", "S21": "AIに多い言い回し(調査より)", "S37": "同じ動詞の見出しが続く", "S43": "導入に□", "S45": "別々の話を並べている", "S49": "見出しが「〜から選ぶ」", "S53": "導入と同じ文が3行まとめにある", "S44": "3行まとめの文末がそろっていない", "S54": "「額が出ます」型の「出る・出す」", "S56": "主語と述語が合わない(量・結果が「〜します」)", "S57": "前の文とつながっていない文"}

ABSTRACT_HEAD = re.compile(r"(?:数え|確かめ|確認し|調べ|見直し|考え|見)(?:て(?:み)?)?(?:よう|ましょう)|数えて|確かめて|てみよう|てみましょう|てみる[!?！？]?$")
SUBJ_TOPIC = r"(?:量|数|額|幅|目安|結果|値|金額|総額|費用|料金|回数|日数|人数|必要数|グッズ|もの|項目|商品|期間|割合|費)"
SUBJ_DOING = re.compile(r"^(?:[^。、は]{0,14}、)?[^。、は]{0,16}" + SUBJ_TOPIC + r"は、[^。]*?((?:計算|確認|用意|見直)し|決め|買い足し|買い|増やし|そろえ|比べ|調べ|選び|出し|足し|引き|集め|加え|考え)ます。?$")
SUBJ_FIX = {"計算": "計算できます", "買い足し": "買い足せばOKです / 買い足していきます", "買い": "買えば足ります / 買っていきます", "増や": "増やしていきます",
            "確認": "確認できます / 分かります", "決め": "決まります / 決められます", "出し": "分かります"}
LATER_DOING = re.compile(r"(?:あとから|そのあと|その後|のちに|のちほど|少しずつ|だんだん|徐々に|いずれ)[^。]{0,30}(?:増やし|買い足し|そろえ|用意し|足し|加え)ます。?$")
PARA_MAX_ASK = 3       # ください per page (safety/procedure advice may keep it, but no more than this)
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

    ask = sum(len(re.findall(r"ください", s)) for s in sents)
    if ask > PARA_MAX_ASK:
        add("S04", f"「ください」が{ask}回あります(安全・手続きの案内だけにして、3回まで)。", "ください")
    mash = sum(len(re.findall(r"ましょう", s)) for s in sents)
    if mash > 2:
        add("S04", f"「ましょう」が{mash}回あります(呼びかけが続くと強いられる感じがします。2回まで)。", "ましょう")

    # S10: a range of N+1 values (0..N) against a stated count of types
    blob = "\n".join(body)
    rng = re.search(r"0[〜~ー-](\d{1,2})", blob)
    cnt = re.search(r"(\d{1,2})(?:つの種類|種類)", blob + "\n".join(h for _, h in heads))
    if rng and cnt and int(rng.group(1)) != int(cnt.group(1)):
        add("S10", f"数の範囲(0〜{rng.group(1)})と種類の数({cnt.group(1)}種類)が合いません。", rng.group(0))
    return out
