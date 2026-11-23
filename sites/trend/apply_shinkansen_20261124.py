#!/usr/bin/env python3
"""2026-11-24: add the year-end Shinkansen on-sale-date article (Nippon Travel VC MyLink, trend pid 892749522). Safe to run twice."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_20261123b as m  # noqa: E402

NTA = ('<p><a href="https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3788020&amp;pid=892749522&amp;vc_url=https%3A%2F%2Fwww.nta.co.jp%2Fjr%2Fshinkansen%2F" '
       'rel="nofollow sponsored noopener" target="_blank">日本旅行のJRセットプランを見る</a>（PR）'
       '<img src="https://ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=3788020&amp;pid=892749522" height="1" width="1" border="0" alt=""></p>')

if __name__ == "__main__":
    slug = "trend-nenmatsu-shinkansen-hatsubai-2026"
    m.yahoo_link = lambda *a, **k: NTA
    cat = json.load(open(os.path.join(m.CONTENT, "trend-nozomi-zensekishitei.json"), encoding="utf-8"))["category"]
    m.image("card_年末年始新幹線の発売日.webp", slug)
    m.add(slug, "記事最終稿_年末年始新幹線の発売日_2026-11-24.md", "", "年末年始の新幹線の発売日", "新幹線",
          "新幹線の指定席は、乗る日の1か月前の10時に発売されます。12月28日に乗るなら、11月28日の土曜日の朝10時です。",
          "年末年始の新幹線の指定席は、乗る日の1か月前の10時に発売。12月28日乗車分は11月28日、12月31日と1月1日は12月1日です。事前受付の日程も早見表で確認できます。",
          "指定席は乗る日の1か月前の10時発売。12月31日と1月1日は12月1日にまとまる",
          "鉄道会社の公式案内（2026年度の年末年始日程）、2026年11月24日時点",
          ["trend-nozomi-zensekishitei", "trend-yakou-shinkansen-amaneseru", "trend-jal-timesale-2026"], cat,
          vc_url="")
    print("added", slug)
