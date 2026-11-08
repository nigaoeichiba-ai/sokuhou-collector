#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公開ゲート：文章チェック（shiken-nittei.com）

使い方:
    python3 check_text.py <走査するフォルダ> [--report <出力先md>] [--rules <ng_rules.json>]

動作:
    - フォルダ内の .html / .md / .txt をすべて走査する。
    - ハードNGが1件でもあれば、終了コード 1 で終わる。
      デプロイ側は、この終了コードを見て公開を止めること。
    - ソフト対象は件数と箇所を表示する。0件でなくても終了コードは変えないが、
      公開前チェックリストに「確認した」記録がないと公開できない運用にする。
    - 結果は標準出力と、--report 指定時はそのファイルにも書く。
    - --rules で ng_rules.json（ルールのマスター）を指定すると、その内容で走査する。
      指定したのに読めない場合は、終了コード 2（エラー）で終わる＝ゲートは止める側に倒す。
      --rules を付けない場合は、このファイル内の予備リストで走査する（手元確認用）。

ホワイトリスト（支払い手段の名称は「カード」でも対象外）:
    クレジットカード / カード決済
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

# ハードNG：1件でも残っていたら公開不可（終了コード1）
HARD_PATTERNS = [
    ("並びます", r"並びます"),
    ("カード（部品の意味）", r"カード"),
    ("読み物", r"読み物"),
    ("いちばん（ひらがな）", r"いちばん"),
    ("見せます", r"見せます"),
    ("載せます", r"載せます"),
    ("数えました", r"数えました"),
    ("数えています", r"数えています"),
    ("書きました", r"書きました"),
    ("見てください", r"見てください"),
    ("分かります", r"分かります"),
    ("これから来る", r"これから来る"),
    ("入口（作り手の比喩）", r"入口"),
    ("棚（作り手の比喩）", r"棚"),
]

# ソフト対象：パターン集P2（作る側の場面の述語）など、文脈で判断するもの。
# 件数を出し、チェックリストで目視確認の記録を必須にする。
SOFT_PATTERNS = [
    ("〜の人／〜人は など（読者を指す「人」）", r"(の人[はがをにへ]|人は|人が|人を|人へ)"),
    ("出ます（P2候補）", r"出ます"),
    ("決まります（P2候補）", r"決まります"),
    ("載っています（P2候補）", r"載っています"),
    ("並べ（表示の意味でないか確認）", r"並べ"),
    ("載せ（掲載しない等の見出しは可）", r"載せ"),
]

WHITELIST = ["クレジットカード", "カード決済"]
EXTENSIONS = (".html", ".md", ".txt")


def strip_markup(text: str) -> str:
    """HTMLタグとスクリプト・スタイルを落として、本文だけにする。"""
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def scan(root: str, site: str = None):
    hard_hits = []  # (file, pattern_name, excerpt)
    soft_counts = Counter()
    soft_locations = defaultdict(list)
    applied_exceptions = []  # (file, pattern, reason)
    files = []
    for dirpath, _dirs, names in os.walk(root):
        for name in sorted(names):
            if name.lower().endswith(EXTENSIONS):
                files.append(os.path.join(dirpath, name))
    for path in sorted(files):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
        text = strip_markup(raw)
        for w in WHITELIST:
            text = text.replace(w, "〇〇")
        rel = os.path.relpath(path, root)
        # サイト別例外：--site が一致する例外だけ、その箇所を走査対象から外す
        if site:
            for exc in EXCEPTIONS:
                if exc.get("site") not in (site, "*"):
                    continue
                pages = exc.get("pages")
                if pages and not any(p in rel for p in pages):
                    continue
                pat = exc.get("pattern", "")
                if not pat:
                    continue

                def _blank(m, exc=exc, rel=rel):
                    applied_exceptions.append((rel, exc.get("pattern"), exc.get("reason", "")))
                    return "〇" * max(1, len(m.group(0)))

                text = re.sub(pat, _blank, text)
        for label, pat in HARD_PATTERNS:
            for m in re.finditer(pat, text):
                start = max(0, m.start() - 25)
                excerpt = text[start : m.end() + 25].replace("\n", " ")
                hard_hits.append((rel, label, excerpt))
        for label, pat in SOFT_PATTERNS:
            for m in re.finditer(pat, text):
                soft_counts[label] += 1
                if len(soft_locations[label]) < 50:
                    start = max(0, m.start() - 25)
                    excerpt = text[start : m.end() + 25].replace("\n", " ")
                    soft_locations[label].append((rel, excerpt))
    return files, hard_hits, soft_counts, soft_locations, applied_exceptions


EXCEPTIONS = []


def load_rules(path):
    """ng_rules.json を読み、(hard, soft, whitelist, version, exceptions) を返す。失敗したら例外。"""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    hard = [(item["label"], item["pattern"]) for item in data["hard"]]
    soft = [(item["label"], item["pattern"]) for item in data.get("soft", [])]
    whitelist = data.get("whitelist", [])
    version = data.get("version", "unknown")
    exceptions = data.get("exceptions", [])
    return hard, soft, whitelist, version, exceptions


def main() -> int:
    global HARD_PATTERNS, SOFT_PATTERNS, WHITELIST, EXCEPTIONS
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    report_path = None
    rules_path = None
    site = None
    rules_version = "embedded (予備リスト)"
    if "--report" in sys.argv:
        idx = sys.argv.index("--report")
        if idx + 1 < len(sys.argv):
            report_path = sys.argv[idx + 1]
    if "--rules" in sys.argv:
        idx = sys.argv.index("--rules")
        if idx + 1 < len(sys.argv):
            rules_path = sys.argv[idx + 1]
    if "--site" in sys.argv:
        idx = sys.argv.index("--site")
        if idx + 1 < len(sys.argv):
            site = sys.argv[idx + 1]
    if not args:
        print("使い方: python3 check_text.py <フォルダ> [--report <出力先md>] [--rules <ng_rules.json>] [--site <サイトID>]")
        return 2
    if rules_path:
        try:
            HARD_PATTERNS, SOFT_PATTERNS, WHITELIST, rules_version, EXCEPTIONS = load_rules(rules_path)
            rules_version = f"{rules_version}（{rules_path}）"
        except Exception as exc:  # 読めないルールで通さない（止める側に倒す）
            print(f"ルールファイルを読めませんでした: {rules_path}: {exc}")
            print("ゲートは安全側に倒し、公開不可として終了します。")
            return 2
    root = args[0]
    files, hard_hits, soft_counts, soft_locations, applied_exceptions = scan(root, site=site)

    lines = []
    lines.append("# 文章チェック結果（公開ゲート）")
    lines.append("")
    lines.append(f"- 走査したファイル数: {len(files)}")
    lines.append(f"- 使ったルール: {rules_version}")
    lines.append(f"- 対象サイト: {site if site else '（指定なし＝例外は適用しない）'}")
    lines.append(f"- ハードNGのヒット: {len(hard_hits)} 件")
    if applied_exceptions:
        lines.append(f"- 例外を適用した箇所: {len(applied_exceptions)} 件")
        for rel, pat, reason in applied_exceptions:
            lines.append(f"  - {rel}： パターン「{pat}」（理由: {reason}）")
    lines.append("")
    if hard_hits:
        lines.append("## ハードNG（1件でもあれば公開不可）")
        lines.append("")
        for rel, label, excerpt in hard_hits:
            lines.append(f"- [{label}] {rel}： …{excerpt}…")
        lines.append("")
    lines.append("## ソフト対象（チェックリストで確認の記録が必須）")
    lines.append("")
    if soft_counts:
        for label, count in soft_counts.most_common():
            lines.append(f"- {label}: {count} 件")
            for rel, excerpt in soft_locations[label][:10]:
                lines.append(f"  - {rel}： …{excerpt}…")
    else:
        lines.append("- なし")
    lines.append("")
    verdict = "FAIL（公開不可）" if hard_hits else "PASS（ハードNG 0件）"
    lines.append(f"## 判定: {verdict}")
    output = "\n".join(lines) + "\n"
    print(output)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(output)
    return 1 if hard_hits else 0


if __name__ == "__main__":
    sys.exit(main())
