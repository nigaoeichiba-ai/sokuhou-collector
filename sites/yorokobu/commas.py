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
        particle = any(before.endswith(p) for p in AFTER)
        # keep it: a list ("A、B、C" with short bare nouns), an opening word, after は/が/て/し etc., or when the phrase after it is long
        short_noun = len(before) <= 6 and not particle
        topic = topics and before.endswith("は") and len(before.split("。")[-1]) <= TOPIC and len(seg_after) <= TOPIC_REST and i == 1
        if (particle and len(seg_after) <= SHORT and not short_noun) or topic:
            out += after
        else:
            out += "、" + after
    return out


def lighten(text: str) -> str:
    return "".join(lighten_sentence(x) for x in re.split(r"(?<=。)", text))


def density(text: str) -> float:
    """Commas per 100 characters (spaces not counted)."""
    t = re.sub(r"\s+", "", text)
    return t.count("、") / len(t) * 100 if t else 0.0


def walk(o, fn):
    if isinstance(o, str):
        return fn(o) if len(o) >= MIN_LEN else o
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
