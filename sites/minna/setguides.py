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


def blank_box(im: Image.Image, kind: str = "cream") -> tuple[int, int, int, int] | None:
    """The biggest plain rectangle of a picture that can be written on (a name tag, a podium, a white board), as (x0, y0, x1, y1), or None.
    kind 'cream': the cream of a tag (R>245, G>235, 195<B<245); 'white': a near-white board.  A part counts when it fills at least 80% of its bounding box and is wider than 1.3 times its height."""
    import numpy as np
    from scipy import ndimage
    a = np.array(im.convert("RGBA")).astype(int)
    if kind == "white":
        m = (a[:, :, 3] > 200) & (a[:, :, 0] > 245) & (a[:, :, 1] > 240) & (a[:, :, 2] > 225)
    else:
        m = (a[:, :, 3] > 200) & (a[:, :, 0] > 245) & (a[:, :, 1] > 235) & (a[:, :, 2] > 195) & (a[:, :, 2] < 245)
    lab, k = ndimage.label(m)
    best = None
    for i in range(1, k + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 2500:
            continue
        w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if len(ys) / (w * h) > 0.80 and w / h > 1.3 and (best is None or len(ys) > best[0]):
            best = (len(ys), int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return best[1:] if best else None


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
        "points": [
            "中の空きは、幅{iw_min}〜{iw_max}px、高さ{ih_min}〜{ih_max}pxです。文字の大きさを24pxにすると、最も狭い枠でも1行に約{chars24}字、{lines24}行まで入ります。見出しは短く(運動会、給食だよりのように4〜6字)、詳しい内容は枠の外に書くと、枠の絵が文字に隠れません。写真を入れるときは、枠の中の空きの縦横比(最も細長いお弁当のフレームで約{ratio_max})に合わせて切り抜きます。",
            "12枚は、運動会、賞状、お正月、お月見、ハロウィン、卒業、給食、お弁当、ポップ、クリスマス、読書の秋、年賀状(ひつじ)です。月ごとのおたよりの見出しに使うなら、9月はお月見、10月は運動会・ハロウィン・読書の秋、12月はクリスマス、1月はお正月と年賀状、3月は卒業、給食とお弁当は一年を通して使えます。",
        ],
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
        "points": [
            "全身の人物なので、高さが{hmin}〜{hmax}pxあり、300dpiで印刷すると高さ約{hmin_mm}〜{hmax_mm}mmです。名刺大の案内に置くなら顔が見える最小の大きさ、A4の案内に大きく置くなら高さ60mm(約{dpi60}dpi)までが、粗く見えない目安です。先生(幅353px)は、ドアが一緒に描かれているため、握手する人(幅401px)と並んで、ほかより横幅が広くなっています。",
            "場面ごとの選び方は、園や学校なら保育士と先生、医療や福祉なら看護師と医師、お店なら店員と案内係、会社なら新入社員と握手する人、どこでも使えるのは感謝・お詫び・手を振る人です。お詫びの素材は、肩をすぼめて頭を下げる姿で、予定変更や遅れのお知らせに向きます。人物は小さく置くほど表情が見えにくくなるので、お辞儀の向きが伝われば足りる案内には、大きさを欲張らず、周りに余白をとります。",
        ],
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
        "points": [
            "12点は、冬支度、餅つき、冬至のゆず湯とかぼちゃ、大掃除、年越しそば、除夜の鐘、年賀状の準備、こたつ、鍋、マフラーと手袋、鏡餅です。11月から元日までの順に、おたよりや案内の項目として1点ずつ置けます。食べ物の素材(かぼちゃ、年越しそば、鍋)が3点あるので、給食だよりや献立表の見出しにも向きます。",
            "おたよりの12月の欄をこのセットで作ると、餅つき、冬至、大掃除、大みそか(年越しそばと除夜の鐘)、お正月(鏡餅)の予定表になります。例の1枚目は、そのうち3つを並べた表です。こたつ、鍋、マフラーと手袋、冬支度は日付に縛られないので、1月や2月のおたよりにも使えます。日付つきの項目(餅つき、冬至、大みそか)は、おたよりの左から日付の順に、日付のない項目(こたつ、鍋)は余白に置くと、読みやすくなります。",
        ],
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
        "points": [
            "ひつじ(未)の年賀状は2027年で、次に未年が来るのは2039年です(12年ごと)。12点は全員が同じ赤い羽織を着ているので、十二支の一覧表にしても、1匹だけ浮きません。大きさは幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxで、うさぎだけが幅310pxと細く、高さは528pxで12点のなかで最も高い素材です。",
            "十二支の一覧表は、子・丑・寅・卯・辰・巳・午・未・申・酉・戌・亥の順に並べます。ひつじは8番目です。例の2枚目は、この順に4列×3段に並べた表で、読み方を添えています。毎年の年賀状では、その年の1匹だけを大きく使い、一覧表には12匹を同じ大きさで並べると、区別がつきます。",
        ],
        "examples": [
            ("eto-lineup-kawaii-1", "2027年の年賀状の見本。ひつじを元の大きさのまま置きました。文面は例です。",
             ["eto-lineup-kawaii-sheep"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("eto-lineup-kawaii-2", "十二支の一覧表(掲示用)の見本。12匹を元の大きさの半分に縮めて並べました。",
             [f"eto-lineup-kawaii-{k}" for k in ("rat", "ox", "tiger", "rabbit", "dragon", "snake", "horse", "sheep", "monkey", "rooster", "dog", "boar")], "横長の大きさ"),
        ],
    },
    "tropical-fruits-flat": {
        "why": "南国の果物12種を、丸ごとの姿と切った断面を1枚にそろえて描いたセットです。皮の色と中の色が違う果物が多いので、メニュー、商品の紹介、食育のカードで「外と中」を1枚で見せられます。",
        "frame": False,
        "picks": {
            "dragonfruit": "ピンクの皮と、白い果肉に黒い種の断面。ほかの果物が黄や緑に寄るなかで、色のアクセントになります。",
            "mango": "丸ごとと、格子状に切れ目を入れた切り方の2つ。デザートやドリンクのメニューに。",
            "papaya": "半分に切った断面。オレンジの果肉の真ん中に黒い種が並びます。",
            "lychee": "赤いつぶつぶの皮と、むいた白い実。皮をむく前後を並べたい資料に。",
            "passionfruit": "紫の皮の丸ごとと、黄色い果肉の断面。",
            "coconut": "丸ごと、割った断面、ストロー付き。ドリンクの案内に。",
            "mangosteen": "紫の皮と、白い房に分かれた断面。",
            "guava": "緑の丸ごとと、ピンクの果肉の断面。",
            "rambutan": "赤い毛の皮と、むいた白い実。毛が細かいので、小さく置くときは試し刷りで確かめます。",
            "starfruit": "星形の断面。星の形そのものが、見出しや飾りのアクセントになります。",
            "pineapple": "丸ごとと輪切り。縦長に近い形で、12点のなかで最も背が高い素材です。",
            "durian": "とげの皮と、黄色い房の断面。12点のなかで最も大きく描かれています。",
        },
        "points": [
            "全12点が「外側と断面」のセットになっています。果物の名前カードを作るときは、1枚の絵に名前の枠を足すだけで、外見と中の両方を見せるカードになります。食育の資料では、丸ごとと断面を別々に探して貼り合わせる手間が要りません。",
            "12点とも幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxで、ほぼ同じ大きさに描かれています。並べたときに大きさがそろうので、4枚や6枚の一覧表にそのまま入れられます。背景との相性は、各素材のページに色ごとの実測の数字があります。",
            "例の1枚目は4種類を2×2に並べたお品書きで、値段は空欄です。2枚目は、丸ごとと断面の違いが大きい3種類で作った、中を想像してもらうカードです。どちらも素材は元の大きさの半分以下に縮めて置いています。",
            "丸ごとと断面を1枚の中で左右に並べた素材が多く、絵はほぼ正方形から少し横長です。縦が横より1割以上長いのは、パイナップル(484×557px)だけで、縦の列に置くと余白が出ません。切った面の色(ピンク、黄、橙、白)は、果物ごとの名前札の色分けにも使えます。ドリアンとパイナップルは背が高いので、同じ行に置くときは、少し小さく縮めて行の高さをそろえます。",
        ],
        "examples": [
            ("tropical-fruits-flat-1", "南国フルーツのお品書きの見本。4種類を元の大きさの約5割に縮めて並べ、値段は空欄(○)にしました。",
             ["tropical-fruits-flat-dragonfruit", "tropical-fruits-flat-mango", "tropical-fruits-flat-pineapple", "tropical-fruits-flat-coconut"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("tropical-fruits-flat-2", "食育カードの見本。「中はどうなっているかな?」と問いかけ、丸ごとと断面が1枚になった3種類を並べました。",
             ["tropical-fruits-flat-dragonfruit", "tropical-fruits-flat-passionfruit", "tropical-fruits-flat-durian"], "横長の大きさ"),
        ],
    },
    "animals-undokai-kawaii": {
        "why": "運動会の競技をする動物10匹のセットです。全員が赤いはちまきや帽子をつけていて、かけっこ、綱引き、玉入れ、ハードル、大玉ころがし、パン食い競走、応援、表彰と、競技ごとに1匹ずつ使えます。",
        "frame": False,
        "blank": "cream",
        "picks": {
            "rabbit-run": "かけっこをするうさぎ。プログラムの「かけっこ」の行に。",
            "turtle-run": "ゴールテープを切るカメ。ゴールの場面、結果発表の見出しに。",
            "bear-tsunahiki": "綱引きをするクマ。縄が絵の左右の端まで伸びています。",
            "monkey-tamaire": "玉入れをするサル。かごと玉つき。",
            "cat-hurdle": "ハードルを跳ぶネコ。赤白のハードルつき。",
            "elephant-ball": "赤い大玉を転がすゾウ。大玉ころがしの行に。",
            "penguin-slide": "腹ばいですべるペンギン。10点のなかで唯一の横長(背が低い)素材です。",
            "fox-cheer": "赤い旗を振る応援団長のキツネ。開会のあいさつや応援の案内に。",
            "pig-bread": "パン食い競走のブタ。つるしたパンつき。",
            "lion-medal": "メダルをかけたライオンと、白紙の表彰台。表彰台の面に順位や名前を書き込めます。",
        },
        "points": [
            "運動会のお知らせは、競技の名前を並べる形になりがちです。このセットは、競技名ごとに対応する動物がいるので、プログラム表の行ごとに1匹ずつ置けます。10匹のうち、競技がはっきりしているのは、かけっこ・綱引き・玉入れ・ハードル・大玉ころがし・パン食い競走の6つです。残りは、ゴール、応援、表彰、すべる動物で、開会や閉会、結果の掲示に使います。",
            "表彰台は白紙になっています。表の「書き込める白い面」のとおり、ライオンの台は{blank_lion}pxの面があり、順位や名前を印刷した文字で重ねられます。手書きにするなら、台の面に直接書き込めるので、賞状より小さな賞のカードに向いています。",
            "10点とも幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxです。はがきの幅(100mm)に1匹を置くなら、150dpiの画面にそのまま置けます。A4のプログラムに6行並べるときは、1匹を幅30mm前後にすると、元の素材は最小のものでも約{dpi30}dpiあり、線がはっきり出ます。",
            "運動会のお知らせは、プログラムのほかに、入場門の飾り、応援席のポスター、当日の掲示にも使えます。応援団長のキツネは、旗が絵の右上に高く伸びているので、ポスターの左上の角に置くと、旗が紙面の内側に向かって広がり、文字と重なりません。ペンギンだけが横長(482×303px)で、ほかの9点は縦横が近い素材です。",
        ],
        "examples": [
            ("animals-undokai-kawaii-1", "運動会のプログラムの見本。6つの競技に、対応する動物を元の大きさの約3割に縮めて並べました。時刻は空欄(○)です。",
             ["animals-undokai-kawaii-rabbit-run", "animals-undokai-kawaii-bear-tsunahiki", "animals-undokai-kawaii-monkey-tamaire", "animals-undokai-kawaii-cat-hurdle", "animals-undokai-kawaii-elephant-ball", "animals-undokai-kawaii-pig-bread"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("animals-undokai-kawaii-2", "表彰カードの見本。ライオンの白紙の表彰台に、順位を重ねました。名前は空欄(○)です。",
             ["animals-undokai-kawaii-lion-medal"], "横長の大きさ"),
        ],
    },
    "newyear-eve-cool-sumi": {
        "why": "大みそかの夜から元日の朝までの題材を、時間の順に12点そろえたセットです。墨の黒と朱の赤を基調にした、締まったタッチで、年末年始のポスターやカード、SNSの画像に向きます。",
        "frame": False,
        "picks": {
            "joya-bell": "除夜の鐘と撞木。赤い丸の前に置かれた鐘で、大みそかの夜の案内に。",
            "toshikoshi-soba": "湯気の立つ年越しそばと箸。年越しの食事、お店の年末営業の案内に。",
            "hatsuhinode": "波と山の上に昇る初日の出。円形に近い構図で、元日のあいさつに。",
            "kadomatsu": "門松が2対。左右対称で、玄関の案内に。",
            "kagamimochi": "みかんをのせた鏡餅。お正月飾りの案内に。",
            "daruma": "目が白く抜けたままのだるま。願かけや目標の話題に。",
            "crane": "羽を広げて飛ぶ鶴。年賀状の主役に。",
            "hamaya": "鈴と房のついた破魔矢。初詣の案内に。細長い斜めの素材です。",
            "torii": "松に囲まれた赤い鳥居。初詣の案内に。",
            "fuji": "赤い日の前の富士山。12点のなかで最も背が低い横長の素材です。",
            "osechi": "金の蒔絵風の三段重のおせち。おせちの予約やお店の案内に。",
            "clock-midnight": "針が0時を指す時計。赤い飛沫つき。カウントダウンの案内に。",
        },
        "points": [
            "時間の順に使うと、1枚のポスターで大みそかの流れを案内できます。夜は除夜の鐘と年越しそば、0時の時計、朝は初日の出、鏡餅、おせち、昼は鳥居と破魔矢です。お店や自治会、学校の年末年始のお知らせで、日程の行ごとに1点ずつ置けます。",
            "12点とも、墨の黒い輪郭と、朱の赤い面でそろえてあります。背景は白や、生成り色の紙に合います。暗い背景だと黒い輪郭が沈むので、背景との相性は各素材のページの実測の数字で確かめてください。大きさは幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxです。",
            "同じタッチの「お正月(墨と朱のかっこいいタッチ)」とは、題材が少し重なります(だるま、門松、初日の出と波)。年越しの前後に使うならこのセット、独楽・羽子板・獅子舞・梅・竹といったお正月の遊びと縁起物なら、そちらを使うと、同じ絵が並びません。",
            "赤い丸(日の丸のような円)が背景に描かれている素材は、除夜の鐘、初日の出、富士山の3点です。この3点を並べるときは、赤い円の位置(鐘は右上、初日の出は上、富士山は左上)をそろえると、ポスターに統一感が出ます。年越しの時計は、赤い飛沫がついているので、白い紙の上で目立ちます。",
        ],
        "links": [("お正月(墨と朱のかっこいいタッチ)", "/series/oshogatsu-sumi-cool/")],
        "examples": [
            ("newyear-eve-cool-sumi-1", "大みそかの予定を知らせるポスターの見本。鐘・そば・時計の3点を元の大きさの約4割に縮めて並べました。時刻は空欄(○)です。",
             ["newyear-eve-cool-sumi-joya-bell", "newyear-eve-cool-sumi-toshikoshi-soba", "newyear-eve-cool-sumi-clock-midnight"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("newyear-eve-cool-sumi-2", "年賀状の見本。「初日の出」を元の大きさのまま置きました。",
             ["newyear-eve-cool-sumi-hatsuhinode"], "はがき(100×148mm)を150dpiで作った大きさ"),
        ],
    },
    "office-worker-middleaged-flat": {
        "why": "中高年の会社員男性の一日を、通勤から帰宅まで12場面にしたセットです。同じ人物が、会議、電話、出張、残業、昼食などの場面にいるので、社内文書や研修資料、ビジネス記事の挿絵として、同じ人を続けて使えます。",
        "frame": False,
        "picks": {
            "commute": "満員電車のつり革につかまる姿。周りの乗客も描かれています。",
            "meeting": "眼鏡をかけて、資料を読む会議の場面。",
            "presentation": "白紙のスクリーンを指して説明するプレゼン。スクリーンの前の面は何も描かれていません。",
            "bow": "取引先へのお辞儀。縦長で、幅が12点のなかで最も狭い素材です(足元にかばん)。",
            "phone": "電話を受けながらメモをとる場面。",
            "pc-work": "ノートパソコンで作業する場面。机にコーヒーつき。",
            "overtime": "夜の窓と机のスタンドの下で、頬杖をつく残業の場面。書類の山つき。",
            "business-trip": "キャリーケースを引いて駅のホームを歩く出張の場面。",
            "lunch": "弁当を食べる昼食の場面。",
            "break": "缶を持って柵にもたれる休憩の場面。",
            "thinking": "手を顎にあてて考えこむ場面。ノートが机にあります。",
            "back-home": "上着を腕にかけ、街灯の下を歩いて帰る場面。縦長で、12点のなかで最も背が高い素材です。",
        },
        "points": [
            "同じ人物が一日の流れに沿って12場面あるので、「ある会社員の一日」「一日のスケジュール」といった図解を、絵を探し直さずに作れます。朝は通勤、午前は会議・電話・パソコン作業、昼は昼食、午後はプレゼンと出張、夜は残業と帰宅、というように、行ごとに1点ずつ置けます。",
            "残業と満員電車の場面は、疲れた様子や窮屈な様子が描かれています。働き方や労務の資料で使うと、会社が残業を肯定しているように読まれることがあります。使うときは、見出しや文章で、何を伝える場面なのかを添えてください。",
            "12点とも幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxです。横長が{wide}点、縦長が{tall}点なので、横並びの資料では高さをそろえて置くと、人物の大きさが揃って見えます。",
            "12点の人物は、どの場面でも、ネイビーのスーツと青緑のネクタイです。眼鏡をかけているのは、会議とパソコン作業の2点だけです。同じ人物だと分かる服装なので、横に並べた図解でも、別の人に見えません。通勤の場面だけは、周りの乗客も描かれているため、人物が小さく見えます。",
        ],
        "examples": [
            ("office-worker-middleaged-flat-1", "会議のお知らせの見本。会議の場面を元の大きさのまま置き、日時と場所は空欄(○)にしました。",
             ["office-worker-middleaged-flat-meeting"], "横長の大きさ"),
            ("office-worker-middleaged-flat-2", "「ある会社員の一日」の図解の見本。4つの場面を、元の大きさの約5割に縮めて時間の順に並べました。時刻は空欄(○)です。",
             ["office-worker-middleaged-flat-commute", "office-worker-middleaged-flat-pc-work", "office-worker-middleaged-flat-lunch", "office-worker-middleaged-flat-back-home"], "横長の大きさ"),
        ],
    },
    "animal-nametags-kawaii": {
        "why": "動物が空白の名札を持った12点のセットです。名札の面は何も書かれていないので、名前や学年を、印刷した文字でも手書きでも書き足せます。ロッカー、下駄箱、席札、持ち物の名前の表示に使えます。",
        "frame": False,
        "blank": "cream",
        "picks": {
            "cat": "名札を両手で持つ猫。名札は絵の真ん中より少し下にあります。",
            "dog": "名札を首から下げた犬。12点のなかで、名札の面が最も小さい素材です。",
            "rabbit": "名札を頭の上にかかげるうさぎ。名札は絵の上のほうにあります(ほかの11点は真ん中より下)。",
            "bear": "名札を両手で持つ熊。12点のなかで、名札の面が最も大きい素材です。",
            "penguin": "名札を持つペンギン。名札が体の真ん中にあります。",
            "fox": "名札を持つ狐。大きなしっぽがつきます。",
            "panda": "笹の葉を持つパンダ。名札はおなかの前、絵の下のほうにあります。",
            "chick": "名札の上から顔を出すひよこ。名札は絵の下のほうにあります。",
            "elephant": "鼻のすぐ下に名札を持つ象。名札は絵の下のほうにあります。",
            "sheep": "もこもこの毛の前に名札を持つ羊。",
            "frog": "蓮の葉の上で名札を持つカエル。",
            "lion": "名札を前に抱えるライオン。たてがみが大きく、名札は絵の下のほうにあります。",
        },
        "points": [
            "名札の高さは、上から数えて、うさぎだけが絵の約3割のところ(頭の上)で、ほかの11点は約6〜7割のところにあります。クラスの名簿のように名前を横に並べるときは、うさぎ以外から選ぶと、名前の高さがそろいます。",
            "名札の面は、表の「書き込める白い面」の大きさで、最も小さい犬が185×84px、最も大きい熊が309×122pxです。名前を入れるなら、面の幅の約8割までに収めると、文字が名札の縁にかかりません(例の画像は、その幅で入れています)。長い名前は、字を小さくするより、2行に分けたほうが読みやすくなります。",
            "12点とも幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxです。幅4〜5cm前後のシールやロッカーの表示にするなら、300dpiで十分な解像度があります(幅{wmax}pxは300dpiで約{wmax_mm}mmです)。",
            "動物は、猫、犬、うさぎ、熊、ペンギン、狐、パンダ、ひよこ、象、羊、カエル、ライオンの12種類です。組ごとに動物を決めて、ひらがなの名前を入れる使い方ができます。ひよことゾウは、名札が絵の下のほうにあるので、名札の面の高さが少し違います。名札を切り取ってシールにするときは、名札の周りに少し余白を残して切ります。",
        ],
        "examples": [
            ("animal-nametags-kawaii-1", "ロッカー表示の見本。6匹の名札に、名前を重ねました。元の大きさの約5割に縮めて並べています。名前は例です。",
             ["animal-nametags-kawaii-cat", "animal-nametags-kawaii-dog", "animal-nametags-kawaii-bear", "animal-nametags-kawaii-fox", "animal-nametags-kawaii-panda", "animal-nametags-kawaii-lion"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("animal-nametags-kawaii-2", "席札の見本。2匹の名札に、名前を重ねました。名前は例です。",
             ["animal-nametags-kawaii-penguin", "animal-nametags-kawaii-sheep"], "横長の大きさ"),
        ],
    },
    "oshogatsu-sumi-cool": {
        "why": "だるま・獅子舞・独楽・羽子板・門松・竹・梅・波と初日の出という、お正月の縁起物と遊びを、墨の黒と朱の赤でそろえた8点のセットです。年賀状、ポスター、SNSの画像に向きます。",
        "frame": False,
        "picks": {
            "daruma": "目が描き込まれただるま。赤い体に金の縦じま。目の大きさが分かる絵です。",
            "bamboo": "2本の竹と葉。門松の竹と組んで、松竹梅の「竹」に。",
            "plum": "赤い梅の枝。松竹梅の「梅」に。",
            "koma": "回る独楽と、軌跡の線。",
            "hagoita": "羽子板と羽根。柄の梅の模様が見えます。",
            "shishimai": "獅子舞の顔。8点のなかで最も迫力のある絵で、年賀状の主役に。",
            "sunrise-wave": "波と、朱色の初日の出。",
            "kadomatsu": "松・竹・梅の飾りがつく門松。8点のなかで最も縦長の素材です。",
        },
        "points": [
            "松竹梅を、門松の松、竹、梅の3点で組めます。縁起のよい3つ組を、絵を足さずに年賀状の飾りにできます。このセットは8点なので、12点のセットより素材は少ないのですが、題材は1点ずつ違います。",
            "同じタッチの「大みそかとお正月(墨と朱)」とは、題材が少し重なります(だるま、門松、初日の出と波)。こちらは独楽・羽子板・獅子舞・梅・竹といった、お正月の遊びと縁起物が中心です。年越しの鐘やおせちは、あちらにあります。",
            "8点とも幅{wmin}〜{wmax}px、高さ{hmin}〜{hmax}pxです。年賀状のはがき(100×148mm)に1点を大きく置くなら、150dpiの画面にそのまま置けます。背景は白や生成り色が合い、暗い背景だと黒い輪郭が沈みます。",
            "8点のうち、赤い面が大きいのは、だるま、獅子舞、波と初日の出の3点です。この3点を同じ紙面に置くと色が重くなるので、白い余白を広めにとります。緑が主役の竹と、赤い花の梅は、赤の面が小さいので、重い絵の横に置くと、紙面の色のバランスがとれます。年賀状に使うときは、獅子舞か達磨のどちらか1点を主役にして、梅や竹を脇に添えると、絵が散らかりません。",
        ],
        "links": [("大みそかとお正月(墨と朱)", "/series/newyear-eve-cool-sumi/")],
        "examples": [
            ("oshogatsu-sumi-cool-1", "年賀状の見本。獅子舞を元の大きさのまま置きました。",
             ["oshogatsu-sumi-cool-shishimai"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("oshogatsu-sumi-cool-2", "お正月の催しのポスターの見本。羽子板・独楽・だるまを、元の大きさの約5割に縮めて並べました。日付は空欄(○)です。",
             ["oshogatsu-sumi-cool-hagoita", "oshogatsu-sumi-cool-koma", "oshogatsu-sumi-cool-daruma"], "横長の大きさ"),
        ],
    },
    "realistic-zoo-field-guide": {
        "why": "動物園で人気の12種を、図鑑のように細かく描いたリアルなタッチのセットです。かわいいタッチの動物イラストとは別に、教材、調べ学習の資料、展示パネル、動物園の案内に向きます。",
        "frame": False,
        "picks": {
            "panda": "笹を食べるジャイアントパンダ。笹の葉つき。",
            "koala": "ユーカリの枝にしがみつくコアラ。縦長です。",
            "capybara": "草の上に立つカピバラ。横向きの全身。",
            "redpanda": "枝に乗るレッサーパンダ。長いしっぽが目立ちます。",
            "lion": "たてがみのあるオスのライオン。横向きの全身。",
            "giraffe": "全身が縦に長いキリン。12点のなかで最も背が高い素材です。",
            "elephant": "横向きに歩くアフリカゾウ。12点のなかで最も幅が広い素材です。",
            "zebra": "しま模様がはっきり見えるシマウマ。",
            "flamingo": "片足で立つフラミンゴ。縦長です。",
            "polarbear": "横向きに歩くホッキョクグマ。横長です。",
            "penguin": "首の下にオレンジ色が見えるペンギン。縦長です。",
            "meerkat": "立ち上がったミーアキャット。",
        },
        "points": [
            "このセットは、かわいいタッチの動物ではなく、毛並みや模様を細かく描いた図鑑風の絵です。名前の欄と、調べたことを書く欄を足すだけで、動物カードになります。クラスで1人1種類を調べて、カードを並べて貼る調べ学習にも向きます。",
            "12点のうち、横長が{wide}点、縦長が{tall}点です。展示パネルに並べるときは、高さをそろえるより、全部を同じ面積に収めるつもりで置くと、キリンとホッキョクグマの大きさの差が目立ちません。",
            "毛並みの細かい描き込みは、大きく広げると粗く見えます。12点のなかで最も大きい素材でも、幅は{wmax}pxです。A4の幅(210mm)いっぱいに広げると、約{dpi_a4}dpiまで下がります。展示パネルなど大きく使うときは、必ず試し刷りをしてください。",
            "図鑑のページにするときは、向きで分けると並べやすくなります。横向きに立つか歩くのは、カピバラ、ライオン、ゾウ、シマウマ、ホッキョクグマの5点、正面を向くのは、パンダとミーアキャットの2点です。ほかの5点は、木や枝に乗っている姿(コアラ、レッサーパンダ)、片足立ち(フラミンゴ)、全身が縦に長い姿(キリン)、ペンギンです。",
        ],
        "examples": [
            ("realistic-zoo-field-guide-1", "どうぶつカードの見本。パンダを元の大きさのまま置き、名前の欄と、調べたことを書く欄を空欄にしました。",
             ["realistic-zoo-field-guide-panda"], "はがき(100×148mm)を150dpiで作った大きさ"),
            ("realistic-zoo-field-guide-2", "シルエットクイズの見本。キリン・シマウマ・アフリカゾウの輪郭を黒くして、答えを下に並べました。",
             ["realistic-zoo-field-guide-giraffe", "realistic-zoo-field-guide-zebra", "realistic-zoo-field-guide-elephant"], "横長の大きさ"),
        ],
    },
}


def guide_stats(its: list[dict], g: dict) -> dict:
    """The numbers a guide's paragraphs may use ({n}, {wmin}, {iw_min}, ...), measured from the set's pictures."""
    ws, hs = [i["w"] for i in its], [i["h"] for i in its]
    stats = {"n": len(its), "wmin": min(ws), "wmax": max(ws), "hmin": min(hs), "hmax": max(hs), "wide": sum(1 for i in its if i["w"] > i["h"] * 1.15), "tall": sum(1 for i in its if i["h"] > i["w"] * 1.15),
             "dpi30": round(min(ws) / (30 / 25.4)), "dpi_a4": round(max(ws) / (210 / 25.4)), "wmax_mm": mm(max(ws), 300)}
    stats.update({"hmin_mm": mm(min(hs), 300), "hmax_mm": mm(max(hs), 300), "dpi60": round(min(hs) / (60 / 25.4))})
    if g["frame"]:
        boxes = [inner_box(Image.open(i["path"])) for i in its]
        iws, ihs = [b[2] - b[0] for b in boxes], [b[3] - b[1] for b in boxes]
        stats.update({"iw_min": min(iws), "iw_max": max(iws), "ih_min": min(ihs), "ih_max": max(ihs), "chars24": min(iws) // 24, "lines24": int(min(ihs) // (24 * 1.5)),
                      "ratio_max": f"{max(w / h for w, h in zip(iws, ihs)):.1f}:1"})
    lion = next((i for i in its if i["id"].endswith("-lion-medal")), None)
    if lion is not None:
        bb = blank_box(Image.open(lion["path"]), "cream")
        stats["blank_lion"] = f"{bb[2] - bb[0] + 1}×{bb[3] - bb[1] + 1}" if bb else "なし"
    return stats


def set_guide_html(s: dict) -> str:
    """The 使い分けのガイド section of a featured set, or '' for the other sets."""
    g = GUIDES.get(s["slug"])
    if not g:
        return ""
    slug = s["slug"]
    its = s["items"]
    by_key = {i["id"][len(slug) + 1:]: i for i in its}
    assert set(g["picks"]) == set(by_key), f"{slug}: a picture without a line or a line without a picture: {set(g['picks']) ^ set(by_key)}"
    head = ["素材", "使いどころ", "大きさ(px)", "300dpiで印刷すると"] + (["中の空き(px)"] if g["frame"] else []) + (["書き込める白い面(px)"] if g.get("blank") else [])
    rows = []
    for key, it in by_key.items():
        cells = [f'<a href="/illust/{it["id"]}/">{esc(it["title"])}</a>', esc(g["picks"][key]), f'{it["w"]}×{it["h"]}',
                 f'約{mm(it["w"], 300)}×{mm(it["h"], 300)}mm']
        if g["frame"]:
            x0, y0, x1, y1 = inner_box(Image.open(it["path"]))
            cells.append(f"{x1 - x0}×{y1 - y0}")
        if g.get("blank"):
            b = blank_box(Image.open(it["path"]), g["blank"])
            cells.append(f"{b[2] - b[0] + 1}×{b[3] - b[1] + 1}" if b else "なし")
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
    blank_note = ""
    if g.get("blank"):
        blank_note = "<p>「書き込める白い面」は、名前や文字を書き足せる、四角い白(クリーム色)の部分のいちばん大きいものの大きさです。</p>"
    stats = guide_stats(its, g)
    points = "".join(f"<p>{esc(p.format(**stats))}</p>" for p in g.get("points", []))
    points_html = f'<section style="margin-top:44px"><h2><span class="scribble">使い方のコツ</span></h2>{points}' + (
        '<ul class="check">' + "".join(f'<li><a href="{esc(h)}">{esc(l)}</a></li>' for l, h in g["links"]) + "</ul>" if g.get("links") else "") + "</section>" if points else ""
    return f"""<section style="margin-top:44px"><h2><span class="scribble">このセットの使い分け</span></h2>
<p>{esc(g['why'])}</p>
{table}
{frame_note}{blank_note}<p>{esc(size_note)}</p></section>
{points_html}
<section style="margin-top:44px"><h2><span class="scribble">このセットだけで作った例</span></h2>
{"".join(ex_html)}
<p class="memo-note">見本の絵と文字は、このセットの素材と文字だけで作りました。素材は元の大きさのまま(拡大なし)で、日付は空欄です。素材は、このページ上のまとめて保存ボタンや各素材のページから、ずっと無料・商用OK・クレジット不要で保存できます。詳しい条件は<a href="/license/">利用について</a>へ。</p></section>"""
