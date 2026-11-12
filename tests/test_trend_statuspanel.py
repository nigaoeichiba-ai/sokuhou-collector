"""trend-sokuho.com: the status panel (sites/trend/statuspanel.py, the common part) and the 防災チェック gauges.  Desk spec 2026-11-10: the class is JMA's ladder, the danger level is the
site's reading of the maximum wind against JMA's wording of the strength of wind, every step has a word, the numbers stay as text, and a follow-up report only replaces the numbers."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from sokuhou import newsite
from sokuhou.newsite import site_hooks

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"
hooks = site_hooks(SITE)
import sys  # noqa: E402

sys.path.insert(0, str(SITE))
import statuspanel  # noqa: E402

BASE = {"label": "台風99号", "asof": "5日9時現在", "pressure": 960, "gust": 60, "impact": {"area": "小笠原諸島", "until": "6日15時", "prob": 91, "only_area": True}}


def panel(wind, **kw):
    st = dict(BASE, wind=wind)
    st.update(kw)
    return statuspanel.typhoon_panel(st)


class StatusPanel(unittest.TestCase):
    def test_the_class_follows_jmas_ladder_at_every_boundary(self):
        for wind, name in [(16.9, "熱帯低気圧"), (17, "台風"), (32.9, "台風"), (33, "強い"), (43.9, "強い"), (44, "非常に強い"), (53.9, "非常に強い"), (54, "猛烈な")]:
            self.assertEqual(statuspanel.LADDER[statuspanel.klass(wind)][1], name, wind)

    def test_the_danger_level_follows_the_desks_table_at_every_boundary(self):
        for wind, level, word in [(14, 1, "やや強い風"), (15, 2, "強い風"), (19, 2, "強い風"), (20, 3, "非常に強い風"), (29, 3, "非常に強い風"), (30, 4, "猛烈な風"), (39, 4, "猛烈な風"), (40, 5, "猛烈な風")]:
            self.assertEqual(statuspanel.danger(wind), (level, word), wind)

    def test_a_follow_up_only_replaces_the_numbers_and_the_panel_follows(self):
        a, b = panel(45, cls="非常に強い"), panel(35, pressure=985, cls="強い")
        self.assertEqual(a.count('class="step now"'), 1)
        self.assertIn('<div class="step now" aria-current="true">非常に強い<br>44〜54m/s</div>', a)
        self.assertIn('<div class="step now" aria-current="true">強い<br>33〜44m/s</div>', b)
        self.assertIn("5段階の 5", a)
        self.assertIn("5段階の 4", b)
        self.assertEqual(a.count('class="seg on'), 5)
        self.assertEqual(b.count('class="seg on'), 4)
        self.assertIn("中心気圧 985hPa、最大風速 35m/s", b)      # the numbers stay as text, not only in the gauge

    def test_every_gauge_has_its_words_and_the_note_comes_once(self):
        h = panel(40)
        self.assertIn("強い <span", h)
        self.assertIn("「猛烈な風」に当たる強さです", h)
        self.assertEqual(h.count('class="sp-note"'), 1)
        self.assertIn("階級の名前が「台風」でも、弱いという意味ではありません。", h)
        self.assertIn('role="img" aria-label="危険度 5段階の5"', h)
        self.assertIn("小笠原諸島が暴風域に入る確率は、6日15時までに91%です。", h)

    def test_a_class_that_disagrees_with_the_wind_stops_the_build(self):
        with self.assertRaises(SystemExit):
            panel(45, cls="強い")      # a follow-up that changed the wind but not the JMA's class name must not pass

    def test_an_impact_box_without_the_confirmed_case_stops_the_build(self):
        with self.assertRaises(SystemExit):
            panel(45, impact={"area": "小笠原諸島", "until": "6日15時", "prob": 91})      # a different case needs a new wording from the desk

    def test_an_extratropical_low_shows_one_line_and_no_class_or_danger_rows(self):
        h = panel(45, extratropical="11日21時", impact=None)
        self.assertIn("温帯低気圧に変わりました（11日21時、気象庁）", h)
        for gone in ("気象庁の階級", "危険度（風の強さ）", 'class="ladder"', 'class="gauge"', "sp-note", "sp-impact"):
            self.assertNotIn(gone, h)
        self.assertIn("5日9時現在（気象庁の発表）", h)


class TyphoonArticle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg, spec, content = newsite.load_site(SITE)
        cls.content = hooks.prepare(cfg, spec, content, SITE)

    def test_the_typhoon_article_carries_the_panel_right_after_the_lead(self):
        ty = next(p for p in self.content if p["path"] == "/trend-typhoon32/")
        heads = [s.get("h2") for s in ty["sections"]]
        i = heads.index("3行まとめ")
        self.assertIn("status-panel", ty["sections"][i + 1].get("html", ""))
        self.assertEqual(sum("status-panel" in s.get("html", "") for s in ty["sections"]), 1)

    def test_the_numbers_and_dates_in_the_text_agree_with_the_panel(self):
        ty = next(p for p in self.content if p["path"] == "/trend-typhoon32/")
        st = ty["status_typhoon"]
        text = json.dumps(ty["sections"], ensure_ascii=False)
        self.assertIn(f'{st["pressure"]}hPa', text)
        self.assertIn(f'最大風速は{st["wind"]}m/s', text)
        if st.get("extratropical"):
            self.assertIn(f'{st["extratropical"]}に南鳥島近海で温帯低気圧', text)
            self.assertNotIn("近づいています", text)
            self.assertNotIn("達します", text)      # no future tense about a typhoon that is over
        self.assertTrue(ty["updated"] >= "2026-11-13")


class BousaiGauges(unittest.TestCase):
    """The 防災チェック: 8 items, two tiers, a gauge and a word for each, the overall step by the number of items that reached the guide."""

    def setUp(self):
        d = json.loads((SITE / "content" / "bousai.json").read_text(encoding="utf-8"))
        self.h = next(s["html"] for s in d["sections"] if s.get("html", "").startswith('<div class="bz"'))

    def test_the_eight_items_are_in_two_tiers_with_the_desks_wording(self):
        self.assertLess(self.h.index("<h2>まず備えるもの</h2>"), self.h.index("<h2>あると安心なもの</h2>"))
        first, second = self.h.split("<h2>あると安心なもの</h2>")
        self.assertEqual([m for m in ("water", "food", "toilet", "light", "battery") if f'id="{m}-fill"' in first], ["water", "food", "toilet", "light", "battery"])
        self.assertEqual([m for m in ("radio", "rain", "aid") if f'id="{m}-fill"' in second], ["radio", "rain", "aid"])
        for w in ("3日分に届いていない", "3日分ある", "1週間分ある", "まだそろっていない", "一部だけそろっている", "そろっている", "まだ足りない", "最低限そろっている", "安心",
                  "入力した内容がサイトに送られることはありません"):
            self.assertIn(w, self.h)
        self.assertEqual(self.h.count('<div class="segbar" id="segbar">'), 1)
        self.assertEqual(self.h.count("<div></div>"), 8)      # 8 cells
        self.assertNotIn("<form", self.h)      # nothing is sent
        self.assertNotIn("localStorage", self.h)      # nothing is saved
        self.assertNotIn("fetch(", self.h)

    def test_the_overall_step_boundaries_are_4_5_and_8(self):
        self.assertIn("var overall = count >= 8 ? 2 : (count >= 5 ? 1 : 0);", self.h)
        self.assertIn("var wdays = bottles * 2 / (fam * 3);", self.h)      # 2 L bottles, 3 L per person per day
        self.assertIn("function daysStage(days) { return days >= 7 ? 2 : (days >= 3 ? 1 : 0); }", self.h)


if __name__ == "__main__":
    unittest.main()
