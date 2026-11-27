#!/usr/bin/env python3
"""2026-11-27: two advertisers asked today for their ads to come down (desk request).  Iris Plaza (own shop stopped):
its A8 links and tracking images are removed from two articles.  The au PAY Market store of the same name is another
sales channel (its listing was open today), but a page that names the advertiser must carry its link (linkage gate), so
that store's row is taken out for now; the desk can restore it when the programme resumes or the rule is changed.  Daimaru
Matsuzakaya online: the year-end gift article no longer reads as if it can be ordered there now.  Safe to run twice."""
import json
import os
import urllib.parse

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
TODAY = "2026-11-27"
CODE = "4BEGD8+HV6BU+CHG"
REL = 'rel="nofollow sponsored noopener" target="_blank"'


def load(slug):
    p = os.path.join(CONTENT, slug + ".json")
    return p, json.load(open(p, encoding="utf-8"))


def save(p, d):
    d["updated"] = TODAY  # the data basis date stays: only the links and the shop's status were looked at today
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def replace(d, old, new):
    found = []

    def walk(v):
        if isinstance(v, str):
            if old in v:
                found.append(1)
                return v.replace(old, new)
            return v
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v

    d["sections"] = walk(d["sections"])
    assert found, old


def aupay():
    p, d = load("trend-aupay-blackfriday")
    if not any(CODE in x.get("html", "") for x in d["sections"]):
        return print("skip: aupay")
    d["sections"] = [x for x in d["sections"] if CODE not in x.get("html", "")]
    table = next(x["table"] for x in d["sections"] if "table" in x and any(r[1].startswith("アイリスプラザ") for r in x["table"]["rows"] if len(r) > 1))
    table["rows"] = [r for r in table["rows"] if not r[1].startswith("アイリスプラザ")]
    replace(d, "、家電や寝具なら24日から30日のアイリスプラザ、", "、")
    replace(d, "公式発表では、期間を区切って、目玉の店舗が紹介されています。", "公式発表では、期間を区切って目玉の店舗が紹介されています。下の表はその一部です。")
    save(p, d)
    print("changed aupay")


def bukka():
    p, d = load("trend-tokyo-bukka-202610")
    i = next((i for i, x in enumerate(d["sections"]) if CODE in x.get("html", "")), None)
    if i is None:
        return print("skip: bukka")
    q = urllib.parse.quote("日用品 まとめ買い")
    d["sections"][i] = {"html": '<p>日用品は、まとめ買いの単価を比べると差が出ます。<a href="https://www.amazon.co.jp/s?k=%s&amp;tag=amazonmacs-22" %s>'
                                'Amazonで日用品のまとめ買いを探す</a>（PR）</p>' % (q, REL)}
    save(p, d)
    print("changed bukka")


def oseibo():
    p, d = load("trend-oseibo-hayawari")
    table = next(x["table"] for x in d["sections"] if "table" in x)
    row = next(r for r in table["rows"] if r[0] == "大丸松坂屋オンラインストア")
    if "公式" in row[-1]:
        return print("skip: oseibo")
    row[2] = "10月8日から優待（今の受付状況は公式で確認）"
    row[-1] = "受付状況を公式で確認"
    replace(d, "<strong>高島屋オンラインストア・大丸松坂屋オンラインストア：</strong> 12月24日 午前10時",
            "<strong>高島屋オンラインストア：</strong> 12月24日 午前10時")
    replace(d, "注文を進める前に、ネットと店頭のどちらで申し込むのが自分の条件に合っているかを確認しておきましょう。",
            "注文を進める前に、ネットと店頭のどちらで申し込むのが自分の条件に合っているかを確認しておきましょう。大丸松坂屋オンラインストアは、今申し込めるかどうかを公式の案内で確かめてから進めてください（2026年11月27日現在）。")
    replace(d, "高島屋や大丸松坂屋などでも12月下旬にかけて締切を迎える", "高島屋などでも12月下旬にかけて締切を迎える")
    save(p, d)
    print("changed oseibo")


if __name__ == "__main__":
    aupay()
    bukka()
    oseibo()
