"""atomou skins: every colour pairing the page relies on meets its WCAG contrast ratio, every variable is defined, and a bad skin is caught."""
import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import skins  # noqa: E402

ASSETS = ROOT / "sites" / "atomou" / "assets"
DESIGN = ASSETS / "design.css"

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SHADOW_LAYER = re.compile(r"^(?:-?\d+(?:px)?\s+){2,4}rgba\(\d+,\d+,\d+,[0-9.]+\)$")
COLOUR_VARS = [v for v in skins.VARS if v not in skins.NON_COLOUR_VARS]

# (foreground, background, minimum ratio, why)
PAIRS = [
    ("text", "bg", 7.0, "body text on page"),
    ("text", "surface", 7.0, "body text on card"),
    ("muted", "surface", 4.5, "secondary text on card"),
    ("on-accent", "accent", 4.5, "main button"),
    ("on-ato", "ato", 4.5, "text on 'ato' colour"),
    ("on-mou", "mou", 4.5, "text on 'mou' colour"),
    ("ato-ink", "ato-soft", 4.5, "'ato' label: ink on its pale face"),
    ("mou-ink", "mou-soft", 4.5, "'mou' label: ink on its pale face"),
    ("ato-ink", "surface", 4.5, "'ato' ink on card"),
    ("mou-ink", "surface", 4.5, "'mou' ink on card"),
    ("ato", "surface", 3.0, "big 'ato' number on card"),
    ("mou", "surface", 3.0, "big 'mou' number on card"),
    ("quiet-text", "quiet-bg", 4.5, "quiet card text"),
    ("head-text", "head-bg", 4.5, "header"),
    ("foot-text", "foot-bg", 4.5, "footer"),
    ("band-text", "band-bg", 4.5, "hero band"),
    ("wm-ink", "head-bg", 4.5, "wordmark ink in the header"),
    ("wm-ato", "head-bg", 3.0, "wordmark 'あと' in the header"),
    ("wm-mou", "head-bg", 3.0, "wordmark 'もう' in the header"),
    ("accent", "bg", 4.5, "links and outline buttons on page"),
    ("accent", "surface", 4.5, "outline buttons on card"),
    ("focus", "bg", 3.0, "focus ring on page"),
    ("g1", "surface", 3.0, "genre mark 1 on card"),
    ("g2", "surface", 3.0, "genre mark 2 on card"),
    ("g3", "surface", 3.0, "genre mark 3 on card"),
    ("g4", "surface", 3.0, "genre mark 4 on card"),
    ("g5", "surface", 3.0, "genre mark 5 on card"),
    ("g6", "surface", 3.0, "genre mark 6 on card"),
    ("g7", "surface", 3.0, "genre mark 7 on card"),
    ("g8", "surface", 3.0, "genre mark 8 on card"),
    ("g9", "surface", 3.0, "genre mark 9 on card"),
    ("g10", "surface", 3.0, "genre mark 10 on card"),
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


def mix(a, b, t):
    """a + (b - a) * t in sRGB, as #RRGGBB (what CSS color-mix(in srgb, b t%, a) gives)."""
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(_rgb(a), _rgb(b)))


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
    # the secondary button in every skin: accent text on a face of 9% accent over the card (design.css `.btn.ghost`)
    face = mix(v["surface"], v["accent"], 0.09)
    if ratio(v["accent"], face) < 4.5:
        problems.append(f"{sid}: --accent on the ghost button face = {ratio(v['accent'], face):.2f} < 4.5 (secondary button)")
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
    if not re.fullmatch(r"\d(px)", v["bw"]) or not 1 <= int(v["bw"][0]) <= 4:
        problems.append(f"{sid}: --bw must be 1px-4px, got {v['bw']!r}")
    for k in ("font-head", "font-num"):
        if re.search(r"https?:|//|url\(|@import|src", v[k], re.I):
            problems.append(f"{sid}: --{k} must be system fonts only: {v[k]!r}")
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
    """Every skin (normal and seasonal)."""
    yield from skins.SKINS


class SkinListTest(unittest.TestCase):
    def test_count_and_basic_first(self):
        self.assertEqual(len(skins.normal_skins()), 21)
        self.assertEqual(skins.SKINS[0]["id"], "basic")
        self.assertEqual(skins.SKINS[0]["name"], "ベーシック")
        self.assertFalse(skins.SKINS[0]["dark"])
        self.assertNotIn("dark_vars", skins.SKINS[0])

    def test_ids_unique_and_well_formed(self):
        ids = [s["id"] for s in skins.SKINS]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^[a-z]+(-[a-z]+)*$")

    def test_meta(self):
        for s in skins.SKINS:
            for k in ("id", "name", "desc", "mood", "audience", "card", "dark", "attrs"):
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
        self.assertEqual(n, len(skins.SKINS))

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


class AttrsTest(unittest.TestCase):
    def test_every_skin_has_valid_attrs(self):
        for s in skins.SKINS:
            self.assertEqual(skins.attr_problems(s), [], s["id"])

    def test_every_attr_value_is_used_by_some_skin(self):
        for key, vals in skins.ATTR_VALUES.items():
            used = {s["attrs"][key] for s in skins.SKINS}
            self.assertEqual(used, set(vals), key)

    def test_basic_keeps_the_base_look(self):
        for key, vals in skins.ATTR_VALUES.items():
            self.assertEqual(skins.get("basic")["attrs"][key], vals[0], key)

    def test_skins_are_not_only_recoloured(self):
        """21 normal skins must differ in shape too: no two normal skins share the same eight attributes, and ten of them differ from every other skin in at least three."""
        normal = skins.normal_skins()
        shapes = [tuple(s["attrs"][k] for k in skins.ATTR_ORDER) for s in normal]
        self.assertEqual(len(set(shapes)), len(shapes))
        far = 0
        for i, a in enumerate(shapes):
            if all(sum(x != y for x, y in zip(a, b)) >= 3 for j, b in enumerate(shapes) if j != i):
                far += 1
        self.assertGreaterEqual(far, 10)
        # the skins with a character (everything except the readability-first ones) change the header or decorate the page
        plain = {"basic", "dark", "contrast", "large", "cb-safe", "ring", "nordic"}
        for s in normal:
            if s["id"] not in plain:
                self.assertTrue(s["attrs"]["head"] != "left" or s["attrs"]["deco"] != "none", s["id"])

    def test_bad_attrs_are_caught(self):
        s = copy.deepcopy(skins.get("pop"))
        s["attrs"]["head"] = "huge"
        self.assertTrue(any("attrs.head" in p for p in skins.attr_problems(s)))
        del s["attrs"]["btn"]
        self.assertTrue(any("attrs.btn is missing" in p for p in skins.attr_problems(s)))
        s["attrs"]["foo"] = "x"
        self.assertTrue(any("not a known key" in p for p in skins.attr_problems(s)))
        s2 = copy.deepcopy(skins.get("pop"))
        del s2["attrs"]
        self.assertTrue(skins.attr_problems(s2))


class SeasonTest(unittest.TestCase):
    def test_seasonal_skins_come_last_and_are_marked(self):
        flags = [skins.is_seasonal(s) for s in skins.SKINS]
        self.assertEqual(flags, sorted(flags))  # False first, then True
        self.assertEqual({s["id"] for s in skins.seasonal_skins()}, {"halloween", "christmas", "newyear", "valentine", "sakura", "summer", "tsukimi"})

    def test_season_fields(self):
        for s in skins.seasonal_skins():
            se = s["season"]
            self.assertRegex(se["from"], r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$", s["id"])
            self.assertRegex(se["to"], r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$", s["id"])
            self.assertTrue(se["label"].strip(), s["id"])
        self.assertEqual(skins.get("halloween")["season"], {"from": "10-10", "to": "11-02", "label": "ハロウィン"})

    def test_in_season_inclusive_and_across_new_year(self):
        from datetime import date
        h, n = skins.get("halloween"), skins.get("newyear")
        self.assertTrue(skins.in_season(h, date(2026, 10, 10)))
        self.assertTrue(skins.in_season(h, date(2026, 11, 2)))
        self.assertFalse(skins.in_season(h, date(2026, 10, 9)))
        self.assertFalse(skins.in_season(h, date(2026, 11, 3)))
        self.assertTrue(skins.in_season(n, date(2026, 12, 27)))
        self.assertTrue(skins.in_season(n, date(2027, 1, 10)))
        self.assertFalse(skins.in_season(n, date(2027, 1, 11)))
        self.assertFalse(skins.in_season(n, date(2026, 12, 26)))
        self.assertFalse(skins.in_season(skins.get("basic"), date(2026, 10, 10)))
        self.assertEqual([s["id"] for s in skins.current_seasons(date(2026, 10, 20))], ["halloween"])

    def test_every_day_of_the_year_is_handled(self):
        from datetime import date, timedelta
        d = date(2026, 1, 1)
        while d.year == 2026:
            skins.current_seasons(d)
            d += timedelta(days=1)


def design_problems(css: str, assets: Path) -> list[str]:
    """What is wrong with a design.css text (empty = fine)."""
    out = []
    if re.search(r"https?:|@import|@font-face|//[a-z]", css):
        out.append("an external address, @import or @font-face")
    if "prefers-color-scheme" in css:
        out.append("prefers-color-scheme (the page must not turn dark by itself)")
    if css.count("{") != css.count("}"):
        out.append("unbalanced braces")
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        for u in re.findall(r"url\((?!\"data:|%23)([^)]+)\)", m.group(2)):
            if not re.fullmatch(r"/assets/skins/[a-z0-9-]+\.webp", u):
                out.append(f"picture address not under /assets/skins/*.webp: {u}")
            elif not (assets / u.removeprefix("/assets/")).exists():
                out.append(f"picture missing: {u}")
            if "data-skin" not in m.group(1):
                out.append(f"picture {u} is named outside a data-skin selector (it would load for every skin)")
    return out


def button_problems(css: str) -> list[str]:
    """Button rules in design.css that would make a button look unpressable (Codex skin review r1: dashed and text-only buttons).
    Every rule whose selector names .btn (outside the quiet card and the toast) must not draw a dashed/dotted frame, remove the frame, or empty the face."""
    out = []
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        sel, body = m.group(1).strip(), m.group(2)
        if ".btn" not in sel or ".quiet" in sel or ".toast" in sel:
            continue
        decls = [d.strip().replace(" ", "") for d in body.split(";")]
        for d in decls:
            if re.match(r"border(-bottom|-top)?-style:(dashed|dotted)", d) or re.search(r"border:\d*\s*(dashed|dotted)", d):
                out.append(f"dashed button: {sel}")
            if re.match(r"border:0$|border:none$", d):
                out.append(f"button without a frame: {sel}")
            if d == "background:transparent":
                out.append(f"button without a face: {sel}")
    return out


class DesignCssTest(unittest.TestCase):
    """assets/design.css: the shape rules.  No external address, no font files, pictures only under their own skin, every picture present and small."""

    @classmethod
    def setUpClass(cls):
        cls.css = DESIGN.read_text(encoding="utf-8")
        cls.skins_dir = ASSETS / "skins"

    def test_design_css_is_clean(self):
        self.assertEqual(design_problems(self.css, ASSETS), [])
        self.assertTrue(re.search(r"url\(/assets/skins/", self.css))

    def test_the_check_catches_bad_css(self):
        bad = {
            "external": "body{background:url(https://example.com/a.png)}",
            "import": '@import "x.css";',
            "font": "@font-face{font-family:x}",
            "dark": "@media (prefers-color-scheme: dark){:root{--bg:#000}}",
            "braces": ":root{--a:1",
            "everywhere": "body{background:url(/assets/skins/pop.webp)}",
            "missing": ':root[data-skin="pop"]{--b:url(/assets/skins/nothing-here.webp)}',
            "elsewhere": ':root[data-skin="pop"]{--b:url(/img/pop.webp)}',
        }
        for name, css in bad.items():
            self.assertTrue(design_problems(css, ASSETS), name)
        self.assertEqual(design_problems(':root[data-skin="pop"]{--b:url(/assets/skins/pop.webp)}', ASSETS), [])

    def test_buttons_look_pressable_in_every_skin(self):
        self.assertEqual(button_problems(self.css), [])
        # the secondary button gets a face and a solid frame in every skin
        self.assertRegex(self.css, r":root\[data-skin\] \.btn\.ghost[^{]*\{[^}]*border:2px solid var\(--accent\)")

    def test_the_button_check_catches_the_old_rules(self):
        old = {
            "dashed ghost": ':root[data-btn="outline"] .btn.ghost{border-style:dashed}',
            "dashed underline": ':root[data-btn="underline"] .btn.ghost{border-bottom-style:dashed}',
            "text-only": ':root[data-btn="underline"] .btn{background:transparent;color:var(--accent);border:0;border-bottom:3px solid var(--accent)}',
            "transparent": ':root[data-btn="outline"] .btn{background:transparent;color:var(--accent);border-width:2px}',
        }
        for name, css in old.items():
            self.assertTrue(button_problems(css), name)
        # the quiet card and the toast keep their own quiet / white-on-dark buttons
        self.assertEqual(button_problems(':root[data-skin] .card.quiet .btn{background:transparent;border:2px solid var(--quiet-line)}'), [])
        self.assertEqual(button_problems('.toast.act .btn.ghost{background:transparent}'), [])

    def test_pictures_are_small(self):
        files = list(self.skins_dir.glob("*.webp"))
        self.assertGreaterEqual(len(files), 15)
        total = 0
        for f in files:
            self.assertLessEqual(f.stat().st_size, 60_000, f.name)
            total += f.stat().st_size
        self.assertLessEqual(total, 1_500_000)
        self.assertEqual({p.suffix for p in self.skins_dir.iterdir()}, {".webp"})

    def test_every_picture_is_used_by_some_skin(self):
        used = set(re.findall(r"/assets/skins/([a-z0-9-]+)\.webp", self.css))
        have = {f.stem for f in self.skins_dir.glob("*.webp")}
        self.assertEqual(have - used, set())

    def test_every_attribute_value_that_needs_rules_has_rules(self):
        for key, vals in skins.ATTR_VALUES.items():
            for v in vals[1:]:
                self.assertIn(f'[data-{key}="{v}"]', self.css, f"{key}={v}")

    def test_quiet_card_guard_exists(self):
        self.assertIn(".card.quiet::after", self.css)
        self.assertRegex(self.css, r"\.card\.quiet \.btn")

    def test_decorations_never_touch_the_quiet_card(self):
        # the corner mark and the number styles are written for .card:not(.quiet)
        self.assertRegex(self.css, r"\.card:not\(\.quiet\)::after")
        self.assertRegex(self.css, r"\.card:not\(\.quiet\) \.c-count \.num")


class SkinCssTest(unittest.TestCase):
    def test_every_skin_has_a_block_with_all_variables(self):
        out = skins.css()
        for s in skins.SKINS:
            m = re.search(r':root\[data-skin="' + re.escape(s["id"]) + r'"\]\{([^}]*)\}', out)
            self.assertIsNotNone(m, s["id"])
            body = m.group(1)
            for k in skins.VARS:
                self.assertIn(f"--{k}:", body, f"{s['id']} --{k}")

    def test_basic_is_default_and_never_follows_the_os_dark_mode(self):
        out = skins.css()
        self.assertIn(":root{--bg:#F7F7F5", out)
        self.assertNotIn("prefers-color-scheme", out)
        self.assertNotIn("@media", out)

    def test_design_css_does_not_follow_the_os_dark_mode_either(self):
        self.assertNotIn("prefers-color-scheme: dark", DESIGN.read_text(encoding="utf-8"))
        self.assertNotIn("prefers-color-scheme:dark", DESIGN.read_text(encoding="utf-8"))

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

    def test_pale_secondary_button_is_caught(self):
        s = self.good()
        s["vars"]["accent"] = "#8FB4F0"  # pale blue: fails on the tinted button face
        self.assertTrue(any("ghost button face" in p for p in check_skin(s)))

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
