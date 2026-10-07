"""Content factory of よろこぶプレゼント: grows the site every day without anybody asking for it.

    python -m sites.yorokobu.factory status
    python -m sites.yorokobu.factory brief themes   --n 6 --out BRIEF.md --answer ANSWER.json
    python -m sites.yorokobu.factory brief articles --n 3 --out BRIEF.md --answer ANSWER.json
    python -m sites.yorokobu.factory merge themes   ANSWER.json
    python -m sites.yorokobu.factory merge articles ANSWER.json

A session (Claude, started on a schedule; see sokuhou-sites/docs/FACTORY_PLAYBOOK.md) writes a brief, hands it to Codex (`codex exec`), validates what
comes back with `merge` (the quality gates in quality.py: calm copy, no claims, no repeats, real search queries) and commits.  The deploy then builds the
new pages; a theme whose search finds too few products is simply not published (build.py MIN_THEME_ITEMS).  `merge` exits 1 and prints every problem when
something is wrong, so the problems can go back to Codex.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import content as ct  # noqa: E402
from sites.yorokobu import quality  # noqa: E402

CONTENT = ct.CONTENT_DIR
INSPIRATION = """
Angles to draw from (these are only seeds; invent new ones, combine them, go beyond them, and avoid anything the site already covers):
- life situations: 手土産, 持ち寄りパーティー, 旅行のおみやげ, お見舞い, 引っ越しのあいさつ, 同窓会, 発表会, 試験前の応援, 単身赴任, 帰省, 初対面の相手
- problems to solve: 何も思いつかない, 予算が少ない, 遠方で渡せない, 配送日を指定したい, 相手の好みが分からない, 受け取る人が多い, 荷物になりたくない, お返しを気にさせたくない
- constraints: 軽い, 小さい, 宅配ボックスに入る, 賞味期限が長い, アレルギー配慮, 持ち帰りしやすい, 手入れが簡単, 場所を取らない, ひとり暮らし向き
- lifestyles and personalities: 在宅ワーク, 早起き, 夜型, 運転が多い, 立ち仕事, 読書家, 倹約家, 凝り性, ミニマリスト, 収集家
- seasons and weather: 梅雨, 猛暑, 寒波, 花粉, 台風の備え, 夜長, 新生活, 年度末
- relationships and ages: 新社会人, 転勤する人, 新米パパママ, 定年後, 一人暮らしを始めた子, 義実家, ご近所, 習い事の先生, 部活の後輩
- emotions: ありがとう, ごめんね, がんばれ, おつかれさま, 会いたい, 元気でいてね
- kinds of gifts: 手作りキット, 長く使える道具, 一生モノ, 日用品の上質版, 地域の名産, 家族で分けられる物, 写真や名前が入る物
"""
THEME_SPEC = """
{"themes":[{"slug":"ascii-lowercase-hyphens","group":"<an existing group slug, or a NEW one you also describe in "new_groups">","name":"short name 4-12 chars","title":"page title 14-34 chars","lead":"110-220 chars, concrete, calm editorial voice","reasons":["3 items, 38-120 chars"],"how_to_choose":["3 items, 28-110 chars"],"avoid":["2 items 20-70 chars"],"recipient":null,"ideas":[{"label":"2-12 chars","type":"one of: 実用品|食べもの・飲みもの|ファッション小物|癒し・リラックス|思い出・名入れ|体験・お出かけ|趣味・ホビー|おもしろ・サプライズ|子ども向け","query":"Rakuten keyword search, 2-5 words, concrete product nouns plus a gift word","why":"40-90 chars"}],"keywords":["8 short search words"],"tiers":["choose 3-5 of: under3000, 3000-5000, 5000-10000, 10000-20000, over20000"],"map":[[x,y],[x,y],[x,y],[x,y]]}],
 "new_groups":[{"slug":"ascii","name":"group name","blurb":"one sentence, 30-70 chars"}]}
"map" places each of the 4 ideas (same order) on the gift map: x from -2 (used up at once: food, drink, consumable) to 2 (lasts for years), y from -2 (classic, safe) to 2 (unusual, characterful); halves allowed; use the full range and do not put all four at one place.
Exactly 4 ideas per theme (4 DIFFERENT product kinds across price levels), 3 reasons, 3 how_to_choose, 8 keywords. "recipient" is null unless the theme clearly implies one of boyfriend|girlfriend|husband|wife|father|mother|grandfather|grandmother|friend-female|friend-male|colleague|boss|teacher|baby|toddler|child|teen|in-laws. "new_groups" may be empty.
"""
ARTICLE_SPEC = """
{"articles":[{"slug":"ascii-lowercase-hyphens","title":"title 18-40 chars, natural, specific","lead":"110-230 chars","sections":[{"h":"heading 8-22 chars","body":"200-420 chars, concrete: situations, wording to use, what to do and avoid"} x 4-5],"checklist":["3-6 short action items, 12-34 chars"],"faq":[{"q":"14-34 chars","a":"60-140 chars"} x 2-3],"themes":["2-4 slugs chosen ONLY from the theme list below, the ones a reader would want next"]}]}
Do not write a "date" field (it is added automatically).
"""
MESSAGE_SPEC = """
{"messages":[{"occasion":"<an occasion slug from the list below>","intro":"110-240 chars: when and how people write a card or message for this occasion, calm and practical","sets":[{"to":"2-12 chars: who the message is for, e.g. 母へ / 職場の先輩へ / 遠くに住む友人へ","style":"丁寧|やわらかい|ひとこと","lines":["EXACTLY 3 different ready-to-copy messages for this person, each 30-110 chars, natural spoken-written Japanese, complete sentences ending with 。 or !"]} x 5-6 sets with different recipients and a mix of styles],"manners":["3 items, 34-100 chars: wording or habits to avoid on this occasion, or how to word things well"],"closing":["3-4 short closing phrases, 6-24 chars, e.g. 体に気をつけてね。"]}]}
Messages must be usable as they are: they may address the person only as "あなた" or by relation (お母さん, 先輩), never with a placeholder or a name. Do not mention the gift's brand or price. Different sets must sound different (not the same sentence with the relation swapped).
"""
RULES = """
LENGTH CALIBRATION: past answers were consistently about 30% SHORTER than requested because characters are hard to count. Aim for the upper half of every range (write about 40% more than feels necessary), then check a few fields by counting.
HARD RULES: polite です・ます Japanese with varied sentence length; no statistics, surveys, rankings, "調査", "人気", "売れ筋"; no guarantees ("必ず", "絶対", "最高"); no brand or shop names; never mention Rakuten, Amazon, affiliates or AI; no medical or cosmetic-effect claims; no emojis; no stacked abstract nouns; each item reads differently, and nothing may repeat sentences of the existing pages. Products must be physical things you can find on a Japanese shopping site (no tickets, bookings or services). There is no python in your sandbox that you can rely on: count characters yourself while writing.
"""


def _load() -> dict:
    return ct.load(CONTENT)


def _groups_text(c: dict) -> str:
    return "\n".join(f"- {g['slug']}: {g['name']} ({g['blurb']})" for g in c["theme_groups"])


def status() -> None:
    c = _load()
    picks = json.loads((CONTENT / "picks.json").read_text(encoding="utf-8")) if (CONTENT / "picks.json").exists() else {}
    added = sorted(t.get("added", "") for t in c["themes"] if t.get("added"))
    print(f"pairs {len(c['pairs'])}, themes {len(c['themes'])} (factory-added {len(added)}, latest {added[-1] if added else '-'}), "
          f"articles {len(c['articles'])} (latest {c['articles'][0]['date'] if c['articles'] else '-'}), guides {len(c['guides'])}, "
          f"groups {len(c['theme_groups'])}, curated pages {len(picks)}")


def brief(kind: str, n: int, out: Path, answer: Path) -> None:
    c = _load()
    if kind == "themes":
        covered = "\n".join(f"- {t['slug']} | {t['name']} | queries: {', '.join(i['query'] for i in t['ideas'])}" for t in c["themes"])
        text = (f"Content task (workspace-write). Reply in English with a very short report. Write exactly ONE file: {answer.as_posix()} (UTF-8 JSON, ensure_ascii false). "
                f"Do not edit anything else.\n\nSITE: \"よろこぶプレゼント\", a Japanese gift-recommendation site that wants to be THE place to research gifts from every angle, "
                f"with surprising, useful angles no other gift site offers (not the usual rankings and occasion lists). THEME pages start from a feeling, a situation, a problem, "
                f"an interest or a constraint instead of an occasion; each shows 4 product ideas that editors then fill with real products.\n\n"
                f"WRITE {n} NEW theme pages that are clearly different from every covered one below (different angle, different products, different queries).\n"
                f"Existing groups:\n{_groups_text(c)}\n{INSPIRATION}\nFORMAT:{THEME_SPEC}\nCOVERED THEMES (do not repeat; do not reuse these queries):\n{covered}\n{RULES}")
    elif kind == "messages":
        todo = [o for o in c["occasions"] if o["slug"] not in c["messages"]][:n]
        listing = "\n".join(f"- {o['slug']} | {o['name']} | {o['timing']}" for o in todo)
        text = (f"Content task (workspace-write). Reply in English with a very short report. Write exactly ONE file: {answer.as_posix()} (UTF-8 JSON, ensure_ascii false). "
                f"Do not edit anything else.\n\nSITE: \"よろこぶプレゼント\", a Japanese gift site. For each occasion below write the message examples people copy onto a card or send "
                f"with a gift (what they search as \"<occasion> メッセージ 例文\"). Write exactly {len(todo)} entries, one per occasion, using these slugs:\n{listing}\n\n"
                f"FORMAT:{MESSAGE_SPEC}\n{RULES}")
    else:
        covered = "\n".join(f"- {a['slug']} | {a['title']}" for a in c["articles"]) or "(none yet)"
        themes = "\n".join(f"- {t['slug']}: {t['name']}" for t in c["themes"])
        text = (f"Content task (workspace-write). Reply in English with a very short report. Write exactly ONE file: {answer.as_posix()} (UTF-8 JSON, ensure_ascii false). "
                f"Do not edit anything else.\n\nSITE: \"よろこぶプレゼント\", a Japanese gift-recommendation site. We publish READING ARTICLES that help people before they choose a gift: "
                f"practical, specific, written like a thoughtful Japanese editor (not SEO filler): how to ask about someone's taste without being obvious, how to hand a gift over, "
                f"what to write on a card, sending to someone far away, workplace gift manners, returning a gift, handling a gift you dislike, budget thinking, wrapping and noshi basics, "
                f"making a small gift feel special, gifts for people who say 'nothing needed', and anything else a person planning a gift would truly want to know.\n\n"
                f"WRITE {n} NEW articles on topics clearly different from the covered ones.\nFORMAT:{ARTICLE_SPEC}\nEXISTING ARTICLES (do not repeat):\n{covered}\n\n"
                f"THEME PAGES you may link to (use ONLY these slugs):\n{themes}\n{RULES}")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"brief written to {out}; Codex must write {answer}")


def retry_brief(kind: str, answer: Path, out: Path) -> None:
    """A brief that hands the refused answer back with the validator's problems; Codex writes the corrected, complete file next to it."""
    probs = answer.with_suffix(".problems.txt").read_text(encoding="utf-8")
    fixed = answer.with_name(answer.stem + "_fixed.json")
    text = (f"Content task (workspace-write). Reply in English with a very short report. Read {answer.as_posix()} (your earlier answer) and write the CORRECTED, COMPLETE file to "
            f"{fixed.as_posix()} (UTF-8 JSON, ensure_ascii false, same format). Do not edit anything else.\n\nThe validator refused it for these reasons:\n{probs}\n\n"
            f"Fix every problem: lengths below the minimum mean you must write MORE (add concrete detail, not filler); keep what was fine; keep slugs. Do not shorten anything else.\n{RULES}")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"retry brief written to {out}; Codex must write {fixed}")


def problems_themes(c: dict, items: list[dict], extra_groups: list[dict]) -> list[str]:
    groups = {g["slug"] for g in c["theme_groups"]} | {g["slug"] for g in extra_groups}
    known_q = {i["query"] for t in c["themes"] for i in t["ideas"]}
    known_s = {t["slug"] for t in c["themes"]} | {p for p in ()}
    out: list[str] = []
    new_q: set[str] = set()
    for t in items:
        out += quality.theme_problems(t, groups, known_q | new_q, known_s)
        new_q |= {i["query"] for i in t.get("ideas", [])}
        known_s.add(t.get("slug", ""))
    texts = [" ".join([t["lead"], *t["reasons"], *t["how_to_choose"]]) for t in c["themes"]] + [" ".join([t["lead"], *t["reasons"], *t["how_to_choose"]]) for t in items if t.get("lead")]
    out += [f"repeated sentence: {s[:40]}" for s in quality.repeated_sentences(texts)]
    return out


def merge_themes(answer: dict, today: date) -> tuple[int, list[str]]:
    c = _load()
    items = answer.get("themes", [])
    extra = answer.get("new_groups", [])
    probs = problems_themes(c, items, extra)
    if probs:
        return 0, probs
    if extra:
        path = CONTENT / "theme_groups.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"groups": []}
        have = {g["slug"] for g in data["groups"]} | {g["slug"] for g in c["theme_groups"]}
        data["groups"] += [g for g in extra if g["slug"] not in have]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    path = CONTENT / "themes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    tags_path = CONTENT / "map_tags.json"
    tags = json.loads(tags_path.read_text(encoding="utf-8")) if tags_path.exists() else {}
    for t in items:
        t.setdefault("avoid", [])
        t["recipient"] = t.get("recipient") or None
        t["added"] = today.isoformat()
        dots = t.pop("map", None)
        if dots and len(dots) == 4 and all(len(d) == 2 and all(-2 <= float(v) <= 2 for v in d) for d in dots):
            tags[f"theme-{t['slug']}"] = dots
        data["themes"].append(t)
    tags_path.write_text(json.dumps(tags, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    _load()   # the loader's own cross-reference checks
    return len(items), []


def merge_articles(answer: dict, today: date) -> tuple[int, list[str]]:
    c = _load()
    items = answer.get("articles", [])
    theme_slugs = {t["slug"] for t in c["themes"]}
    known = {a["slug"] for a in c["articles"]}
    probs: list[str] = []
    for a in items:
        a["date"] = today.isoformat()
        probs += quality.article_problems(a, theme_slugs, known)
        known.add(a.get("slug", ""))
    old = [" ".join(s["body"] for s in a["sections"]) for a in c["articles"]] + [" ".join(g_s["body"] for g_s in g["sections"]) for g in c["guides"].values()]
    probs += [f"repeated sentence: {s[:40]}" for s in quality.repeated_sentences(old + [" ".join(s["body"] for s in a["sections"]) for a in items if a.get("sections")])]
    if probs:
        return 0, probs
    path = CONTENT / "articles.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"articles": []}
    data["articles"] += items
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    _load()
    return len(items), []


def merge_messages(answer: dict, today: date) -> tuple[int, list[str]]:
    c = _load()
    items = answer.get("messages", [])
    occ = {o["slug"] for o in c["occasions"]}
    known = set(c["messages"])
    probs: list[str] = []
    for m in items:
        probs += quality.message_problems(m, occ, known)
        known.add(m.get("occasion", ""))
    old = [ln for e in c["messages"].values() for s in e["sets"] for ln in s["lines"]]
    new = [ln for m in items for s in m.get("sets", []) for ln in s.get("lines", [])]
    dup = set(old) & set(new)
    probs += [f"a message repeats an existing one: {x[:30]}" for x in dup]
    if probs:
        return 0, probs
    path = CONTENT / "messages.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"messages": []}
    for m in items:
        m["added"] = today.isoformat()
    data["messages"] += items
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    _load()
    return len(items), []


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    b = sub.add_parser("brief")
    b.add_argument("kind", choices=["themes", "articles", "messages"])
    b.add_argument("--n", type=int, default=5)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--answer", type=Path, required=True)
    m = sub.add_parser("merge")
    m.add_argument("kind", choices=["themes", "articles", "messages"])
    m.add_argument("file", type=Path)
    m.add_argument("--today", default=date.today().isoformat())
    r = sub.add_parser("retry", help="write a brief that sends a refused answer back to Codex with the problems")
    r.add_argument("kind", choices=["themes", "articles", "messages"])
    r.add_argument("file", type=Path)
    r.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "status":
        status()
    elif a.cmd == "brief":
        brief(a.kind, a.n, a.out, a.answer)
    elif a.cmd == "retry":
        retry_brief(a.kind, a.file, a.out)
    else:
        answer = json.loads(a.file.read_text(encoding="utf-8"))
        n, probs = (merge_themes if a.kind == "themes" else merge_articles)(answer, date.fromisoformat(a.today))
        problems_file = a.file.with_suffix(".problems.txt")
        if probs:
            problems_file.write_text("\n".join(probs), encoding="utf-8")
        else:
            problems_file.unlink(missing_ok=True)
        for p in probs:
            print(p)
        print(f"merged {n} {a.kind}" if not probs else f"REFUSED: {len(probs)} problems")
        sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
