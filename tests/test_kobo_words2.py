"""The desk's residual points (2026-11-04 evening): titles, repeated heading verbs, 全角？, dictionary entries."""
import unittest

from sokuhou.kobo import doc, engine, lexicon, style_rules


class Residual(unittest.TestCase):
    def test_a_title_with_kudasai_or_mashou_is_marked_and_dropped_from_the_vote(self):
        for t in ("パーソナルジムの契約は、持ち帰って決めてください", "停電に備えて電池を確認しましょう"):
            d = doc.parse("# " + t + "\n\n冒頭です。二文目です。\n\n## 見出し\n本文です。\n")
            self.assertIn("S20", [x["code"] for x in style_rules.check(d)], t)
            self.assertTrue(engine.BAD_TITLE.search(t), t)

    def test_the_same_verb_in_three_headings(self):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 水を確かめる\nあ。\n\n## 食料を確かめる\nい。\n\n## ライトを確かめる\nう。\n"
        self.assertIn("S37", [x["code"] for x in style_rules.check(doc.parse(md))])
        ok = "# 題\n\n冒頭です。二文目です。\n\n## 水を確かめる\nあ。\n\n## 食料を見る\nい。\n\n## ライトを選ぶ\nう。\n"
        self.assertNotIn("S37", [x["code"] for x in style_rules.check(doc.parse(ok))])

    def test_question_marks_and_the_new_entries(self):
        self.assertEqual(lexicon.autofix("## 足りない？ いくつ?\n\n本当ですか?")[0], "## 足りない？ いくつ？\n\n本当ですか？")
        self.assertEqual(lexicon.autofix("https://example.com/?a=1")[0], "https://example.com/?a=1")      # a URL is left alone
        self.assertTrue(lexicon.scan(["家族が代わりに相談するとき", "介護や見守りをしている人からの相談"])[0:1])
        self.assertIn("手に取れる場所", lexicon.autofix("すぐ手に取れる所にありますか")[0])
        self.assertTrue(lexicon.scan(["停電への備えは、いま見直す時期です。"]))
        self.assertTrue(lexicon.scan(["事前防災の徹底を求める緊急要請を出しました。"]))
        self.assertFalse(lexicon.scan(["「事前防災の徹底を求める緊急要請」と呼ばれます。"]))


class Summary(unittest.TestCase):
    def test_a_lead_sentence_repeated_in_the_summary_is_marked(self):
        md = ("# 題\n\n防災庁は2026年11月2日、家庭でやることを5つ呼びかけました。全部を一度に始めなくて大丈夫です。\n\n"
              "## 3行まとめ\n- 防災庁は2026年11月2日、家庭でやることを5つ呼びかけました。\n- 水は一人一日3リットルです。\n- どれから始めるかを選びます。\n\n## 見出し\n本文です。\n")
        self.assertIn("S53", [x["code"] for x in style_rules.check(doc.parse(md))])
        ok = md.replace("- 防災庁は2026年11月2日、家庭でやることを5つ呼びかけました。", "- 5つは、耐震診断と家具の固定、備蓄、ハザードマップの確認、持ち出し品の準備、防災訓練への参加です。")
        self.assertNotIn("S53", [x["code"] for x in style_rules.check(doc.parse(ok))])


class Wording(unittest.TestCase):
    def test_the_calculator_label_and_the_sonae_noun(self):
        from sokuhou.kobo import parts
        h = parts.calculator_html([{"name": "水", "rate": 3, "unit": "リットル"}])
        self.assertIn("いっしょに暮らす人数", h)
        self.assertNotIn("家の人数", h)
        self.assertIn("水と食料、必要な量", lexicon.autofix("水と食料の数え方")[0])
        self.assertIn("携帯トイレ、必要な数", lexicon.autofix("携帯トイレの数え方")[0])
        self.assertEqual(lexicon.autofix("足りない備えを増やす")[0], "足りない防災グッズを増やす")
        self.assertEqual(lexicon.autofix("水や食料などの備えは足りていますか")[0], "水や食料などの備蓄は足りていますか")
        self.assertFalse(lexicon.scan(["災害への備えが大事です。"]))             # the general use stays
        self.assertTrue(lexicon.scan(["家にある備えに□をつけます。"]))


class SeparateStories(unittest.TestCase):
    def test_typhoon_and_the_agency_call_in_one_lead_or_paragraph_are_marked(self):
        md = ("# 題\n\n台風31号は直撃しない予報です。防災庁は11月2日、備えを呼びかけました。\n\n## 見出し\n本文です。\n\n## 別の節\n台風と同じころ、防災庁は呼びかけました。\n")
        marks = [x for x in style_rules.check(doc.parse(md)) if x["code"] == "S45"]
        self.assertEqual(len(marks), 2)                                       # the lead and the paragraph
        ok = ("# 題\n\n台風31号は直撃しない予報です。備えは足りていますか。\n\n## 見出し\n本文です。\n\n## 別の節\n国の防災庁は11月2日、備えを呼びかけました。\n")
        self.assertFalse([x for x in style_rules.check(doc.parse(ok)) if x["code"] == "S45"])
        self.assertTrue(lexicon.scan(["台風と同じころ、防災庁は呼びかけました。"]))
        self.assertFalse(lexicon.scan(["国の防災庁は11月2日、水と食料を備えるよう呼びかけました。"]))


class Residual2(unittest.TestCase):
    def test_square_in_the_lead_and_mixed_summary_endings(self):
        md = ("# 題\n\n冒頭に□をつけます。二文目です。\n\n## 3行まとめ\n- 一つ目です。\n- 二つ目は、そろえる。\n- 三つ目です。\n\n## 見出し\n本文です。\n")
        codes = [x["code"] for x in style_rules.check(doc.parse(md))]
        self.assertIn("S43", codes)
        self.assertIn("S44", codes)
        ok = md.replace("□をつけ", "確かめ").replace("そろえる。", "そろえます。")
        self.assertNotIn("S44", [x["code"] for x in style_rules.check(doc.parse(ok))])


if __name__ == "__main__":
    unittest.main()


class DeAndOku(unittest.TestCase):
    def test_deru_and_oku_words(self):
        hit = ["回数が出たら、次へ進みます。", "表で出した回数に届くものを選びます。", "買い足す数を出す", "手の届く場所に置きます。", "手元に置いて読みます。"]
        ok = ["ライトを出して、一度点けます。", "外に出る前に確認します。", "熱が出たら休みます。", "水道水の汲み置きは3日ほどです。", "古い電池の買い置きを数えます。", "置き場所を決めます。", "位置を測ります。"]
        for t in hit:
            self.assertTrue(lexicon.scan([t]), t)
        for t in ok:
            self.assertFalse(lexicon.scan([t]), t)


class SubjectPredicate(unittest.TestCase):
    """The owner's points of 2026-11-05 are the negative examples: each must be marked, and the natural rewrite must not be."""

    def _codes(self, body):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n" + body + "\n"
        return [x["code"] for x in style_rules.check(doc.parse(md))]

    def test_s54_catches_any_word_before_demasu(self):
        for t in ("額が出ます。", "幅が出ます。", "水の量が出ます。", "結果が出ます。"):
            self.assertTrue([h for h in lexicon.scan([t]) if h.get("code") == "S54"], t)
        for t in ("ライトを出して点けます。", "熱が出たら休みます。", "ごみを出す日です。", "新しい話が出ると、迷います。"):
            self.assertFalse([h for h in lexicon.scan([t]) if h.get("code") == "S54"], t)

    def test_s56_quantity_subject_with_a_doing_verb(self):
        self.assertIn("S56", self._codes("水の必要量は、人数と日数をかけて計算します。"))
        self.assertIn("S56", self._codes("足りない防災グッズは、いつもの買い物で買い足します。"))
        self.assertIn("S56", self._codes("まず3日分をそろえて、あとから1週間分まで増やします。"))
        self.assertNotIn("S56", self._codes("水の必要量は、人数と日数をかけて計算できます。"))
        self.assertNotIn("S56", self._codes("足りない防災グッズは、買い足していきます。"))
        self.assertNotIn("S56", self._codes("あとから1週間分まで増やしていきます。"))

    def test_s57_a_sentence_that_starts_in_the_middle(self):
        bad = "防災庁は、水と食料を最低3日分備蓄することをすすめています。食事に使う分も含めて、1人1日3リットルです。"
        self.assertIn("S57", self._codes(bad))
        self.assertIn("S57", self._codes("その量は、人数で決まります。"))
        self.assertNotIn("S57", self._codes("防災庁は、水と食料を最低3日分備蓄することをすすめています。水は、食事に使う分も含めて、1人1日3リットルです。"))
        self.assertNotIn("S57", self._codes("これからの流れを書きます。"))


class SeoKeyword(unittest.TestCase):
    def test_keyword_in_title_lead_and_description(self):
        m = {"keyword": "防災グッズ チェックリスト", "description": "水・食料・携帯トイレなど8項目の一覧で、家に足りない防災グッズを確かめるチェックリストです。"}
        bad = doc.parse("# 防災グッズ、本当に足りていますか？\n\nきっかけは防災庁の呼びかけです。8項目あります。\n\n## 見出し\n本文です。\n")
        ok = doc.parse("# 防災グッズのチェックリスト、8項目で見直す\n\n防災グッズのチェックリストで、家に足りないものが分かります。8項目に□をつけます。\n\n## 見出し\n本文です。\n")
        self.assertEqual(sorted({x["code"] for x in style_rules.seo_check(bad, m)}), ["S58"])
        self.assertGreaterEqual(len(style_rules.seo_check(bad, m)), 2)                 # title and lead
        self.assertEqual(style_rules.seo_check(ok, m), [])
        self.assertTrue(style_rules.seo_check(ok, dict(m, description="")))            # no description
        self.assertTrue(style_rules.seo_check(ok, dict(m, description="防災グッズのチェックリストで、家に足りないものが分かります。")))   # the lead copied
        self.assertEqual(style_rules.seo_check(bad, {}), [])                           # no keyword: not checked


class OwnerNov5Evening(unittest.TestCase):
    def _codes(self, md):
        return [x["code"] for x in style_rules.check(doc.parse(md))]

    def test_box_symbol_is_replaced(self):
        self.assertEqual(lexicon.autofix("家にあるものに□をつけると分かります。")[0], "家にあるものにチェックを入れると分かります。")
        self.assertEqual(lexicon.autofix("□のつかなかった項目から買います。")[0], "チェックのない項目から買います。")
        self.assertTrue(lexicon.scan(["□を見ます。"]))

    def test_masu_run_is_marked_and_a_mix_is_not(self):
        bad = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n水を見ます。食料を書いておきます。ライトを選びます。\n"
        ok = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n水を見ます。食料は、賞味期限を書いておくと分かります。ライトは、両手があくものが使いやすいです。\n"
        self.assertIn("S59", self._codes(bad))
        self.assertNotIn("S59", self._codes(ok))

    def test_thing_topic_with_a_persons_act(self):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\nライトは、停電の暗さに備えます。\n\nラジオは、情報を聞く手段のひとつです。スマホとは別の手段として、そろえておきます。\n"
        self.assertEqual(sum(1 for c in self._codes(md) if c == "S56"), 2)
        ok = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\nライトは、停電の暗さに備える防災グッズです。\n\nラジオは、スマホとは別の情報の手段になります。\n"
        self.assertNotIn("S56", self._codes(ok))

    def test_the_same_gist_in_many_places_and_the_closing(self):
        md = ("# 題\n\n冒頭です。二文目です。\n\n## 3行まとめ\n- 足りない防災グッズから、1つずつ買い足します。\n- 二です。\n- 三です。\n\n"
              "## 見出し\n足りない防災グッズから、1つずつ買い足していきます。\n\n> ライフハック: 小さな話\n> 箱の中の話です。\n")
        c = self._codes(md)
        self.assertIn("S60", c)
        self.assertIn("S61", c)                                       # it ends on a box
        ok = md.replace("足りない防災グッズから、1つずつ買い足していきます。", "チェックのない項目を1つ選びます。").replace("- 足りない防災グッズから、1つずつ買い足します。", "- 水は、1人1日3リットルです。")
        ok += "\n## まとめ: 今日は、足りない防災グッズを1つ決める\nこのページのまとめです。今日は、足りない防災グッズを1つ決めるところから始めるとよいです。\n"
        self.assertNotIn("S60", self._codes(ok))
        self.assertNotIn("S61", self._codes(ok))


class ClosingAndNounEndings(unittest.TestCase):
    def _codes(self, md):
        return [x["code"] for x in style_rules.check(doc.parse(md))]

    def test_closing_section_needs_matome_heading_and_opening(self):
        base = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n本文です。\n\n"
        bad = base + "## 今日は、足りない防災グッズを1つ決める\n今日は、1つ選んで始めるとよいです。\n"
        ok = base + "## まとめ: 今日は、足りない防災グッズを1つ決める\nこのページのまとめです。答えは、チェックのない項目を見ることです。今日は、1つ選んで始めるとよいです。\n"
        noopen = base + "## まとめ: 今日は1つ決める\n答えは、チェックのない項目を見ることです。今日は、1つ選びます。\n"
        self.assertIn("S61", self._codes(bad))
        self.assertNotIn("S61", self._codes(ok))
        self.assertIn("S61", self._codes(noopen))

    def test_the_same_noun_ending_in_a_row(self):
        bad = ("# 題\n\n冒頭です。二文目です。\n\n## 見出し\n電池と充電は、スマホの電池を残すための用意です。\n\n救急用品は、けがの手当てに使うものの用意です。\n")
        ok = ("# 題\n\n冒頭です。二文目です。\n\n## 見出し\n電池と充電の役目は、スマホの電池を残すことです。\n\n救急用品は、けがの手当てが中心です。\n")
        self.assertIn("S63", self._codes(bad))
        self.assertNotIn("S63", self._codes(ok))
        self.assertTrue(lexicon.scan(["足りないものと、読むページが分かります。"]))


class OwnersAiWords(unittest.TestCase):
    def test_ai_words_are_marked_and_concrete_uses_are_left(self):
        for t in ["必要な回数に届くものを選びます。", "ライトを用意します。", "目安が分かります。", "備蓄を残すことです。", "資料に載っています。", "量が決まります。", "読むとよいページが下に表示されます。"]:
            self.assertTrue(lexicon.scan([t]), t)
        for t in ["手の届く場所に出します。", "宅配で荷物が届きます。", "契約書を用意して行きます。"]:
            self.assertFalse(lexicon.scan([t]), t)


class OwnersAiWords2(unittest.TestCase):
    def test_more_ai_words(self):
        for t in ["本数が要ります。", "手順を一つずつ進めます。", "流れがつかめます。", "ラジオは情報を得る手段です。", "リンクがつきます。"]:
            self.assertTrue(lexicon.scan([t]), t)
        for t in ["重要な点です。", "移動の手段です。", "ご覧いただくよう勧めます。"]:
            self.assertFalse(lexicon.scan([t]), t)

    def test_candidates_come_from_phrases_the_human_documents_do_not_use(self):
        from sokuhou.kobo import aiwords
        texts = {"a": "手順を進めます。話を進めます。", "b": "予約を進めます。確認します。確認します。確認します。"}
        human = {"確認します": [9, 5]}
        keys = [r["key"] for r in aiwords.candidates(texts, human, min_out=3)]
        self.assertIn("進めます", keys)
        self.assertNotIn("確認します", keys)


class ThingAndQuantity(unittest.TestCase):
    def _s77(self, t):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n" + t + "\n"
        return [x["code"] for x in style_rules.check(doc.parse(md)) if x["code"] == "S77"]

    def test_topic_and_predicate_do_not_fit(self):
        for t in ["食料は、水と同じ日数分です。", "携帯トイレは、1日5から6回×人数×7日分です。", "水は、人数×日数×3リットルです。"]:
            self.assertTrue(self._s77(t), t)
        for t in ["食料も、水と同じ日数分が必要です。", "携帯トイレは、7日分が必要です。", "水は、1人1日3リットルが目安です。", "ライトは、1人1本です。", "電池は、4本で足ります。"]:
            self.assertFalse(self._s77(t), t)
        self.assertTrue(lexicon.scan(["最低3日分をめざします。"]))


class OwnerNightRules(unittest.TestCase):
    def _codes(self, body, box=""):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n" + body + "\n" + box
        return [x["code"] for x in style_rules.check(doc.parse(md))]

    def test_each_rule_marks_the_example_and_not_the_fix(self):
        self.assertIn("S79", self._codes("1つずつで足り、慌てて買い込む必要はありません。"))
        self.assertNotIn("S79", self._codes("まずは、1つずつで足ります。慌てて買い込む必要はありません。"))
        self.assertIn("S80", self._codes("本文です。", "\n> ライフハック: 保管\n> 玄関の隅に分けて保管します。\n"))
        self.assertNotIn("S80", self._codes("本文です。", "\n> ライフハック: 保管\n> 玄関の隅に分けて保管しましょう。\n"))
        self.assertIn("S81", self._codes("そのページを開くところから始めるとよいです。"))
        self.assertIn("S82", self._codes("水と食料は、1人1日3リットルを目安に、最低3日分をそろえます。"))
        self.assertNotIn("S82", self._codes("水は、1人1日3リットルを目安にします。水と食料とも、最低3日分をそろえます。"))
        self.assertIn("S83", self._codes("これをくり返すのが、ローリングストックです。"))
        self.assertNotIn("S83", self._codes("ローリングストックとは、少し多めに買って使う方法です。"))


class DecideWord(unittest.TestCase):
    def test_decide_is_marked_unless_concrete(self):
        for t in ["今日は、足りない防災グッズを1つ決めて、始めます。", "避難情報を見る先を決めます。"]:
            self.assertTrue(lexicon.scan([t]), t)
        for t in ["その場では決めずに、持ち帰ります。", "返事の日を決めます。", "何から買うか決めやすくなります。"]:
            self.assertFalse(lexicon.scan([t]), t)


class TimeClash(unittest.TestCase):
    def _s85(self, t):
        md = "# 題\n\n冒頭です。二文目です。\n\n## 見出し\n" + t + "\n"
        return [x["code"] for x in style_rules.check(doc.parse(md)) if x["code"] == "S85"]

    def test_topic_time_and_predicate_time(self):
        self.assertTrue(self._s85("今日は、足りないものを1つだけ、次の買い物のかごに入れましょう。"))
        self.assertTrue(self._s85("今日は、あとで読む本を選びます。"))
        self.assertFalse(self._s85("今は、来週の予定を確かめます。"))
        self.assertFalse(self._s85("次の買い物では、足りないものを1つだけ、かごに入れましょう。"))
        self.assertFalse(self._s85("今日は、次のページで量を確かめます。"))


class NineMoreWords(unittest.TestCase):
    def test_nine_owner_words(self):
        for t in ["回数を考えます。", "まず、そこを確かめます。", "ライトを選びます。", "ここを見ます。", "備蓄を増やせます。", "買い物の中身を入れます。", "窓口で聞けます。", "気持ちを伝えます。", "ここに書き込みます。"]:
            self.assertTrue([h for h in lexicon.scan([t]) if h.get("code") in {f"S{n}" for n in range(86, 95)}], t)
        for t in ["持ち帰って考えます。", "充電が残っているか確かめます。", "ベランダの物を家の中に入れます。", "表に書き込みます。"]:
            self.assertFalse([h for h in lexicon.scan([t]) if h.get("code") in {f"S{n}" for n in range(86, 95)}], t)
