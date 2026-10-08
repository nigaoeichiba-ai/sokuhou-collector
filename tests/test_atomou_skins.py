"""atomou skins: every colour pairing the page relies on meets its WCAG contrast ratio, every variable is defined, and a bad skin is caught."""
import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import skins  # noqa: E402

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SHADOW_LAYER = re.compile(r"^(?:-?\d+(?:px)?\s+){2,4}rgba\(\d+,\d+,\d+,[0-9.]+\)$")
COLOUR_VARS = [v for v in skins.VARS if v not in ("radius", "shadow", "font", "size", "num-weight", "bg-image")]

# (foreground, background, minimum ratio, why)
PAIRS = [
    ("text", "bg", 7.0, "body text on page"),
    ("text", "surface", 7.0, "body text on card"),
    ("muted", "surface", 4.5, "secondary text on card"),
    ("on-accent", "accent", 4.5, "main button"),
    ("on-ato", "ato", 4.5, "text on 'ato' colour"),
    ("on-mou", "mou", 4.5, "text on 'mou' colour"),
    ("ato", "surface", 3.0, "big 'ato' number on card"),
    ("mou", "surface", 3.0, "big 'mou' number on card"),
    ("quiet-text", "quiet-bg", 4.5, "quiet card text"),
    ("head-text", "head-bg", 4.5, "header"),
    ("foot-text", "foot-bg", 4.5, "footer"),
    ("focus", "bg", 3.0, "focus ring on page"),
    ("g1", "surface", 3.0, "genre mark 1 on card"),
    ("g2", "surface", 3.0, "genre mark 2 on card"),
    ("g3", "surface", 3.0, "genre mark 3 on card"),
    ("g4", "surface", 3.0, "genre mark 4 on card"),
    ("g5", "surface", 3.0, "genre mark 5 on card"),
    ("g6", "surface", 3.0, "genre mark 6 on card"),
]
STRICT = {"contrast", "large"}  # these two need >= 10 for the text pairs
STRICT_PAIRS = {("text", "bg"), ("text", "surface")}


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def luminance(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def chroma(h):
    r, g, b = _rgb(h)
    return (max(r, g, b) - min(r, g, b)) / 255


def check_skin(skin):
    """Return a list of problems for one skin dict (empty = fine)."""
    problems = []
    v = skin.get("vars", {})
    sid = skin.get("id", "?")
    for k in skins.VARS:
        if k not in v or not str(v[k]).strip():
            problems.append(f"{sid}: --{k} is missing")
    for k in COLOUR_VARS:
        if k in v and not HEX.match(v[k]):
            problems.append(f"{sid}: --{k} is not #RRGGBB: {v[k]!r}")
    if problems:
        return problems
    strict = skin["id"] in STRICT or skin.get("strict")
    for fg, bg, need, why in PAIRS:
        if strict and (fg, bg) in STRICT_PAIRS:
            need = 10.0
        r = ratio(v[fg], v[bg])
        if r < need:
            problems.append(f"{sid}: --{fg}/--{bg} = {r:.2f} < {need} ({why})")
    # quiet card: lower saturation than its surroundings, and visibly its own surface
    if chroma(v["quiet-bg"]) > 0.12:
        problems.append(f"{sid}: --quiet-bg is too colourful ({chroma(v['quiet-bg']):.2f})")
    if chroma(v["quiet-line"]) > 0.15:
        problems.append(f"{sid}: --quiet-line is too colourful")
    if chroma(v["quiet-text"]) > max(0.2, chroma(v["ato"]) * 0.6):
        problems.append(f"{sid}: --quiet-text is too colourful")
    if v["quiet-bg"].upper() == v["surface"].upper():
        problems.append(f"{sid}: --quiet-bg equals --surface")
    # ato and mou must differ (not only by shape)
    if v["ato"].upper() == v["mou"].upper():
        problems.append(f"{sid}: --ato equals --mou")
    # dark flag matches the background
    lum = luminance(v["bg"])
    if skin.get("dark") and lum > 0.2:
        problems.append(f"{sid}: marked dark but --bg is light")
    if not skin.get("dark") and lum < 0.4:
        problems.append(f"{sid}: marked light but --bg is dark")
    # style variables
    size = re.fullmatch(r"(\d+)px", v["size"])
    if not size or not 16 <= int(size.group(1)) <= 22:
        problems.append(f"{sid}: --size must be 16px-22px, got {v['size']!r}")
    if not re.fullmatch(r"\d{3}", v["num-weight"]) or not 500 <= int(v["num-weight"]) <= 900:
        problems.append(f"{sid}: --num-weight must be 500-900, got {v['num-weight']!r}")
    if not re.fullmatch(r"\d+px", v["radius"]):
        problems.append(f"{sid}: bad --radius {v['radius']!r}")
    if v["shadow"] != "none" and not all(SHADOW_LAYER.match(x.strip()) for x in re.split(r",(?![^(]*\))", v["shadow"])):
        problems.append(f"{sid}: bad --shadow {v['shadow']!r}")
    if re.search(r"https?:|//|url\(|@import|\bsrc\b", v["font"], re.I):
        problems.append(f"{sid}: --font must be system fonts only: {v['font']!r}")
    bi = v["bg-image"]
    if bi != "none" and (not re.match(r"^(linear|radial|repeating-linear|repeating-radial)-gradient\(", bi) or re.search(r"url\(|https?:|//", bi, re.I)):
        problems.append(f"{sid}: --bg-image must be 'none' or a CSS gradient: {bi!r}")
    return problems


def all_variants():
    """Every skin, plus basic's dark values as a skin of its own."""
    for s in skins.SKINS:
        yield s
        if s.get("dark_vars"):
            d = dict(s)
            d.update(id=s["id"] + "(dark)", vars=s["dark_vars"], dark=True)
            yield d


class SkinListTest(unittest.TestCase):
    def test_count_and_basic_first(self):
        self.assertGreaterEqual(len(skins.SKINS), 18)
        self.assertEqual(skins.SKINS[0]["id"], "basic")
        self.assertEqual(skins.SKINS[0]["name"], "ベーシック")
        self.assertTrue(skins.SKINS[0].get("dark_vars"))

    def test_ids_unique_and_well_formed(self):
        ids = [s["id"] for s in skins.SKINS]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^[a-z]+(-[a-z]+)*$")

    def test_meta(self):
        for s in skins.SKINS:
            for k in ("id", "name", "desc", "mood", "audience", "card", "dark"):
                self.assertIn(k, s, s.get("id"))
            self.assertIn(s["card"], skins.CARDS, s["id"])
            self.assertIsInstance(s["dark"], bool)
            self.assertTrue(s["name"].strip() and s["mood"].strip() and s["audience"].strip())
            self.assertLessEqual(len(s["desc"]), 30, s["id"])
            self.assertGreater(len(s["desc"]), 0)
        names = [s["name"] for s in skins.SKINS]
        self.assertEqual(len(names), len(set(names)))

    def test_required_skins_exist(self):
        have = set(skins.ids())
        for need in ("basic", "dark", "contrast", "large", "cb-safe", "wafuu", "kids", "neon"):
            self.assertIn(need, have)

    def test_every_card_kind_is_used(self):
        self.assertEqual({s["card"] for s in skins.SKINS}, set(skins.CARDS))

    def test_no_audience_label_by_gender_or_nationality(self):
        for s in skins.SKINS:
            for bad in ("男性", "女性", "男の", "女の", "日本人", "外国人"):
                self.assertNotIn(bad, s["audience"] + s["mood"] + s["desc"], s["id"])


class SkinColourTest(unittest.TestCase):
    def test_all_variables_defined_and_all_pairs_pass(self):
        n = 0
        for s in all_variants():
            self.assertEqual(check_skin(s), [], s["id"])
            n += 1
        self.assertGreaterEqual(n, 19)

    def test_pair_count_per_skin(self):
        self.assertGreaterEqual(len(PAIRS), 18)

    def test_strict_skins_reach_ten(self):
        for sid in STRICT:
            v = skins.get(sid)["vars"]
            self.assertGreaterEqual(ratio(v["text"], v["bg"]), 10, sid)
            self.assertGreaterEqual(ratio(v["text"], v["surface"]), 10, sid)

    def test_large_text_size(self):
        self.assertEqual(skins.get("large")["vars"]["size"], "20px")

    def test_no_external_fonts_anywhere(self):
        for s in skins.SKINS:
            self.assertNotRegex(s["vars"]["font"], r"https?:|url\(|@import|//")
        self.assertNotRegex(skins.css(), r"https?:|url\(|@import|@font-face")

    def test_dark_skins_have_dark_background(self):
        for s in skins.SKINS:
            lum = luminance(s["vars"]["bg"])
            if s["dark"]:
                self.assertLess(lum, 0.2, s["id"])
            else:
                self.assertGreater(lum, 0.4, s["id"])

    def test_quiet_card_is_calmer_than_accent(self):
        for s in all_variants():
            v = s["vars"]
            self.assertLessEqual(chroma(v["quiet-bg"]), 0.12, s["id"])


class SkinCssTest(unittest.TestCase):
    def test_every_skin_has_a_block_with_all_variables(self):
        out = skins.css()
        for s in skins.SKINS:
            m = re.search(r':root\[data-skin="' + re.escape(s["id"]) + r'"\]\{([^}]*)\}', out)
            self.assertIsNotNone(m, s["id"])
            body = m.group(1)
            for k in skins.VARS:
                self.assertIn(f"--{k}:", body, f"{s['id']} --{k}")

    def test_basic_is_default_and_follows_os_dark(self):
        out = skins.css()
        self.assertIn(":root{--bg:#F7F7F5", out)
        m = re.search(r"@media \(prefers-color-scheme: dark\)\{:root:not\(\[data-skin\]\)\{([^}]*)\}\}", out)
        self.assertIsNotNone(m)
        for k in skins.VARS:
            self.assertIn(f"--{k}:", m.group(1))
        self.assertIn("--bg:#121316", m.group(1))
        self.assertEqual(out.count("prefers-color-scheme"), 1)  # only basic follows the OS

    def test_braces_balanced(self):
        out = skins.css()
        self.assertEqual(out.count("{"), out.count("}"))

    def test_card_is_not_a_css_variable(self):
        self.assertNotIn("--card", skins.css())


class NegativeTest(unittest.TestCase):
    """The checker must catch bad skins (a check that cannot fail proves nothing)."""

    def good(self):
        return copy.deepcopy(skins.get("basic"))

    def test_good_skin_passes(self):
        self.assertEqual(check_skin(self.good()), [])

    def test_low_contrast_text_is_caught(self):
        s = self.good()
        s["vars"]["text"] = "#9A9A9A"
        out = check_skin(s)
        self.assertTrue(any("--text/--bg" in p for p in out), out)
        self.assertTrue(any("--text/--surface" in p for p in out), out)

    def test_low_contrast_button_is_caught(self):
        s = self.good()
        s["vars"]["on-accent"] = "#7FB0FF"
        self.assertTrue(any("--on-accent/--accent" in p for p in check_skin(s)))

    def test_pale_ato_number_is_caught(self):
        s = self.good()
        s["vars"]["ato"] = "#CCE0FF"
        self.assertTrue(any("--ato/--surface" in p for p in check_skin(s)))

    def test_pale_muted_text_is_caught(self):
        s = self.good()
        s["vars"]["muted"] = "#A0A0A0"
        self.assertTrue(any("--muted/--surface" in p for p in check_skin(s)))

    def test_quiet_text_footer_header_focus_are_caught(self):
        for key, pair in (("quiet-text", "--quiet-text"), ("head-text", "--head-text"), ("foot-text", "--foot-text"), ("focus", "--focus/--bg")):
            s = self.good()
            s["vars"][key] = "#F4F4F4" if key != "foot-text" else "#2B2F37"
            self.assertTrue(any(pair in p for p in check_skin(s)), key)

    def test_genre_colour_too_pale_is_caught(self):
        s = self.good()
        s["vars"]["g3"] = "#FFD6E0"
        self.assertTrue(any("--g3/--surface" in p for p in check_skin(s)))

    def test_missing_variable_is_caught(self):
        s = self.good()
        del s["vars"]["quiet-line"]
        self.assertTrue(any("--quiet-line is missing" in p for p in check_skin(s)))

    def test_bad_colour_format_is_caught(self):
        s = self.good()
        s["vars"]["bg"] = "white"
        self.assertTrue(any("not #RRGGBB" in p for p in check_skin(s)))

    def test_size_out_of_range_is_caught(self):
        for bad in ("12px", "30px", "1rem"):
            s = self.good()
            s["vars"]["size"] = bad
            self.assertTrue(any("--size" in p for p in check_skin(s)), bad)

    def test_external_font_is_caught(self):
        s = self.good()
        s["vars"]["font"] = '"Foo",url(https://fonts.example.com/foo.woff2)'
        self.assertTrue(any("--font" in p for p in check_skin(s)))

    def test_image_url_in_bg_image_is_caught(self):
        s = self.good()
        s["vars"]["bg-image"] = "url(tex.png)"
        self.assertTrue(any("--bg-image" in p for p in check_skin(s)))

    def test_colourful_quiet_card_is_caught(self):
        s = self.good()
        s["vars"]["quiet-bg"] = "#FFD0D0"
        self.assertTrue(any("--quiet-bg is too colourful" in p for p in check_skin(s)))

    def test_dark_flag_mismatch_is_caught(self):
        s = self.good()
        s["dark"] = True
        self.assertTrue(any("marked dark" in p for p in check_skin(s)))

    def test_strict_threshold_catches_a_skin_that_would_pass_normally(self):
        s = copy.deepcopy(skins.get("basic"))
        s["vars"]["text"] = "#4A4A4A"  # about 8:1, fine for a normal skin
        self.assertEqual([p for p in check_skin(s) if "--text/" in p], [])
        s["strict"] = True
        self.assertTrue(any("--text/--bg" in p for p in check_skin(s)))


class RatioTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(ratio("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(ratio("#777777", "#FFFFFF"), 4.48, places=1)
        self.assertAlmostEqual(ratio("#FFFFFF", "#FFFFFF"), 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
