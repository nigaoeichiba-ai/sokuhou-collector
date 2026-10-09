"""Quality gates for editorial content, shared by the unit tests and the content factory (sites/yorokobu/factory.py).

Each function returns a list of problems (empty = fine).  The factory merges new themes and articles only when this list is empty, so nobody has
to read them before they go live: calm copy, no claims we cannot back up, no repeats of what the site already says.
"""
from __future__ import annotations

import re

FORBIDDEN_WORDS = ["調査", "%", "％", "人気", "ランキング", "No.1", "必ず", "絶対", "最高", "楽天", "アフィリ", "AI", "1位"]
TEMPLATE_PHRASES = ["視点を合わせると", "生活の中で出番がある", "節目に、相手をよく見て", "迷ったら普段の使い方に近いもの",
                    "好みが分からないときは高価さより", "使う場面が浮かぶ品なら", "候補を絞りやすくなります"]
TYPES = ["実用品", "食べもの・飲みもの", "ファッション小物", "癒し・リラックス", "思い出・名入れ", "体験・お出かけ", "趣味・ホビー", "おもしろ・サプライズ", "子ども向け"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[。!?!?]", text) if len(s) >= 25]


def _words(blob: str) -> list[str]:
    return [w for w in FORBIDDEN_WORDS + TEMPLATE_PHRASES if w in blob] + (["emoji"] if EMOJI.search(blob) else [])


# ---- Japanese style (the rules are in sokuhou-sites/docs/STYLE_GUIDE_YOROKOBU_CODEX_2026-10-09.md and the owner's note that the site's Japanese felt off)
INTERNAL_WORDS = ["切り口", "ソムリエ", "ナビゲーター", "見立て", "ギフトマップ", "コンシェルジュ", "ガチャ"]     # editors' jargon; the reader does not know them
YOUNG_TONE = ["選んでね", "見つけたよ", "どれがよさそう", "ぜんぶ", "わくわく", "いっしょに見つけ", "してね。", "だよ。"]       # a gift site for adults does not talk like this
CLAIMS_WITHOUT_BASIS = ["よく読まれている", "人気の", "売れ筋"]
PARTICLE_COMMA = re.compile(r"[をにでとがはもへの]、")        # 「3週間前に、カレンダーで、お知らせします」: a comma after every short phrase
MAX_YASUI = 4                                                    # 「〜しやすい」 is the easy way to end a reason: at most 4 in one item, and at most 2 sentences ending 「〜やすいです。」
MAX_SENTENCE = 100


def language_problems(blob: str, slug: str, casual: bool = False) -> list[str]:
    """Style problems in one item's text.  `casual` (card messages written in the sender's voice) allows ね/よ endings."""
    out = [f"{slug}: internal word {w}" for w in INTERNAL_WORDS if w in blob]
    out += [f"{slug}: claim without basis {w}" for w in CLAIMS_WITHOUT_BASIS if w in blob]
    if not casual:
        out += [f"{slug}: childish tone {w}" for w in YOUNG_TONE if w in blob]
    for s in re.split(r"(?<=。)", blob):
        if len(PARTICLE_COMMA.findall(s)) >= 3 and len(s) < 80:
            out.append(f"{slug}: a comma after every short phrase: {s[:30]}")
        if len(s) > MAX_SENTENCE:
            out.append(f"{slug}: sentence of {len(s)} characters (split it): {s[:30]}")
    if blob.count("やすい") > MAX_YASUI or blob.count("やすいです。") > 2:
        out.append(f"{slug}: too many 〜やすい ({blob.count('やすい')}); name the concrete reason instead (分けられる, 持ち帰れる, 保管できる)")
    return out


def theme_problems(t: dict, groups: set[str], known_queries: set[str] | None = None, known_slugs: set[str] | None = None) -> list[str]:
    out = []
    slug = t.get("slug", "?")
    for f in ("slug", "group", "name", "title", "lead", "reasons", "how_to_choose", "ideas", "keywords", "tiers"):
        if not t.get(f):
            out.append(f"{slug}: missing {f}")
    if out:
        return out
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        out.append(f"{slug}: slug must be lowercase ascii with hyphens")
    if known_slugs and slug in known_slugs:
        out.append(f"{slug}: slug exists")
    if t["group"] not in groups:
        out.append(f"{slug}: unknown group {t['group']}")
    blob = " ".join([t["title"], t["lead"], *t["reasons"], *t["how_to_choose"], *t.get("avoid", []), *[i["label"] + i["why"] for i in t["ideas"]]])
    out += [f"{slug}: forbidden {w}" for w in _words(blob)]
    out += language_problems(blob, slug)
    if not 75 <= len(t["lead"]) <= 260:
        out.append(f"{slug}: lead length {len(t['lead'])}")
    if not 12 <= len(t["title"]) <= 40:
        out.append(f"{slug}: title length {len(t['title'])}")
    if len(t["reasons"]) != 3 or len(t["how_to_choose"]) != 3 or len(t["ideas"]) != 4 or len(t["keywords"]) != 8:
        out.append(f"{slug}: counts (reasons 3, how_to_choose 3, ideas 4, keywords 8)")
    queries = [i["query"] for i in t["ideas"]]
    if len(set(queries)) != 4:
        out.append(f"{slug}: repeated query")
    if known_queries:
        out += [f"{slug}: query already used elsewhere: {q}" for q in queries if q in known_queries]
    for i in t["ideas"]:
        if i["type"] not in TYPES:
            out.append(f"{slug}: bad type {i['type']}")
        if not 24 <= len(i["why"]) <= 110:
            out.append(f"{slug}: idea why length {len(i['why'])}")
        if not 2 <= len(i["label"]) <= 14:
            out.append(f"{slug}: idea label length {len(i['label'])}")
        if not 2 <= len(i["query"].split()) <= 5:
            out.append(f"{slug}: query should be 2-5 words: {i['query']}")
    return out


def article_problems(a: dict, theme_slugs: set[str], known_slugs: set[str] | None = None) -> list[str]:
    out = []
    slug = a.get("slug", "?")
    for f in ("slug", "title", "lead", "sections", "faq", "themes", "date"):
        if not a.get(f):
            out.append(f"{slug}: missing {f}")
    if out:
        return out
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        out.append(f"{slug}: slug must be lowercase ascii with hyphens")
    if known_slugs and slug in known_slugs:
        out.append(f"{slug}: slug exists")
    blob = " ".join([a["title"], a["lead"], *[s["h"] + s["body"] for s in a["sections"]], *a.get("checklist", []), *[f["q"] + f["a"] for f in a["faq"]]])
    out += [f"{slug}: forbidden {w}" for w in _words(blob)]
    out += language_problems(blob, slug)
    if not 15 <= len(a["title"]) <= 44:
        out.append(f"{slug}: title length {len(a['title'])}")
    if not 80 <= len(a["lead"]) <= 260:
        out.append(f"{slug}: lead length {len(a['lead'])}")
    if not 4 <= len(a["sections"]) <= 6:
        out.append(f"{slug}: sections {len(a['sections'])}")
    for s in a["sections"]:
        if not 140 <= len(s["body"]) <= 480 or not 6 <= len(s["h"]) <= 26:
            out.append(f"{slug}: section '{s['h']}' lengths {len(s['h'])}/{len(s['body'])}")
    if not 2 <= len(a["faq"]) <= 4:
        out.append(f"{slug}: faq {len(a['faq'])}")
    bad = [s for s in a["themes"] if s not in theme_slugs]
    if bad or not 2 <= len(a["themes"]) <= 4:
        out.append(f"{slug}: related themes {a['themes']} (need 2-4 existing ones)")
    return out


MESSAGE_FORBIDDEN = ["調査", "%", "％", "楽天", "アフィリ", "AI", "Amazon", "http", "ランキング", "No.1", "1位", "〇〇様へ、"]
MESSAGE_STYLES = ["丁寧", "やわらかい", "ひとこと"]


def message_problems(m: dict, occasion_slugs: set[str], known: set[str] | None = None) -> list[str]:
    """One occasion's message examples: 5-6 sets of 3 ready-to-copy messages, manners and closing phrases, each within its length range."""
    out = []
    slug = m.get("occasion", "?")
    for f in ("occasion", "intro", "sets", "manners", "closing"):
        if not m.get(f):
            out.append(f"{slug}: missing {f}")
    if out:
        return out
    if slug not in occasion_slugs:
        out.append(f"{slug}: unknown occasion")
    if known and slug in known:
        out.append(f"{slug}: messages exist")
    if not 90 <= len(m["intro"]) <= 280:
        out.append(f"{slug}: intro length {len(m['intro'])}")
    if not 5 <= len(m["sets"]) <= 6:
        out.append(f"{slug}: sets {len(m['sets'])} (need 5-6)")
    lines_seen: list[str] = []
    for s in m["sets"]:
        to = s.get("to", "")
        if not 2 <= len(to) <= 14:
            out.append(f"{slug}: set '{to}' recipient label length {len(to)}")
        if s.get("style") not in MESSAGE_STYLES:
            out.append(f"{slug}: set '{to}' style {s.get('style')} (one of {MESSAGE_STYLES})")
        lines = s.get("lines", [])
        if len(lines) != 3:
            out.append(f"{slug}: set '{to}' has {len(lines)} lines (need 3)")
        for ln in lines:
            if not 24 <= len(ln) <= 130:
                out.append(f"{slug}: '{ln[:14]}...' message length {len(ln)} (24-130)")
            lines_seen.append(ln)
    if len(set(lines_seen)) != len(lines_seen):
        out.append(f"{slug}: a message appears twice")
    if not 3 <= len(m["manners"]) <= 4 or any(not 28 <= len(x) <= 110 for x in m["manners"]):
        out.append(f"{slug}: manners need 3-4 items of 28-110 chars")
    if not 3 <= len(m["closing"]) <= 5 or any(not 5 <= len(x) <= 28 for x in m["closing"]):
        out.append(f"{slug}: closing needs 3-5 phrases of 5-28 chars")
    blob = " ".join([m["intro"], *m["manners"], *m["closing"], *[ln for s in m["sets"] for ln in s.get("lines", [])], *[s.get("to", "") for s in m["sets"]]])
    out += [f"{slug}: forbidden {w}" for w in MESSAGE_FORBIDDEN if w in blob]
    out += language_problems(" ".join([m["intro"], *m["manners"]]), slug)                                           # the site's own voice
    out += language_problems(" ".join([*[ln for s in m["sets"] for ln in s.get("lines", [])], *m["closing"]]), slug, casual=True)   # the sender's voice: ね/よ are fine
    if EMOJI.search(blob):
        out.append(f"{slug}: emoji")
    return out


def repeated_sentences(texts: list[str]) -> list[str]:
    """Long sentences that occur more than once in the given texts (a new text must not copy the site's older ones)."""
    seen: dict[str, int] = {}
    for t in texts:
        for s in set(sentences(t)):
            seen[s] = seen.get(s, 0) + 1
    return [s for s, n in seen.items() if n > 1]
