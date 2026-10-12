"""みんなのイラスト: hub pages by purpose (/use/ and /use/<slug>/).

A visitor often knows what the picture is for (a flyer, a nursery newsletter, a slide) before knowing what it should show.  Each hub gathers the sets of the library that fit that use,
the specials, reading and tools next to it, and a few plain points about using the pictures that way.  The sets are found by words (title, lead, subject and the tags of the pictures),
so a new series joins the right hub without anyone editing a list.  Words are the page's own: nothing here names a product, a person or a brand.
"""
from __future__ import annotations

HUBS = [
    {"slug": "flyer", "name": "チラシ・ポスター・店頭POP", "short": "店頭のポップ、チラシ、イベントの案内",
     "words": ["チラシ", "ポスター", "お店", "ポップ", "販促", "セール", "イベント", "案内", "カフェ", "飲食", "季節", "行事"],
     "intro": ["店頭のポップやチラシ、イベントの案内に使えるイラストです。個人でも会社でも無料で商用利用でき、クレジット表示は不要です。",
               "背景が透明なPNGなので、色のついた背景や写真の上にもそのまま重ねられます。"],
     "points": [("背景を選ばない", "背景は透明です。配色が決まっている紙面にも、そのまま置けます。"),
                ("季節の素材は特集から", "行事ごとのイラストは特集ページにまとめています。時期が近いものから探せます。"),
                ("絵柄をそろえる", "同じセットのイラストは、同じ絵柄でそろっています。1枚の紙面では、同じセットから選ぶと統一感が出ます。")],
     "specials": ["christmas", "halloween", "winter", "frames-lines"], "guides": [], "tools": ["/tool/calendar/", "/tool/nametag/"]},
    {"slug": "nenga", "name": "年賀状・挨拶状", "short": "干支、お正月、季節のあいさつ",
     "words": ["年賀", "干支", "お正月", "正月", "ひつじ", "羊", "鏡餅", "初詣", "寒中", "あいさつ"],
     "intro": ["年賀状や寒中見舞い、季節のあいさつ状に使えるイラストです。干支のイラストは、毎年の年賀状に向けて追加しています。",
               "個人でも会社でも無料で商用利用でき、クレジット表示は不要です。"],
     "points": [("宛名面とは別に使う", "イラストは背景が透明です。年賀状ソフトや文書作成ソフトの図として貼り付けて使えます。"),
                ("名前入りのカード", "名前とひとことを入れたカードを作って、画像で保存できます。"),
                ("特集にまとめています", "干支と新年のイラストは、年賀状の特集から探せます。")],
     "specials": ["nenga-2027", "hitsuji"], "guides": [], "tools": ["/tool/card/"]},
    {"slug": "otayori", "name": "園・学校のおたより", "short": "保育園、幼稚園、学校の行事とおたより",
     "words": ["おたより", "保育園", "幼稚園", "学校", "給食", "運動会", "行事", "先生", "子ども", "園"],
     "intro": ["保育園・幼稚園・学校のおたよりや掲示物に使えるイラストです。毎月の行事、給食、運動会、季節のあいさつの場面をそろえています。",
               "個人でも園や学校でも無料で使え、クレジット表示は不要です。"],
     "points": [("毎月のおたよりに", "季節の行事ごとのセットがあります。月の初めに、その月のセットから選べます。"),
                ("掲示物にも", "名札や時間割は、A4のPDFで印刷できます。名前入りの名札は、名前を入れて作れます。"),
                ("人物の扱い", "人物は架空のイラストです。実在の人物をもとにしたものではありません。")],
     "specials": ["otayori", "shichigosan", "setsubun-hinamatsuri"], "guides": [], "tools": ["/tool/nametag/", "/printables/"]},
    {"slug": "business", "name": "社内資料・プレゼン・営業資料", "short": "仕事の場面、オフィス、会議、テレワーク",
     "words": ["仕事", "ビジネス", "オフィス", "会議", "テレワーク", "資料", "営業", "職場", "職業", "働"],
     "intro": ["社内資料、プレゼンテーション、営業資料、採用ページに使える、仕事の場面のイラストです。オフィスワーク、会議、テレワーク、さまざまな職業の人物をそろえています。",
               "個人でも会社でも無料で商用利用でき、クレジット表示は不要です。"],
     "points": [("資料の雰囲気に合わせる", "線画、フラット、水彩など、絵柄ごとにセットが分かれています。資料の雰囲気に近い絵柄を選んでください。"),
                ("背景色を試す", "各イラストのページで、背景色を切り替えて見え方を確かめられます。"),
                ("使い方は利用についてで確認", "商用利用の範囲や、加工・再配布の条件は、利用についてのページにまとめています。")],
     "specials": ["business"], "guides": [], "tools": []},
    {"slug": "web", "name": "SNS・ブログ・ウェブ", "short": "アイコン、見出し、フレーム、区切り線",
     "words": ["SNS", "ブログ", "アイコン", "吹き出し", "見出し", "フレーム", "飾り罫", "ライン", "背景", "ピクト"],
     "intro": ["SNSの投稿画像、ブログの見出し、ウェブサイトの飾りに使えるイラストです。アイコン、フレーム、区切り線、吹き出し、ピクトグラム風のイラストを集めています。",
               "個人でも会社でも無料で商用利用でき、クレジット表示は不要です。"],
     "points": [("透明PNG", "背景が透明なので、サイトの背景色に合わせて重ねられます。"),
                ("フレームと区切り線", "飾りのフレームや罫線は、特集ページにまとめています。"),
                ("画像の形式", "各イラストのページで、背景色や大きさを指定して、PNGやJPGで保存できます。")],
     "specials": ["frames-lines"], "guides": [], "tools": []},
    {"slug": "care", "name": "医療・介護・福祉", "short": "シニア、健康づくり、防災の案内",
     "words": ["介護", "医療", "福祉", "シニア", "健康", "看護", "病院", "体操", "防災", "高齢"],
     "intro": ["医療・介護・福祉の案内やお知らせ、健康づくりの掲示に使えるイラストです。シニアの運動、健康管理、防災の場面などをそろえています。",
               "個人でも法人でも無料で商用利用でき、クレジット表示は不要です。"],
     "points": [("やわらかい絵柄", "水彩や線画など、落ち着いた絵柄のセットがあります。"),
                ("防災の案内", "防災のイラストは、案内や掲示の補助として使えます。避難に関する情報は、必ず自治体などの公式の情報を確認してください。"),
                ("人物の扱い", "人物は架空のイラストです。実在の人物をもとにしたものではありません。")],
     "specials": ["senior", "bousai"], "guides": [], "tools": []},
    {"slug": "learning", "name": "教材・学習プリント", "short": "ぬりえ、時間割、教室の掲示",
     "words": ["学習", "勉強", "教材", "ぬりえ", "学校", "時間割", "先生", "算数", "教室", "生き物"],
     "intro": ["教材や学習プリント、教室の掲示に使えるイラストです。線画のぬりえ、時間割、動物や植物、学校の場面をそろえています。",
               "個人でも学校や塾でも無料で使え、クレジット表示は不要です。"],
     "points": [("印刷して塗る", "線画は、A4のぬりえとして印刷できます。ブラウザ上で色を塗ることもできます。"),
                ("生き物の図鑑風", "リアルな絵柄のセットは、生き物の名前を覚える教材の挿絵に向いています。"),
                ("時間割の用紙", "時間割はA4のPDFで、イラスト入りのものを印刷できます。")],
     "specials": ["nurie"], "guides": [], "tools": ["/tool/nurie/", "/printables/"]},
    {"slug": "craft", "name": "手づくり・名前入りの印刷物", "short": "カレンダー、名札、賞状、カード",
     "words": ["カード", "名札", "賞状", "カレンダー", "招待", "お祝い", "誕生日", "ありがとう"],
     "intro": ["カレンダー、名札、席札、賞状、メッセージカードなど、名前や日付を入れて印刷するものを、サイトの中で作れます。入力した内容はこの端末の中だけで使われ、送信されません。",
               "作ったものは画像で保存でき、そのまま印刷もできます。"],
     "points": [("入力は端末の中だけ", "名前も文面も、ブラウザの中だけで処理します。"),
                ("A4で印刷", "カレンダー、名札、賞状はA4で印刷できる大きさで作れます。"),
                ("イラストは自由に選べる", "サイトのイラストから、好きなものを選んで入れられます。")],
     "specials": [], "guides": [], "tools": ["/tool/calendar/", "/tool/nametag/", "/tool/card/", "/printables/"]},
]


def rank_series(words: list[str], series: list[dict], limit: int = 12) -> list[dict]:
    """The sets that name these words most: a word in the title, subject or lead counts three, a word among the picture tags once."""
    scored = []
    for s in series:
        if not s.get("items"):
            continue
        head = (s.get("title", "") + " " + s.get("subject", "") + " " + s.get("lead", "")).lower()
        tags = " ".join(t for it in s["items"] for t in it.get("tags", [])).lower()
        score = 0
        for w in words:
            w = w.lower()
            if w in head:
                score += 3
            if w in tags:
                score += 1
        if score:
            scored.append((score, 0 if s.get("legacy") else 1, s["slug"], s))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [x[3] for x in scored[:limit]]
