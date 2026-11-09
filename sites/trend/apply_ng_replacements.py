"""The desk's replacement sentences for the NG words that are still hard in ng_rules 2026-11-09.3 (outbox 差し替え_*.md, 適用が必須の7件).  Each replacement is exact:
the old sentence must be found exactly once in the site's files, or the script stops (nothing is guessed).  Run once; a second run finds nothing to replace and changes nothing."""
from __future__ import annotations

from pathlib import Path

SITE = Path(__file__).resolve().parent
REPLACE = [
    ("足りないものを確かめます。", "足りないものを確認します。"),                                     # home
    ("最新の情報は、気象庁の発表で確かめてください。", "最新の情報は、気象庁の発表でご確認ください。"),         # about
    ("産地の出荷量や天候の影響もあわせて確かめます。", "産地の出荷量や天候の影響もあわせて伝えます。"),         # category 家計
    ("増えているという流れで見ます。", "増えているという流れで捉えます。"),                              # influenza
    ("袋の価格を重さで割った単価で見ます。", "袋の価格を重さで割った単価で比べます。"),                      # rice
    ("金額ではなく増え方の率で見ます。", "金額ではなく増え方の率で比べます。"),                            # wage
    ("という順で見ると、", "という順で比べると、"),                                                # wage
]


def main() -> int:
    files = sorted(SITE.glob("content/*.json")) + [SITE / "site.json"]
    texts = {f: f.read_text(encoding="utf-8") for f in files}
    for old, new in REPLACE:
        hits = [f for f, t in texts.items() if old in t]
        if not hits:
            if any(new in t for t in texts.values()):
                continue                                             # already done
            raise SystemExit(f"not found: {old}")
        if sum(texts[f].count(old) for f in hits) != 1:
            raise SystemExit(f"found {sum(texts[f].count(old) for f in hits)} times (must be exactly once): {old}")
        texts[hits[0]] = texts[hits[0]].replace(old, new)
    for f, t in texts.items():
        if f.read_text(encoding="utf-8") != t:
            f.write_text(t, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
