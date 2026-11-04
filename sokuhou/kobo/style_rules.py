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

LABELS = {"S01": "「並べる」の言い方", "S02": "「置く」(商品・案内)", "S03": "「扱う」の言い方", "S04": "強い言い方・「ください」の多さ",
          "S05": "題・見出しの抽象的な動詞", "S06": "動詞止めの見出しに目的語がない", "S07": "「へ」止めの見出し", "S08": "名詞の列挙が文になっていない",
          "S09": "何の数・目安・量か分からない", "S10": "数の範囲と種類数が合わない", "S11": "表の案内文(「〜の行」・命令形)", "S12": "「家族の人」「人数の行」", "S13": "「数える」に「何を」がない", "S14": "助詞で終わる文・見出し", "S15": "「所」「ところ」(場所でないもの)", "S16": "「見つけてみませんか」", "S17": "「どこ」(場所でないもの)", "S18": "個数でないものを「数える」"}

ABSTRACT_HEAD = re.compile(r"(?:数え|確かめ|確認し|調べ|見直し|考え|見)(?:て(?:み)?)?(?:よう|ましょう)|数えて|確かめて|てみよう|てみましょう|てみる[!?！？]?$")
PARA_MAX_ASK = 3        # ください per page (safety/procedure advice may keep it, but no more than this)
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
        if kind == "見出し" and last and VERB_END.search(last) and "を" not in last and not last.endswith(("ください", "ましょう")):
            add("S06", "見出しが動詞で終わっていて、何を・どうするかの「何を」がありません。名詞止めか「〜を〜する」の形にしてください。", h)
        if h.rstrip().endswith("へ"):
            add("S07", "見出しが「へ」で終わっています。動詞まで言い切るか、名詞止めにしてください。", h)

    for s in sents:
        if re.search(r"並べ|並んで|並び", s) and "並べ替" not in s:
            add("S01", "物や数字を「並べる」は不自然です。「書き込む」「載せる」「比べる」などにしてください。", s)
        if re.search(r"(?:商品|案内|リンク|カード|一覧|ページ)(?:を|も)?(?:ここに|下に|横に)?(?:置い|置く|置き)", s):
            add("S02", "商品や案内を「置く」は不自然です。「載せる」「紹介する」にしてください。", s)
        if "扱" in s:
            add("S03", "「扱う」は何をするのか分かりにくい言い方です。記事の内容なら「取り上げる」「紹介する」、物なら「使い方」「捨て方」など具体的に。", s)
        if re.search(r"てみてください|しなさい|べき|しないと", s):
            add("S04", "読み手に強いる言い方です。「〜すると〜が分かります」「〜できます」「〜するのがおすすめです」にしてください。", s)
        if NOUN_LIST.match(s) and not re.search(r"です|ます|ない|した|する|ある", s):
            add("S08", "名詞を並べただけで、文として終わっていません。「〜の七つです」のように言い切ってください。", s)
        if re.search(r"(?:^|[、。 　はをにがでとも])(?:その|この|あの)?(?:数|目安)(?:を|は|が|と|に|で)", s) or re.search(r"(?:必要な|いまある|今ある|そろっている|それぞれの)(?:数|量)(?!の|だけ)", s):
            add("S09", "「数」「目安」「量」が、何の数かを言っていません。対象を入れてください。", s)
        if re.search(r"の行", s) and re.search(r"見て|探して|確かめて", s):
            add("S11", "「〜の行」は何の人数・何の行か分かりにくく、「見てください」は何が分かるかを言っていません。「自分の家の人数の行を見ると、〜が分かります」の形に。", s)
        if re.search(r"家族の人(?!数)|(?<!家の)(?<!自分の家の)人数の行", s):
            add("S12", "「家族の人」「人数の行」は不自然・不明です。「家族がいる人」「家の人数の行」などにしてください。", s)

    # S13 数える/確かめる without an object in the same sentence; S14 a sentence or heading that stops on a particle
    for s in sents + [h for _, h in heads if h]:
        if re.search(r"数え(?:る|て|ます|られます|ておきます|ておく)", s) and not re.search(r"を[^。、]{0,40}数え", s) and not re.search(r"(?:数|量|回数|在庫)が", s):
            add("S13", "「数える」に、何を、がありません。「〜を数える」の形にしてください(題・見出しの「数える」だけは、S05)。", s)
        if re.search(r"[でにをはがもとのへ][。!！]?$", s.strip()) and not re.search(r"(?:ので|ため|とも|のに)[。]?$", s.strip()):
            add("S14", "文や見出しが助詞で終わっていて、述語がありません。", s)

    # S15-S18 place-words used for things; 数える for things that are not counts (the owner, 2026-11-04)
    for s in sents + [h for _, h in heads if h]:
        if re.search(r"(?:足りない|直す|気になる|見つかる|困る|迷る|迷う|引っかかる|分からない|大切な|大事な|注意が必要な)(?:所|ところ|箇所)", s):
            add("S15", "場所でないもの・ことに「所」「ところ」「箇所」は不自然です。「足りないもの」「直す点」「気になる点」のように具体的な名詞にしてください。", s)
        if re.search(r"見つけて(?:み)?ませんか", s):
            add("S16", "「見つけてみませんか」は不自然です。「何か、確認しませんか」「そろっているか確認しませんか」などにしてください。", s)
        if re.search(r"どこ(?:から|を|が|は|も)", s) and not re.search(r"場所|置|探|地域|住|店|窓口|ページ|家の中|部屋|地図|県|市|町|ある|いる|行", s):
            add("S17", "場所でないものに「どこ」「どこから」は使えません。「何から」「どれを」にしてください。", s)
        if re.search(r"(?:種類|備え|グッズ|項目|もの)を[^。、]{0,14}数え", s):
            add("S18", "物の個数でないものを「数える」は普通は使いません。「見直す」「棚卸しする」「確認する」にしてください(個数のときだけ「数」「何個」)。", s)

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
