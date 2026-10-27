"""みんなのイラスト: the 使い分けのガイド of a featured set (/series/<slug>/).

A featured set gets what a list of pictures cannot say by itself: which picture is for what, how big each one really prints, where a frame is empty, and a few finished examples made
only from the set's own pictures (setexamples.py).  The words are written by hand for each set after looking at every picture; every number is measured from the files in the build.
Nothing here is said about print quality that has not been measured: the print sizes are the pixels divided by the dpi, nothing more.
"""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
EXAMPLES_DIR = HERE / "assets" / "examples"


def inner_box(im: Image.Image, alpha_max: int = 24) -> tuple[int, int, int, int]:
    """The biggest empty (transparent) rectangle that grows from the centre of a picture, as (x0, y0, x1, y1) in the picture's own pixels: where a frame lets a photo or a text show."""
    a = np.array(im.convert("RGBA"))[:, :, 3] > alpha_max
    h, w = a.shape
    x0, x1, y0, y1 = w // 2, w // 2 + 1, h // 2, h // 2 + 1
    if a[h // 2, w // 2]:
        return (w // 2, h // 2, w // 2, h // 2)
    grown = True
    while grown:
        grown = False
        if x0 > 0 and not a[y0:y1, x0 - 1].any():
            x0 -= 1
            grown = True
        if x1 < w and not a[y0:y1, x1].any():
            x1 += 1
            grown = True
        if y0 > 0 and not a[y0 - 1, x0:x1].any():
            y0 -= 1
            grown = True
        if y1 < h and not a[y1, x0:x1].any():
            y1 += 1
            grown = True
    return (x0, y0, x1, y1)


def mm(px: int, dpi: int) -> int:
    return round(px / dpi * 25.4)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# slug -> the words of the set.  "picks" is keyed by the end of each picture's id (what comes after the set's slug and a hyphen); every picture of the set has one line.
GUIDES: dict[str, dict] = {
    "event-frames-flat": {
        "why": "行事ごとの飾り枠12枚です。どれも真ん中が透明で、写真や文字を入れる前提で描かれています。おたよりの見出し、掲示物、行事の案内に向きます。",
        "frame": True,
        "picks": {
            "undokai": "運動会・スポーツ大会の案内。旗とメダル、足元に走路があり、プログラムの表紙や結果の写真に。",
            "shojo": "賞状・表彰の飾り。金の縁の赤い枠で、感謝状や修了のお知らせに。飾りであって、証書そのものではありません。",
            "oshogatsu": "日の出と松竹梅、水引。新年のあいさつやお正月のお知らせに。",
            "otsukimi": "夜空・すすき・月見だんご。お月見会の案内、9月と10月のおたよりに。",
            "halloween": "かぼちゃ・こうもり・クモの巣。ハロウィンの会や10月の掲示に。",
            "sotsugyo": "桜と卒業証書・学帽。卒業・修了のお知らせ、3月のおたよりに。",
            "kyushoku": "パン・牛乳・スプーン。給食だよりの見出しや献立表に。",
            "obento": "おにぎり・卵焼き・ミニトマト。お弁当の日や遠足の持ち物のお知らせに。",
            "pop": "星とギザギザの派手な枠。セールやイベントのPOP、子ども向けの掲示に。",
            "christmas": "ベルとヒイラギ、プレゼント。クリスマス会の案内やカードに。",
            "dokusho": "秋の葉と本・めがね。読書週間や図書だよりに。",
            "nenga": "ひつじと雲。2027年(未年)の年賀状に。",
        },
        "examples": [
            ("event-frames-flat-1", "運動会のお知らせの見本。「運動会のフレーム」を元の大きさのまま置き、枠の中に文字を入れました。日付は空欄(○)です。",
             ["event-frames-flat-undokai"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("event-frames-flat-2", "給食だよりの見出しの見本。「給食のフレーム」の中にタイトルを入れました。",
             ["event-frames-flat-kyushoku"], "正方形のSNS・おたより用の大きさ"),
        ],
    },
    "bowing-greetings-flat": {
        "why": "お辞儀・あいさつをする人物の素材です。仕事や場面ごとに服装が違うので、お知らせの「ごあいさつ」を誰が言っているように見せたいかで選べます。",
        "frame": False,
        "picks": {
            "hoikushi": "ピンクのエプロンの保育士。園のおたより、入園・見学のご案内に。",
            "nurse": "白い服の看護師。医院の案内や院内掲示のごあいさつに。",
            "newbie": "スーツの新入社員。配属・入社のあいさつ、会社案内や研修資料に。",
            "clerk": "緑のエプロンの店員。「ご来店ありがとうございます」のPOPや店内の案内に。",
            "teacher": "ドアのそばでお辞儀をする先生。教室・塾のお知らせに。ドアが絵の一部なので、横幅が広めです。",
            "doctor": "白衣と聴診器の医師。診療所の案内、診療時間のお知らせに。",
            "host": "手を差し出して案内する係(お辞儀ではなく、案内の身ぶり)。受付や順路の案内に。",
            "thanks": "深く頭を下げる男性。お礼状や感謝のお知らせに。",
            "sorry": "肩をすぼめて頭を下げる女性。おわびの文面や、予定変更のお知らせに。",
            "wave": "手を振る男の子。「ようこそ」「またね」など、子ども向けの案内に。",
            "handshake": "握手する二人のスーツ姿。提携・歓迎・お礼のお知らせに。",
        },
        "examples": [
            ("bowing-greetings-flat-1", "園のご案内の見本。保育士を元の大きさのまま置き、右にあいさつ文を並べました。",
             ["bowing-greetings-flat-hoikushi"], "横長(はがきを横にした比率)の大きさ"),
            ("bowing-greetings-flat-2", "新入社員のごあいさつの見本。新入社員を元の大きさのまま置きました。日付や課の名前は空欄(○)です。",
             ["bowing-greetings-flat-newbie"], "横長の大きさ"),
        ],
    },
    "winter-prep-year-end-flat": {
        "why": "11月から年末までの暮らしの場面12枚です。冬支度、餅つき、冬至、大掃除、年越し、鏡餅と、日付の順にそのままおたよりや案内の項目になります。",
        "frame": False,
        "picks": {
            "fuyujitaku": "ストーブ・ブランケット・セーター。冬支度、防寒のお知らせに。",
            "mochitsuki": "二人で餅をつく場面。餅つき会の案内に。",
            "toji": "ゆずを浮かべた木の風呂桶。冬至のゆず湯のお知らせに。",
            "kabocha": "冬至のかぼちゃの煮物。給食だよりや献立に。",
            "osouji": "バケツ・モップ・はたき。大掃除のお知らせや当番表に。",
            "toshikoshi": "えび天のせの年越しそば。年末の献立やお店のお知らせに。",
            "joya": "雪の夜の除夜の鐘。大みそか・初詣のご案内に。",
            "nenga": "白いはがきと筆。年賀状の準備・受付のお知らせに。",
            "kotatsu": "みかんをのせたこたつ。冬の暮らしの話題に。",
            "nabe": "具だくさんの鍋。冬の献立、鍋の会のお知らせに。",
            "scarf": "マフラーと手袋。持ち物欄や防寒のお願いに。",
            "kagamimochi": "鏡餅。お正月飾りや年末年始のお知らせに。",
        },
        "examples": [
            ("winter-prep-year-end-flat-1", "12月のおたよりの見本。大掃除・餅つき・冬至の3つを、元の大きさの約4割に縮めて並べました。日付は空欄(○)です。",
             ["winter-prep-year-end-flat-osouji", "winter-prep-year-end-flat-mochitsuki", "winter-prep-year-end-flat-toji"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("winter-prep-year-end-flat-2", "年末年始の休業のお知らせの見本。鏡餅を添えました。日付は空欄(○)です。",
             ["winter-prep-year-end-flat-kagamimochi"], "横長の大きさ"),
        ],
    },
    "eto-lineup-kawaii": {
        "why": "子から亥までの十二支の動物12匹を、そろいの赤い羽織で描いた素材です。毎年の年賀状は、その年の動物を使います。表の「次にその年になるのは」は、西暦を12で割った余りで数えた年です。",
        "frame": False,
        "picks": {
            "rat": "ねずみ(子)。次にその年になるのは2032年。",
            "ox": "うし(丑)。次にその年になるのは2033年。",
            "tiger": "とら(寅)。次にその年になるのは2034年。",
            "rabbit": "うさぎ(卯)。次にその年になるのは2035年。細長い形です。",
            "dragon": "たつ(辰)。次にその年になるのは2036年。",
            "snake": "へび(巳)。次にその年になるのは2037年。",
            "horse": "うま(午)。2026年がこの年。次は2038年。",
            "sheep": "ひつじ(未)。2027年がこの年で、年賀状はこの1枚。",
            "monkey": "さる(申)。次にその年になるのは2028年。",
            "rooster": "にわとり(酉)。次にその年になるのは2029年。",
            "dog": "いぬ(戌)。次にその年になるのは2030年。",
            "boar": "いのしし(亥)。次にその年になるのは2031年。",
        },
        "examples": [
            ("eto-lineup-kawaii-1", "2027年の年賀状の見本。ひつじを元の大きさのまま置きました。文面は例です。",
             ["eto-lineup-kawaii-sheep"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("eto-lineup-kawaii-2", "十二支の一覧表(掲示用)の見本。12匹を元の大きさの半分に縮めて並べました。",
             [f"eto-lineup-kawaii-{k}" for k in ("rat", "ox", "tiger", "rabbit", "dragon", "snake", "horse", "sheep", "monkey", "rooster", "dog", "boar")], "横長の大きさ"),
        ],
    },
}


def set_guide_html(s: dict) -> str:
    """The 使い分けのガイド section of a featured set, or '' for the other sets."""
    g = GUIDES.get(s["slug"])
    if not g:
        return ""
    slug = s["slug"]
    its = s["items"]
    by_key = {i["id"][len(slug) + 1:]: i for i in its}
    assert set(g["picks"]) == set(by_key), f"{slug}: a picture without a line or a line without a picture: {set(g['picks']) ^ set(by_key)}"
    head = ["素材", "使いどころ", "大きさ(px)", "300dpiで印刷すると"] + (["中の空き(px)"] if g["frame"] else [])
    rows = []
    for key, it in by_key.items():
        cells = [f'<a href="/illust/{it["id"]}/">{esc(it["title"])}</a>', esc(g["picks"][key]), f'{it["w"]}×{it["h"]}',
                 f'約{mm(it["w"], 300)}×{mm(it["h"], 300)}mm']
        if g["frame"]:
            x0, y0, x1, y1 = inner_box(Image.open(it["path"]))
            cells.append(f"{x1 - x0}×{y1 - y0}")
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    table = f'<div class="tablewrap"><table><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    ws, hs = [i["w"] for i in its], [i["h"] for i in its]
    size_note = (f"どの素材も幅{min(ws)}〜{max(ws)}px、高さ{min(hs)}〜{max(hs)}pxです。300dpiの印刷なら約{mm(min(ws), 300)}〜{mm(max(ws), 300)}mm×{mm(min(hs), 300)}〜{mm(max(hs), 300)}mmで、"
                 f"はがき(幅100mm)に載せるなら、150dpi(幅約591px)で作る画面にそのまま置けます。A4の幅(210mm)いっぱいまで広げると、{round(max(ws) / 210 * 25.4)}dpi前後になり、"
                 "線が粗く見えます。小さめに置くか、大きく使うときは試し刷りで確かめてください。")
    ex_html = []
    for name, caption, uses, size_label in g["examples"]:
        f = EXAMPLES_DIR / f"{name}.webp"
        w, h = Image.open(f).size
        used = "、".join(f'<a href="/illust/{u}/">{esc(next(i["title"] for i in its if i["id"] == u))}</a>' for u in uses[:3]) + ("ほか" if len(uses) > 3 else "")
        ex_html.append(f'<figure style="margin:0 0 28px"><img src="/assets/examples/{name}.webp" alt="{esc(caption)}" width="{w}" height="{h}" loading="lazy" '
                       f'style="max-width:100%;height:auto;border-radius:8px"><figcaption class="memo-note" style="margin-top:8px">{esc(caption)}文面は例です。'
                       f'({size_label}、{w}×{h}px)使った素材: {used}</figcaption></figure>')
    frame_note = ""
    if g["frame"]:
        frame_note = "<p>「中の空き」は、枠の真ん中で透明になっている、いちばん大きい四角の大きさです。文字や写真は、この中に収めると枠にかかりません。</p>"
    return f"""<section style="margin-top:44px"><h2><span class="scribble">このセットの使い分け</span></h2>
<p>{esc(g['why'])}</p>
{table}
{frame_note}<p>{esc(size_note)}</p></section>
<section style="margin-top:44px"><h2><span class="scribble">このセットだけで作った例</span></h2>
{"".join(ex_html)}
<p class="memo-note">見本の絵と文字は、このセットの素材と文字だけで作りました。素材は元の大きさのまま(拡大なし)で、日付は空欄です。素材は、このページ上のまとめて保存ボタンや各素材のページから、ずっと無料・商用OK・クレジット不要で保存できます。詳しい条件は<a href="/license/">利用について</a>へ。</p></section>"""
