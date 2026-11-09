# -*- coding: utf-8 -*-
"""見直し稿(2026-11-09, ルール .3 訂正反映)を shiken のソースに適用する。
使い方: python sites/shiken/apply_review_rev3.py [--write]
 - 取り下げ(原文のまま)の文は飛ばす。
 - 原文が、ソース内でちょうど1か所に見つかったものだけ置き換える(0件・複数は一覧に出す)。
"""
import os
import re
import sys

SRC = "H:/マイドライブ/sokuhou/inbox/見直し稿_新ルール対応_2026-11-09.md"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
WRITE = "--write" in sys.argv

lines = open(SRC, encoding="utf-8").read().split("\n")

withdrawn = set()
rows = []  # (page, old, new)
page = None
mode = None
for ln in lines:
    if ln.startswith("### 取り下げる差し替え"):
        mode = "wd"
        continue
    if ln.startswith("### 言い換えでは済ませない"):
        mode = "keep"
        continue
    if ln.startswith("## 追記（2026-11-09、オーナー"):
        mode = "add"
        continue
    m = re.match(r"^## /([^/]+)/$", ln)
    if m and mode is None:
        page = m.group(1)
        continue
    if ln.startswith("## 別表"):
        mode = "label"
        continue
    if ln.startswith("## ゲートの記録"):
        mode = "gate"
        continue
    if mode == "wd" or mode == "keep":
        m = re.match(r"^- /([^/]+)/：(.+?)( → .*)?$", ln)
        if m:
            withdrawn.add((m.group(1), m.group(2).strip()))
        continue
    if ln.startswith("|") and mode is None and page:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] not in ("原文", "---") and not cells[0].startswith("---"):
            rows.append((page, cells[0], cells[1]))
    elif ln.startswith("|") and mode == "add":
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] not in ("ページ",) and not cells[0].startswith("---"):
            new = cells[2]
            rows.append((cells[0], cells[1], new))
    elif ln.startswith("|") and mode == "label":
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] not in ("現在",) and not cells[0].startswith("---"):
            rows.append(("LABEL", cells[0], cells[1]))

files = []
for dp, dn, fn in os.walk(ROOT):
    rel_dp = os.path.relpath(dp, ROOT).replace(os.sep, "/")
    if "__pycache__" in dp or rel_dp.split("/")[0] in ("docs", "additions", "tools", "articles", "data", "assets"):
        continue
    for n in fn:
        if n.endswith((".json", ".py", ".html", ".md", ".txt", ".js", ".css")) and n != os.path.basename(__file__):
            files.append(os.path.join(dp, n))
# サイト共通のテンプレートも
extra = os.path.join(ROOT, "..", "..", "sokuhou")
texts = {}
for f in files:
    try:
        texts[f] = open(f, encoding="utf-8").read()
    except Exception:
        pass

applied = 0
skipped_wd = 0
problems = []
ALT = [("確かめてください", "(?:確かめてください|ご確認ください|確認してください|お確かめください|確認しておきましょう|調べておきましょう|見ておきましょう|見ておいてください)"),
       ("確かめます", "(?:確かめます|確認します|確認しておきましょう|見ておきましょう)"),
       ("読んでください", "(?:読んでください|お読みください)"),
       ("で見る", "(?:で見る|で調べる|で探す)"),
       ("時刻も", "(?:時刻も|時刻にも)"),
       ("見ます", "(?:見ます|確認できます|確認します|見ておきましょう)"),
       ("置きます", "(?:置きます|入れます)"),
       ("見ると", "(?:見ると|比べると)")]


def rel(f):
    return os.path.relpath(f, ROOT).replace(os.sep, "/")


def candidates(old_t):
    pat = re.escape(old_t)
    for k, alt in ALT:
        pat = pat.replace(re.escape(k), alt)
    yield re.compile(pat)
    if old_t.endswith("。"):
        for k in ("確かめてください", "確かめます", "読んでください", "見ます", "置きます", "読みやすいです", "で見ると", "を見ます"):
            i = old_t.find(k)
            if i >= 10:
                yield re.compile(re.escape(old_t[:i]) + '[^。"\n]{0,45}。')
                break


# オーナー承認済みの Gemini 版(docs/muse-text-replacements-2026-11-09.md の14件)には触れない
OWNER_FINAL = [
    "受験票の届き方と当日の持ち物は、選んだ方式の案内で確かめてください。",
    "あわせて確かめます。",
    "受験票が届いたら、氏名と試験場を確かめてください。",
    "期間を過ぎると見られなくなるので、必要な方は期間内に確かめてください。",
    "締切は、日付だけでなく時刻も確かめてください。",
    "この表は、共通テスト、国公立大学、公立高校の順に追うと読みやすいです。",
    "高校を受ける方は、お住まいの都道府県の学力検査の日を確かめます。",
    "具体例で見ます。",
    "郵送の方法の欄も確かめてください。",
    "手続きには期限があるので、結果と一緒に案内も確かめてください。",
    "令和8年度の流れで見ると",
    "数字で見る宅建",
    "申込は段取りの最初に置きます。",
]
for page, old, new in rows:
    if any(k in old for k in OWNER_FINAL):
        skipped_wd += 1
        continue
    if (page, old) in withdrawn:
        skipped_wd += 1
        continue
    if page == "LABEL":
        old_t, new_t = old, new
    else:
        old_t = old
        new_t = "" if new.startswith("（") else new
    own = [f for f in texts if rel(f) == f"content/{page}.json"]
    if page == "LABEL":
        # 部品の文字: 引用符で囲まれた文字列そのものだけ(本文の途中は触らない)
        lab_old = re.escape(old_t).replace(re.escape("で見る"), "(?:で見る|で調べる)")
        rxl = re.compile('"' + lab_old + '"')
        n = 0
        for f in list(texts):
            if f.endswith(".md"):
                continue
            texts[f], c = rxl.subn('"' + new_t + '"', texts[f])
            n += c
            if c and WRITE:
                open(f, "w", encoding="utf-8", newline="").write(texts[f])
        if n:
            applied += 1
        else:
            problems.append(("なし", page, old))
        continue
    scope = own if own else [f for f in texts if not f.endswith(".md")]
    found = []  # (file, start, end, exact)
    for rx in candidates(old_t):
        for f in scope:
            for m in rx.finditer(texts[f]):
                found.append((f, m.start(), m.end(), m.group(0)))
        if found:
            break
    if not found:
        problems.append(("なし", page, old))
        continue
    if len({x[3] for x in found}) > 1:
        problems.append(("複数の形", page, old + "  => " + " / ".join({x[3] for x in found})))
        continue
    if not own:
        problems.append(("対象ページの専用ファイルなし(全体で置換)", page, old))
    # 正本は gen/*.py(content/*.json は、gen が毎回作り直す出力。テストやビルドで上書きされる)。
    # 現在の文(content の実物)を、gen/*.py・site.json の中で探して置き換える。ほかのページと同じ文が当たったら止めて報告する。
    ex = found[0][3]
    src_files = [f for f in texts if (rel(f).startswith("sites/shiken/gen/") or rel(f) == "site.json" or rel(f).startswith("gen/")) and not f.endswith(".md")]
    total = sum(texts[f].count(ex) for f in src_files)
    if total == 0:
        problems.append(("gen に見当たらない(文を組み立てている?)", page, old + "  => " + ex))
        continue
    if total > 1 and len(ex) < 30:
        problems.append((f"gen に{total}か所(短い文なので止めた)", page, old + "  => " + ex))
        continue
    for f in src_files:
        texts[f] = texts[f].replace(ex, new_t)
    applied += 1

# 削除で空になった段落を取り除く
for f in list(texts):
    if f.endswith(".md"):
        continue
    t = texts[f]
    t2 = re.sub(r',\s*""\s*(?=\])', "", t)
    t2 = re.sub(r'""\s*,\s*', "", t2) if f.endswith(".json") else t2
    texts[f] = t2

if WRITE:
    for f, t in texts.items():
        if not f.endswith(".md"):
            if open(f, encoding="utf-8").read() != t:
                open(f, "w", encoding="utf-8", newline="").write(t)

print(f"表の行 {len(rows)} / 取り下げで飛ばした {skipped_wd} / 適用 {applied} / 要確認 {len(problems)}")
for kind, page, old in problems:
    print(f"[{kind}] /{page}/ {old}")
