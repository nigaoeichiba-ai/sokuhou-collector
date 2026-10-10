"""atomou: the use cases are complete, easy to read, calm where the day is a sad one, and never promise what the service cannot promise."""
import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog, usecases  # noqa: E402

QUIET_BANNED = ("おめでとう", "楽しい", "お得", "おすすめ", "セール", "!", "！")  # half-width and full-width exclamation marks
PROMISE_BANNED = ("確実", "絶対", "必ず届", "忘れません")
SLUG_RE = re.compile(r"^[a-z]+(-[a-z0-9]+)*$")
FIELDS = {"slug": str, "title": str, "who": str, "situation": str, "steps": list, "catalog": (dict, type(None)), "own": (dict, type(None)),
          "tips": list, "cautions": list, "quiet": bool, "group": str, "related": list}
# names of screens, buttons and features that do not exist (the texts were once written from the spec, before the screens were built)
NO_SUCH_SCREEN = ("『登録』", "『もうすぐ』", "『これからの予定』", "『家族・自分の誕生日』", "『毎日の数え方』", "これからの予定", "家族・自分の誕生日",
                  "毎日の数え方", "毎月", "知らせない", "当日の朝だけ", "切りかえ", "切り替え", "グラフ", "チップ", "数え年",
                  # the calendar lives inside the app now: the cards have no 'save' or 'add to calendar' button, and no file is downloaded
                  # ('☆ 予定に入れる' / '★ 予定に入っています' are the real buttons and are not caught by these)
                  "保存する", "カレンダーに入れる", "ダウンロード", "ファイルを開", "今日の数字", "あなたの日")
# words a visitor can filter the catalogue by: categories and the synonym tags of sites/atomou/catalog.py
CATALOG_TAGS = set(catalog.GROUP_OF_CATEGORY) | {t for v in catalog.SYNONYMS.values() for t in v} | set(catalog.GROUPS)


def texts(u):
    """Every string a scenario can show, so a banned word cannot hide in a nested field."""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    walk(u)
    return out


def prose(u):
    """The words a visitor reads (the group name and the slugs are labels, not prose)."""
    own = u.get("own") or {}
    out = [u.get("title", ""), u.get("who", ""), u.get("situation", ""), own.get("label", ""), own.get("hint", "")]
    for k in ("steps", "tips", "cautions"):
        out += [s for s in (u.get(k) or []) if isinstance(s, str)]
    return out


def check_screens(u):
    """Problems with the screen names a scenario uses: names that do not exist, and steps that do not match the kind of scenario."""
    p = []
    for t in prose(u):
        for w in NO_SUCH_SCREEN:
            if w in t:
                p.append(f"実在しない画面・機能の名前「{w}」")
    steps = "\n".join(u.get("steps") or [])
    c = u.get("catalog")
    if c is not None:
        if f"『{c.get('group')}』" not in steps:
            p.append("公式の日付の例なのに、手順にジャンル名がない")
        if "『☆ 予定に入れる』" not in steps:
            p.append("公式の日付の例なのに、手順に『☆ 予定に入れる』がない")
    elif "『この日を記録する』" not in steps:
        p.append("自分の日の例なのに、手順に『この日を記録する』がない")
    return p


def check_scenario(u, slugs=None, groups_order=None, catalog_groups=None):
    """Return the list of problems of one scenario (a dict), so the check can be tried on bad data too."""
    p = []
    for k, typ in FIELDS.items():
        if k not in u:
            p.append(f"{k} がない")
        elif not isinstance(u[k], typ):
            p.append(f"{k} の型が違う")
    if p:
        return p
    if not SLUG_RE.match(u["slug"]):
        p.append("slug は英小文字とハイフンだけ")
    if not u["title"] or len(u["title"]) > 25:
        p.append("title は1〜25字")
    if not u["who"] or len(u["who"]) > 20:
        p.append("who は1〜20字")
    if not 60 <= len(u["situation"]) <= 160:
        p.append("situation は60〜160字")
    if not 3 <= len(u["steps"]) <= 5 or not all(isinstance(s, str) and s for s in u["steps"]):
        p.append("steps は3〜5個の文字列")
    if not 1 <= len(u["tips"]) <= 3 or not all(isinstance(s, str) and s for s in u["tips"]):
        p.append("tips は1〜3個の文字列")
    if len(u["cautions"]) > 2 or not all(isinstance(s, str) and s for s in u["cautions"]):
        p.append("cautions は0〜2個の文字列")
    if len(u["related"]) > 3:
        p.append("related は3個まで")
    if slugs is not None:
        for r in u["related"]:
            if r not in slugs:
                p.append(f"related の {r} がない")
            if r == u["slug"]:
                p.append("related が自分自身")
    if groups_order is not None and u["group"] not in groups_order:
        p.append("group が GROUPS_ORDER にない")
    c = u["catalog"]
    if c is not None:
        if set(c) != {"group", "tags"}:
            p.append("catalog の項目は group と tags")
        else:
            if c["group"] is not None and (catalog_groups is None or c["group"] not in catalog_groups):
                p.append("catalog の group がカタログにない")
            if not isinstance(c["tags"], list) or not all(isinstance(t, str) for t in c["tags"]):
                p.append("catalog の tags は文字列のリスト")
    o = u["own"]
    if o is not None:
        if set(o) != {"label", "kind", "hint"} or not all(isinstance(v, str) and v for v in o.values()):
            p.append("own の項目は label・kind・hint")
        elif o["kind"] not in usecases.KINDS:
            p.append("own の kind が不明")
    for t in texts(u):
        for w in PROMISE_BANNED:
            if w in t:
                p.append(f"約束の言葉「{w}」")
    if u["quiet"]:
        for t in texts(u):
            for w in QUIET_BANNED:
                if w in t:
                    p.append(f"静かな場面に禁句「{w}」")
    return sorted(set(p))


class UsecaseTests(unittest.TestCase):
    def test_enough_scenarios(self):
        self.assertGreaterEqual(len(usecases.USECASES), 25)

    def test_slugs_unique(self):
        slugs = [u["slug"] for u in usecases.USECASES]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_every_scenario_is_valid(self):
        slugs = {u["slug"] for u in usecases.USECASES}
        for u in usecases.USECASES:
            with self.subTest(slug=u.get("slug")):
                self.assertEqual(check_scenario(u, slugs, usecases.GROUPS_ORDER, set(catalog.GROUPS)), [])

    def test_catalog_tags_exist_in_the_catalog_vocabulary(self):
        for u in usecases.USECASES:
            for t in (u["catalog"] or {}).get("tags", []):
                with self.subTest(slug=u["slug"], tag=t):
                    self.assertIn(t, CATALOG_TAGS)

    def test_groups(self):
        self.assertEqual(len(usecases.GROUPS_ORDER), len(set(usecases.GROUPS_ORDER)))
        used = {u["group"] for u in usecases.USECASES}
        self.assertEqual(used, set(usecases.GROUPS_ORDER), "使われない見出し、または未登録の見出しがある")
        self.assertEqual(sum(len(v) for _, v in usecases.grouped()), len(usecases.USECASES))

    def test_grief_scenes_exist_and_carry_no_catalog_or_ads(self):
        quiet = [u for u in usecases.USECASES if u["quiet"]]
        self.assertGreaterEqual(len(quiet), 4)
        for u in quiet:
            self.assertIsNone(u["catalog"], u["slug"])  # official sale/ad-friendly cards are never offered next to grief
        slugs = {u["slug"] for u in quiet}
        self.assertTrue({"memorial-day", "monthly-memorial", "pet-memorial"} <= slugs)

    def test_services_notes_say_regions_differ(self):
        u = usecases.by_slug("memorial-services")
        self.assertTrue(any("地域" in c and "宗派" in c for c in u["cautions"]))

    def test_helpers(self):
        self.assertIsNone(usecases.by_slug("no-such-slug"))
        self.assertEqual(usecases.by_slug("exam-university")["slug"], "exam-university")
        self.assertEqual([r["slug"] for r in usecases.related("exam-university")], usecases.by_slug("exam-university")["related"])
        self.assertEqual(usecases.related("no-such-slug"), [])

    def test_situation_length_is_60_to_120(self):  # 2026-10-08: the copy rewrite shortened the texts; the floor follows check_scenario
        for u in usecases.USECASES:
            with self.subTest(slug=u["slug"]):
                self.assertTrue(60 <= len(u["situation"]) <= 120, len(u["situation"]))

    def test_texts_use_only_screens_that_exist(self):
        for u in usecases.USECASES:
            with self.subTest(slug=u["slug"]):
                self.assertEqual(check_screens(u), [])

    def test_no_digits_that_look_like_dates_or_amounts(self):
        # facts live in the catalogue; the prose only describes how to count
        pat = re.compile(r"\d{4}年|\d{1,2}月\d{1,2}日|\d+円|\d+%")
        for u in usecases.USECASES:
            for t in texts(u):
                with self.subTest(slug=u["slug"]):
                    self.assertIsNone(pat.search(t), t)


class NegativeTests(unittest.TestCase):
    """The checker must catch the faults it exists for."""

    def good(self):
        return copy.deepcopy(usecases.by_slug("memorial-day"))

    def test_good_passes(self):
        self.assertEqual(check_scenario(self.good()), [])

    def test_banned_words_in_a_quiet_scene_are_found(self):
        for w in QUIET_BANNED:
            u = self.good()
            u["tips"] = [f"今日は{w}の日です"]
            self.assertTrue(any(w in x for x in check_scenario(u)), w)

    def test_banned_word_in_a_nested_field_is_found(self):
        u = self.good()
        u["own"]["hint"] = "おめでとうを伝える日"
        self.assertTrue(any("おめでとう" in x for x in check_scenario(u)))

    def test_banned_words_are_allowed_where_the_scene_is_not_quiet(self):
        u = copy.deepcopy(usecases.by_slug("furusato-nozei"))
        u["tips"] = ["セールの時期にも"]
        self.assertEqual(check_scenario(u, catalog_groups=set(catalog.GROUPS)), [])

    def test_promises_are_found_in_any_scene(self):
        for quiet in (True, False):
            for w in PROMISE_BANNED:
                u = self.good()
                u["quiet"] = quiet
                u["cautions"] = [f"{w}に知らせます"]
                self.assertTrue(any(w in x for x in check_scenario(u)), (quiet, w))

    def test_structure_faults_are_found(self):
        cases = {
            "title が長い": lambda u: u.update(title="あ" * 26),
            "steps が2個": lambda u: u.update(steps=["a", "b"]),
            "steps が6個": lambda u: u.update(steps=["a"] * 6),
            "situation が短い": lambda u: u.update(situation="短い"),
            "situation が長い": lambda u: u.update(situation="あ" * 161),
            "slug が大文字": lambda u: u.update(slug="Memorial"),
            "slug が日本語": lambda u: u.update(slug="めもりある"),
            "tips が空": lambda u: u.update(tips=[]),
            "cautions が3個": lambda u: u.update(cautions=["a", "b", "c"]),
            "related が4個": lambda u: u.update(related=["a", "b", "c", "d"]),
            "quiet が文字列": lambda u: u.update(quiet="yes"),
            "own の kind が不明": lambda u: u.update(own={"label": "a", "kind": "zzz", "hint": "b"}),
        }
        for name, mutate in cases.items():
            u = self.good()
            mutate(u)
            self.assertTrue(check_scenario(u), name)

    def test_names_of_screens_that_do_not_exist_are_found_in_every_field(self):
        fields = {
            "situation": lambda u, w: u.update(situation=u["situation"] + w),
            "steps": lambda u, w: u.update(steps=u["steps"][:-1] + [f"{w}を押す"]),
            "tips": lambda u, w: u.update(tips=[f"{w}を使う"]),
            "cautions": lambda u, w: u.update(cautions=[f"{w}に注意"]),
            "own.hint": lambda u, w: u["own"].update(hint=f"{w}のとき"),
            "title": lambda u, w: u.update(title=f"{w}の日"),
        }
        for w in NO_SUCH_SCREEN:
            for name, put in fields.items():
                u = copy.deepcopy(usecases.by_slug("exam-university"))
                put(u, w)
                with self.subTest(word=w, field=name):
                    self.assertTrue(any(w in x for x in check_screens(u)))

    def test_the_old_wording_of_the_spec_is_found(self):
        old = copy.deepcopy(usecases.by_slug("exam-university"))
        old["steps"] = ["ホームの『もうすぐ』を押す", "『学校・資格』から『大学入試』を選ぶ", "志望に合う試験のカードで『登録』を押す"]
        found = check_screens(old)
        self.assertTrue(any("『登録』" in x for x in found), found)
        self.assertTrue(any("『もうすぐ』" in x for x in found), found)
        old = copy.deepcopy(usecases.by_slug("family-birthday"))
        old["steps"] = ["ホームの『記録する』を押す", "『どんな日ですか』で『家族・自分の誕生日』を選ぶ", "人のチップ(母、きょうだいなど)を選ぶ"]
        found = check_screens(old)
        self.assertTrue(any("家族・自分の誕生日" in x for x in found), found)
        self.assertTrue(any("チップ" in x for x in found), found)

    def test_steps_that_do_not_match_the_kind_of_scenario_are_found(self):
        u = copy.deepcopy(usecases.by_slug("exam-university"))
        u["steps"] = ["ホームのジャンル『学校・資格』を押す", "『大学入試』で絞り込む", "カードを開く"]
        self.assertTrue(any("☆ 予定に入れる" in x for x in check_screens(u)))
        u["steps"] = ["『大学入試』で絞り込む", "カードで『☆ 予定に入れる』を押す", "『カレンダー』で確かめる"]
        self.assertTrue(any("ジャンル名" in x for x in check_screens(u)))
        u = copy.deepcopy(usecases.by_slug("wedding-anniversary"))
        u["steps"] = ["メニューの『記録する』を押す", "日付を入れる", "完了"]
        self.assertTrue(any("この日を記録する" in x for x in check_screens(u)))

    def test_the_old_save_and_download_wording_is_found(self):
        old = copy.deepcopy(usecases.by_slug("exam-university"))
        old["steps"] = ["ホームのジャンル『学校・資格』を押す", "カードの『☆ 保存する』を押す", "『カレンダーに入れる』を押して、ファイルを開いて追加する"]
        found = check_screens(old)
        self.assertTrue(any("保存する" in x for x in found), found)
        self.assertTrue(any("カレンダーに入れる" in x for x in found), found)
        self.assertTrue(any("ファイルを開" in x for x in found), found)
        old["steps"] = ["ホームのジャンル『学校・資格』を押す", "カードの『☆ 予定に入れる』を押す", "カレンダーのファイルをダウンロードする"]
        self.assertTrue(any("ダウンロード" in x for x in check_screens(old)))
        old["steps"] = ["ホームのジャンル『学校・資格』を押す", "カードの『☆ 予定に入れる』を押す", "マイページの『まとめてカレンダーに入れる』を押す"]
        self.assertTrue(any("カレンダーに入れる" in x for x in check_screens(old)))

    def test_the_real_buttons_are_not_flagged(self):
        ok = copy.deepcopy(usecases.by_slug("exam-university"))
        ok["steps"] = ["ホームのジャンル『学校・資格』を押す", "カードの『☆ 予定に入れる』を押す(入ると『★ 予定に入っています』に変わる)",
                       "『詳細』で公式ページを見る", "『開く』や『消す』を使う", "『やること』を書いて『追加』を押す"]
        self.assertEqual(check_screens(ok), [])

    def test_no_scenario_uses_the_old_buttons_anywhere(self):
        for u in usecases.USECASES:
            blob = " | ".join(texts(u))
            for w in ("☆ 保存する", "『保存する』", "『カレンダーに入れる』", "ダウンロード"):
                with self.subTest(slug=u["slug"], word=w):
                    self.assertNotIn(w, blob)

    def test_official_scenarios_use_the_add_to_plan_button(self):
        official = [u for u in usecases.USECASES if u["catalog"] is not None]
        self.assertGreaterEqual(len(official), 10)
        for u in official:
            with self.subTest(slug=u["slug"]):
                self.assertIn("『☆ 予定に入れる』", " | ".join(u["steps"]))

    def test_planner_scenarios_exist_and_use_todo_and_events(self):
        group = [u for u in usecases.USECASES if u["group"] == "予定と準備"]
        self.assertGreaterEqual(len(group), 4)
        self.assertTrue(any((u["own"] or {}).get("kind") == "event" for u in group))
        self.assertGreaterEqual(sum("『やること』" in " | ".join(u["steps"] + u["tips"]) for u in usecases.USECASES), 15)

    def test_the_file_for_other_calendar_apps_is_only_a_short_tip(self):
        for u in usecases.USECASES:
            self.assertFalse(any("他のカレンダーアプリ" in s for s in u["steps"]), u["slug"])

    def test_grief_scenes_do_not_push_the_todo(self):
        for u in usecases.USECASES:
            if u["quiet"] and u["slug"] != "memorial-services":
                with self.subTest(slug=u["slug"]):
                    self.assertNotIn("やること", " | ".join(texts(u)))

    def test_screen_check_passes_the_real_data(self):
        for slug in ("exam-university", "wedding-anniversary", "memorial-day"):
            self.assertEqual(check_screens(usecases.by_slug(slug)), [])

    def test_missing_field_is_found(self):
        u = self.good()
        del u["steps"]
        self.assertTrue(any("steps" in x for x in check_scenario(u)))

    def test_dangling_related_group_and_catalog_group_are_found(self):
        u = self.good()
        u["related"] = ["nowhere"]
        self.assertTrue(any("nowhere" in x for x in check_scenario(u, slugs={"memorial-day"})))
        u = self.good()
        u["group"] = "知らない見出し"
        self.assertTrue(any("GROUPS_ORDER" in x for x in check_scenario(u, groups_order=usecases.GROUPS_ORDER)))
        u = copy.deepcopy(usecases.by_slug("exam-university"))
        u["catalog"] = {"group": "ないジャンル", "tags": ["大学入試"]}
        self.assertTrue(any("catalog" in x for x in check_scenario(u, catalog_groups=set(catalog.GROUPS))))


if __name__ == "__main__":
    unittest.main()
