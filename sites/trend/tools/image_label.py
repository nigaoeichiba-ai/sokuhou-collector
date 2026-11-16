# -*- coding: utf-8 -*-
"""写真風の画像に、読める大きさの「イメージです。」(黒地・白の太字)を足す道具。すでにこの道具のラベルがある画像には、重ねて足さない(has_label。2026-11-16 に二重になった不具合の対策)。
元の画像に小さなラベルが焼き込まれている場合は、足さずに元の画像をそのまま使う(足すなら、元のラベルをこのラベルで覆う位置に置く)。"""
from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/YuGothB.ttc"
if not __import__("os").path.exists(FONT):
    FONT = "C:/Windows/Fonts/meiryob.ttc"


LABEL_FILL = (15, 15, 15)


def _geometry(w, h, side="right", scale=1.0, x_left=None, bottom_frac=0.955):
    box_w = round(w * 0.178 * scale)
    fsz = round(box_w * 0.17)
    pad_x, pad_y = round(fsz * 0.55), round(fsz * 0.32)
    font = ImageFont.truetype(FONT, fsz, index=0)
    tw = ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength("イメージです。", font=font)
    bw, bh = round(tw + 2 * pad_x), round(fsz * 1.25 + 2 * pad_y)
    bottom = round(h * bottom_frac)
    right = round(w * 0.97)
    if side == "left":
        right = (round(w * x_left) if x_left is not None else round(w * 0.095)) + bw
    return font, fsz, pad_x, pad_y, bw, bh, right, bottom


def has_label(im: Image.Image) -> bool:
    """True when this tool's own label (a near-black box of the label's size) is already at the bottom right or the bottom left (so it is never added twice)."""
    im = im.convert("RGB")
    w, h = im.size
    for side, sc, xl, bf in (("right", 1.0, None, 0.955), ("right", 0.8, None, 0.955), ("left", 1.0, None, 0.955), ("left", 0.8, None, 0.955), ("left", 1.0, 0.008, 0.995)):
        _, _, _, _, bw, bh, right, bottom = _geometry(w, h, side, sc, xl, bf)
        box = im.crop((right - bw + 2, bottom - bh + 2, right - 2, bottom - 2))
        px = list(box.getdata())
        near = sum(1 for p in px if all(abs(c - f) <= 6 for c, f in zip(p, LABEL_FILL)))
        if px and near / len(px) > 0.6:
            return True
    return False


def add_label(im: Image.Image, side: str = "right", scale: float = 1.0, x_left=None, bottom_frac=0.955) -> Image.Image:
    im = im.convert("RGB")
    if has_label(im):
        return im            # already labelled: never stack a second one
    w, h = im.size
    font, fsz, pad_x, pad_y, bw, bh, right, bottom = _geometry(w, h, side, scale, x_left, bottom_frac)
    d = ImageDraw.Draw(im)
    text = "イメージです。"
    x0, y0 = right - bw, bottom - bh
    d.rectangle([x0, y0, right, bottom], fill=LABEL_FILL)
    d.text((x0 + pad_x, y0 + pad_y - fsz * 0.05), text, font=font, fill=(255, 255, 255))
    return im
