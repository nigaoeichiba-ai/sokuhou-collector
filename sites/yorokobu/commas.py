"""Fewer 読点: a conservative pass that takes out the commas that sit after a case particle inside a short phrase ("渡す日と、食べる日を、決める" -> "渡す日と食べる日を決める").

A comma stays where a reader breathes: after a topic (は), a conjunction or a clause ending (て、ので、が、し、ば、たら、なら), after an opening word (たとえば、一方で), between the items
of a list, and in a sentence long enough to need one.  Used on the text editors write (features, daily picks); `density` is what the gate looks at.

    python -m sites.yorokobu.commas show  <file.json> ...      # the changes it would make, as before/after
    python -m sites.yorokobu.commas apply <file.json> ...      # write them (string values only)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# a comma right after one of these (a case particle or a particle-like end of a noun phrase) is a candidate
AFTER = ("と", "や", "を", "に", "へ", "の", "から", "まで", "より", "も")
# a phrase this short after the comma (up to the next comma or full stop) is not worth a break of its own
SHORT = 18
MIN_LEN = 24                   # a sentence shorter than this keeps its commas as they are


TOPIC = 8                      # a topic this short ("この商品は") needs no comma after it when the rest is short too
TOPIC_REST = 24


def lighten_sentence(s: str, topics: bool = True) -> str:
    """One sentence (ending in 。 or not) with the particle commas of short phrases taken out; a comma that a long sentence needs stays (the last one in a run longer than 40 characters)."""
    if "、" not in s or len(s) < MIN_LEN:
        return s
    parts = s.split("、")                                      # the text between commas
    out = parts[0]
    for i in range(1, len(parts)):
        before, after = parts[i - 1], parts[i]
        seg_after = re.split(r"[、。]", after)[0]
        particle = any(before.endswith(p) for p in AFTER) and not before.endswith(CONCESSIVE)
        # keep it: a list ("A、B、C" with short bare nouns), an opening word, after は/が/て/し etc., or when the phrase after it is long
        short_noun = len(before) <= 6 and not particle
        parallel = bool(re.match(r".{0,12}?(は|なら|が)", seg_after))         # the next piece has a topic of its own ("花は…に、和菓子は…に、ストールは…"): the comma keeps the parts apart
        topic = topics and before.endswith("は") and len(before.split("。")[-1]) <= TOPIC and len(seg_after) <= TOPIC_REST and i == 1
        if (particle and len(seg_after) <= SHORT and not short_noun and not parallel) or topic:
            out += after
        else:
            out += "、" + after
    return out


SHORT_PHRASE = 36              # a heading, a label, a button or one short sentence: this many characters or fewer
OPENERS = ("いま", "まず", "すぐ", "ここで", "ここから", "先に", "次に", "最後に", "あとで", "そのあと", "つづけて", "たとえば", "昨年", "今年", "去年", "来年", "毎年", "前年", "最近", "普段", "今回", "ふだん")
SHORT_AFTER = ("を", "に", "の", "と", "へ", "も", "や", "で", "から", "まで", "より")
MODIFIER = ("たい", "した", "った", "んだ", "える", "ける", "める", "れる", "せる", "見る", "選ぶ", "探す", "贈る", "使う", "いる")      # the end of a clause that describes the noun after the comma ("最後に添える、一言")
MODIFIED_MAX = 12
VERB_END = "うすつぬぶむるぐただ"                     # the last letter of a verb in the form that describes a noun ("添える、一言"; not く/い: "多く、" is a clause of its own)
NOT_NOUN_END = "うくすつぬぶむるぐいただし"             # a piece that ends like this is not a bare noun phrase (so it is not the noun a clause describes)
CONCESSIVE = ("ても", "でも")                            # "決まっていなくても、" is a clause, not a phrase: the comma stays
SHORT_TOPIC = 20                                  # a sentence of up to 36 characters: a topic this long still needs no comma
NOUNS = ("もの", "こと", "ところ", "とき", "ひと", "ため", "ほう", "もと")       # nouns that end in a letter that is also a particle: "好きなもの、趣味" is a list


def lighten_short(s: str) -> str:
    """A short phrase needs no breath: "だれに、贈りますか?" -> "だれに贈りますか?", "いま、準備したいイベント" -> "いま準備したいイベント", "数字で見る、贈り物" -> "数字で見る贈り物".
    A comma stays between the bare nouns of a list, and after a noun that opens a title ("クリスマス、みんなは…")."""
    if "、" not in s or len(s) > SHORT_PHRASE:
        return s
    parts = s.split("、")
    out = parts[0]
    for i in range(1, len(parts)):
        before, after = parts[i - 1], parts[i]
        head = before.split("。")[-1]
        drop = ((any(head.endswith(p) for p in SHORT_AFTER) and not head.endswith(NOUNS + CONCESSIVE)) or head in OPENERS or head.endswith(OPENERS) and len(head) <= 6
                or (head.endswith("は") and len(head) <= SHORT_TOPIC + 1) or (head.endswith("て") and len(head) >= 3)
                or head.endswith("のうち")
                or (head.endswith(MODIFIER) and len(after.split("。")[0]) <= MODIFIED_MAX and not any(c in after for c in "はがをにでとも"))
                or (head[-1:] in VERB_END and not head.endswith(NOUNS) and len(head) >= 3 and 0 < len(after.split("。")[0]) <= MODIFIED_MAX
                    and after.split("。")[0][-1:] not in NOT_NOUN_END and not any(c in after for c in "はがをにでとも")))
        if drop and after:
            out += after
        else:
            out += "、" + after
    return out


def lighten(text: str) -> str:
    """Every sentence of a text (a short one with the short-phrase rule, a long one with the sentence rule)."""
    out = []
    for x in re.split(r"(?<=。)", text):
        if len(x) > SHORT_PHRASE:
            x = lighten_sentence(x)
        out.append(lighten_short(x) if len(x) <= SHORT_PHRASE else x)             # a sentence that became short by the first rule is a short one: the second rule, so the result is stable
    return "".join(out)


def density(text: str) -> float:
    """Commas per 100 characters (spaces not counted)."""
    t = re.sub(r"\s+", "", text)
    return t.count("、") / len(t) * 100 if t else 0.0


def walk(o, fn):
    if isinstance(o, str):
        return fn(o)
    if isinstance(o, dict):
        return {k: (v if k in ("slug", "date", "ref", "img", "url", "verified") else walk(v, fn)) for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v, fn) for v in o]
    return o


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("show", "apply"):
        print(__doc__)
        return 2
    for f in argv[1:]:
        p = Path(f)
        d = json.loads(p.read_text(encoding="utf-8"))
        new = walk(d, lighten)
        before, after = json.dumps(d, ensure_ascii=False), json.dumps(new, ensure_ascii=False)
        print(f"{p.name}: commas {before.count('、')} -> {after.count('、')}")
        if argv[0] == "apply" and before != after:
            p.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
