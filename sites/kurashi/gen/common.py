"""Shared helpers of the generator of sites/kurashi/content/*.json.

Dates, weekdays and "N days later" are computed here, never typed by hand (the deadlines change every year).
The pages are written in gen/pages_*.py; gen/__init__ writes them to ../content/ and the sources to ../site.json.
"""
from __future__ import annotations

from datetime import date, timedelta

TODAY = date(2026, 11, 3)          # the day the facts were checked against the primary sources
CHECKED = "2026年11月3日"
WD = "月火水木金土日"


def d(y: int, m: int, day: int) -> date:
    return date(y, m, day)


def wd(x: date) -> str:
    return WD[x.weekday()]


def jp(x: date, year: bool = True) -> str:
    """2027年2月16日(火)"""
    return f"{x.year}年{x.month}月{x.day}日({wd(x)})" if year else f"{x.month}月{x.day}日({wd(x)})"


def md(x: date) -> str:
    return f"{x.month}月{x.day}日({wd(x)})"


def plus(x: date, n: int) -> date:
    return x + timedelta(days=n)


def after(x: date) -> int:
    """days from TODAY"""
    return (x - TODAY).days


def last_day_inclusive(start: date, n: int) -> date:
    """The last day when the first day counts as day 1 (the Family Register Act, art. 43)."""
    return start + timedelta(days=n - 1)


def last_day_exclusive(start: date, n: int) -> date:
    """The last day when the first day is not counted (Civil Code art. 140)."""
    return start + timedelta(days=n)


def a(path: str, text: str) -> str:
    return f'<a href="{path}">{text}</a>'


def para_html(*parts: str) -> str:
    return "<p>" + "".join(parts) + "</p>"


def row_link(text: str, path: str) -> dict:
    return {"text": text, "href": path}


def page(path, kind, parent, title, h1, kw, intent, desc, answer, sections, related, sources, *, secondary=(), basis=None, updated="2026-11-03", noindex=False):
    p = {
        "updated": updated,
        "data_basis": basis or f"{CHECKED}確認",
        "sources": list(sources),
        "path": path,
        "kind": kind,
        "parent": parent,
        "title": title,
        "h1": h1,
        "primary_kw": kw,
        "secondary_kw": list(secondary),
        "intent": intent,
        "description": desc,
        "answer": answer,
        "sections": sections,
        "related": [{"path": r[0], "text": r[1]} for r in related],
    }
    if noindex:
        p["noindex"] = True
    return p


SOURCES = {
    "nta_nencho": {"org": "国税庁", "table": "年末調整がよくわかるページ(令和8年分)", "url": "https://www.nta.go.jp/users/gensen/nencho/index.htm", "basis": "令和8年分"},
    "nta_2665": {"org": "国税庁", "table": "タックスアンサー No.2665 年末調整の対象となる人", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/gensen/2665.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_2675": {"org": "国税庁", "table": "タックスアンサー No.2675 年末調整の過不足額の精算", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/gensen/2675.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_2020": {"org": "国税庁", "table": "タックスアンサー No.2020 確定申告", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2020.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_1900": {"org": "国税庁", "table": "タックスアンサー No.1900 給与所得者で確定申告が必要な人", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1900.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_2030": {"org": "国税庁", "table": "タックスアンサー No.2030 還付申告", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2030.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_1120": {"org": "国税庁", "table": "タックスアンサー No.1120 医療費を支払ったとき(医療費控除)", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1120.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_1155": {"org": "国税庁", "table": "タックスアンサー No.1155 ふるさと納税(寄附金控除)", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1155.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_2022": {"org": "国税庁", "table": "タックスアンサー No.2022 納税者が死亡したときの確定申告(準確定申告)", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2022.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_4205": {"org": "国税庁", "table": "タックスアンサー No.4205 相続税の申告と納税", "url": "https://www.nta.go.jp/taxes/shiraberu/taxanswer/sozoku/4205.htm", "basis": "令和8年4月1日現在法令等"},
    "nta_tokushu": {"org": "国税庁", "table": "令和7年分 確定申告特集(申告・納付の期限の表示)", "url": "https://www.nta.go.jp/taxes/shiraberu/shinkoku/tokushu/index.htm", "basis": "令和7年分"},
    "soumu_onestop": {"org": "総務省", "table": "ふるさと納税トピックス 制度改正について(ワンストップ特例)", "url": "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/topics/20150401.html", "basis": "平成27年4月1日の制度"},
    "soumu_deduction": {"org": "総務省", "table": "ふるさと納税のしくみ 寄附金控除", "url": "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/mechanism/deduction.html", "basis": "掲載時点"},
    "post_nenga": {"org": "日本郵便", "table": "2027年用年賀はがき等の発売・引受開始に関する発表(2026年8月31日)", "url": "https://files.japanpost.jp/assets/34d9d11432734cfaa759e78fe395b688/159168aef19d465baf3350d358e46fa9/20260831_02_06.pdf", "basis": "2026年8月31日発表"},
    "egov_koseki": {"org": "e-Gov法令検索", "table": "戸籍法(第43条・第49条・第74条・第86条)", "url": "https://laws.e-gov.go.jp/law/322AC0000000224", "basis": "現行法令"},
    "egov_juki": {"org": "e-Gov法令検索", "table": "住民基本台帳法(第22条〜第25条)", "url": "https://laws.e-gov.go.jp/law/342AC0000000081", "basis": "現行法令"},
    "egov_jidou": {"org": "e-Gov法令検索", "table": "児童手当法(第7条・第8条)", "url": "https://laws.e-gov.go.jp/law/346AC0000000073", "basis": "現行法令"},
    "cfa_jidou": {"org": "こども家庭庁", "table": "児童手当制度のご案内(認定請求)", "url": "https://www.cfa.go.jp/policies/kokoseido/jidouteate/annai/", "basis": "掲載時点"},
    "egov_kenpo": {"org": "e-Gov法令検索", "table": "健康保険法(第37条)", "url": "https://laws.e-gov.go.jp/law/211AC0000000070", "basis": "現行法令"},
    "egov_kokuho": {"org": "e-Gov法令検索", "table": "国民健康保険法(第9条)", "url": "https://laws.e-gov.go.jp/law/333AC0000000192", "basis": "現行法令"},
    "egov_sharyo": {"org": "e-Gov法令検索", "table": "道路運送車両法(第12条)", "url": "https://laws.e-gov.go.jp/law/326AC0000000185", "basis": "現行法令"},
    "egov_minpo": {"org": "e-Gov法令検索", "table": "民法(第140条・第739条・第915条)", "url": "https://laws.e-gov.go.jp/law/129AC0000000089", "basis": "現行法令"},
    "egov_toki": {"org": "e-Gov法令検索", "table": "不動産登記法(第76条の2)", "url": "https://laws.e-gov.go.jp/law/416AC0000000123", "basis": "現行法令"},
    "egov_kyujitsu": {"org": "e-Gov法令検索", "table": "行政機関の休日に関する法律(第1条)", "url": "https://laws.e-gov.go.jp/law/363AC0000000091", "basis": "現行法令"},
    "egov_ginko": {"org": "e-Gov法令検索", "table": "銀行法施行令(第5条)", "url": "https://laws.e-gov.go.jp/law/357CO0000000040", "basis": "現行法令"},
    "egov_kaigo": {"org": "e-Gov法令検索", "table": "介護保険法(第27条)", "url": "https://laws.e-gov.go.jp/law/409AC0000000123", "basis": "現行法令"},
    "nenkin_kanyu": {"org": "日本年金機構", "table": "国民年金に加入するための手続き", "url": "https://www.nenkin.go.jp/service/kokunen/kanyu/20140710-04.html", "basis": "掲載時点"},
    "dnc_r9": {"org": "大学入試センター", "table": "令和9年度試験(実施期日)", "url": "https://www.dnc.ac.jp/kyotsu/shiken_jouhou/r9/", "basis": "令和9年度"},
    "kaigokensaku": {"org": "厚生労働省 介護サービス情報公表システム", "table": "サービス利用までの流れ", "url": "https://www.kaigokensaku.mhlw.go.jp/commentary/flow.html", "basis": "掲載時点"},
    "digital_moving": {"org": "デジタル庁", "table": "引越し手続のオンライン化・ワンストップ化(マイナポータルの転出届・転入予約)", "url": "https://www.digital.go.jp/policies/moving_onestop_service", "basis": "2026年3月13日の更新を確認"},
    "env_kafun": {"org": "環境省", "table": "環境から考える、花粉症との付き合い方(2026年3月4日)", "url": "https://www.env.go.jp/guide/info/ecojin/feature1/20260304.html", "basis": "2026年3月4日"},
    "env_kafun2": {"org": "環境省", "table": "ecojin's EYE 花粉症対策(2023年2月8日)", "url": "https://www.env.go.jp/guide/info/ecojin/eye/20230208-1.html", "basis": "2023年2月8日"},
    "post_tenkyo": {"org": "日本郵便", "table": "転居・転送サービス", "url": "https://www.post.japanpost.jp/service/receive/relocation/", "basis": "掲載時点"},
    "npa_onestop": {"org": "警察庁", "table": "住所変更ワンストップサービス等(マイナ免許証)", "url": "https://www.npa.go.jp/bureau/traffic/onestop.pdf", "basis": "掲載時点"},
}


def sources_json() -> dict:
    out = {}
    for k, v in SOURCES.items():
        out[k] = {**v, "fetched": "2026-11-03"}
    return out
