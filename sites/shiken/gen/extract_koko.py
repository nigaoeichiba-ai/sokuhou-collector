"""One-off: pick the prefecture rows for /koko/ out of the verification notes (json from the official boards' pages) and write data/koko.json.
Dates only; the source is the board's own page.  python sites/shiken/gen/extract_koko.py <notes dir>"""
import json
import re
import sys
from pathlib import Path

NOTES = Path(sys.argv[1])
OUT = Path(__file__).resolve().parents[1] / "data" / "koko.json"
# pref -> (index of the general selection, index of the early selection or None)
PICK = {
    "北海道": (1, 0), "青森県": (0, None), "岩手県": (0, None), "宮城県": (0, None), "秋田県": (0, None), "山形県": (2, 0),
    "栃木県": (0, None), "群馬県": (0, None), "埼玉県": (0, None), "千葉県": (0, None), "東京都": (1, 0), "神奈川県": (0, None),
    "新潟県": (0, None), "石川県": (1, 0), "山梨県": (1, 0), "長野県": (1, 0), "岐阜県": (0, None), "静岡県": (0, None), "愛知県": (3, 1),
    "三重県": (1, 0), "大阪府": (9, 0), "兵庫県": (1, 0), "京都府": (2, 0), "広島県": (1, 0), "福岡県": (1, 0),
    "岡山県": (1, 0), "熊本県": (1, 0), "香川県": (1, 0),
    "大分県": (1, 0), "宮崎県": (1, 0), "鹿児島県": (2, 1), "富山県": (2, 0), "茨城県": (0, None),
}
DATE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")


def dates(v):
    if v is None:
        return []
    if isinstance(v, list):
        out = []
        for x in v:
            out += dates(x)
        return out
    return DATE.findall(str(v))


def iso(t):
    return "-".join(t)


def near_first(ds):
    """Re-examinations come days after the main day: keep the days within two days of the first, once each."""
    from datetime import date
    if not ds:
        return []
    first = date.fromisoformat(ds[0])
    out = []
    for d in ds:
        if 0 <= (date.fromisoformat(d) - first).days <= 2 and d not in out:
            out.append(d)
    return out


def stage(s):
    ap_s, ap_e = dates(s.get("apply_start")), dates(s.get("apply_end"))
    return {
        "name": s["name"],
        "apply": [iso(ap_s[0]) if ap_s else None, iso(ap_e[0]) if ap_e else None],
        "exam": near_first([iso(t) for t in dates(s.get("exam_date"))]),
        "result": (lambda r: iso(r[0]) if r else None)(dates(s.get("result_date"))),
        "apply_raw": s.get("apply_end") if isinstance(s.get("apply_end"), str) and "承認" in s.get("apply_end") else None,
    }


rows = {}
for f in ("hs_A.json", "hs_B.json", "hs_C.json", "hs_D.json"):
    if not (NOTES / f).exists():
        continue
    for x in json.load(open(NOTES / f, encoding="utf-8")):
        if x["pref"] in PICK:
            g, e = PICK[x["pref"]]
            if not str(x.get("status", "")).startswith("公表済み") or "令和8年度" in str(x["stages"][0].get("name", "")) or max(g, e or 0) >= len(x["stages"]):
                continue
            rows[x["pref"]] = {"pref": x["pref"], "src": x["source_urls"][0], "general": stage(x["stages"][g]),
                               "early": stage(x["stages"][e]) if e is not None else None}
for k in ("general", "early"):          # Hiroshima registers in steps: the period is left to the board's page
    if rows["広島県"][k]:
        rows["広島県"][k]["apply"] = [None, None]
JIS = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
order = [p for p in JIS if p in rows]
json.dump([rows[p] for p in order], open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for p in order:
    r = rows[p]
    print(p, r["general"]["name"][:14], r["general"]["apply"], r["general"]["exam"], r["general"]["result"], "|", r["early"] and (r["early"]["name"][:10], r["early"]["exam"], r["early"]["result"]))
