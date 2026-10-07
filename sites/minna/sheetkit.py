"""Turn a generated sheet (several illustrations on one flat key-colour background) into separate transparent WebP files.

    python -m sites.minna.sheetkit SHEET.png --cols 3 --rows 2 --out DIR [--prefix sheep] [--max-side 1024]

The generator is asked for a flat background (default magenta #FF00FF) and a grid of equal cells.  This module
  1. estimates the key colour from the sheet's border,
  2. turns every pixel close to it into transparency (soft edge, key colour removed from the edge pixels),
  3. finds the illustrations (connected parts merged, tiny specks dropped), orders them row by row, and
  4. trims, pads and scales each one and saves it as lossless-quality WebP.
It also reports problems (wrong count, an illustration touching the sheet edge or another one, key colour left inside).
Nothing here needs more than Pillow, numpy and scipy.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


@dataclass
class Piece:
    index: int
    image: Image.Image
    bbox: tuple[int, int, int, int]
    problems: list[str] = field(default_factory=list)


def estimate_key(rgb: np.ndarray, border: int = 6) -> np.ndarray:
    """Median colour of the sheet's outer frame."""
    h, w, _ = rgb.shape
    frame = np.concatenate([rgb[:border].reshape(-1, 3), rgb[-border:].reshape(-1, 3),
                            rgb[:, :border].reshape(-1, 3), rgb[:, -border:].reshape(-1, 3)])
    return np.median(frame, axis=0)


def key_to_alpha(rgb: np.ndarray, key: np.ndarray, lo: float = 28.0, hi: float = 96.0) -> np.ndarray:
    """RGBA float array: colour distance from the key -> alpha (0 below lo, 1 above hi), key colour unmixed from soft edges."""
    f = rgb.astype(np.float32)
    dist = np.sqrt(((f - key.astype(np.float32)) ** 2).sum(axis=2))
    a = np.clip((dist - lo) / (hi - lo), 0.0, 1.0)
    # unmix: pixel = a*fg + (1-a)*key  ->  fg = (pixel - (1-a)*key) / a
    safe = np.maximum(a, 1e-3)[..., None]
    fg = (f - (1.0 - a)[..., None] * key.astype(np.float32)) / safe
    fg = np.clip(fg, 0, 255)
    fg[a < 1e-3] = 0
    return np.dstack([fg, a * 255.0])


def flood_alpha(rgb: np.ndarray, step: int = 7, lo: float = 4.0, hi: float = 30.0, pockets: bool = False) -> tuple[np.ndarray, dict]:
    """For a background that is smooth but not flat (vignette, glow, shaded paper): grow the background inward from the sheet's frame, crossing only
    gentle colour steps (an outline is a sharp step and stops it), then take the colour of the nearest background pixel as the local key.
    Background pockets that the growth could not reach (between an arm and the body, the hole of a frame) are removed when they match that local key
    (only safe when the background colour never occurs in the art: key colours, not white).  Returns (RGBA float array, info)."""
    import cv2
    h, w = rgb.shape[:2]
    padded = cv2.copyMakeBorder(np.ascontiguousarray(rgb), 1, 1, 1, 1, cv2.BORDER_REPLICATE)
    mask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(padded, mask, (0, 0), (0, 0, 0), (step,) * 3, (step,) * 3, 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8))
    bg = mask[2:-2, 2:-2] > 0                      # the part of the background reachable from the frame
    info = {"bg_fraction": float(bg.mean())}
    if bg.sum() < 50:
        return np.dstack([rgb.astype(np.float32), np.full((h, w), 255.0, np.float32)]), info
    idx = ndimage.distance_transform_edt(~bg, return_distances=False, return_indices=True)
    local = rgb[idx[0], idx[1]].astype(np.float32)  # colour of the nearest background pixel
    f = rgb.astype(np.float32)
    dist = np.sqrt(((f - local) ** 2).sum(axis=2))
    like = dist < 9.0
    if pockets:
        pk = like & ~bg
        labels, n = ndimage.label(pk)
        if n:
            sizes = ndimage.sum(pk, labels, index=np.arange(1, n + 1))
            keep = np.zeros(n + 1, bool)
            keep[1:] = sizes >= 3000       # only big enclosed holes (a wreath, a frame); small white parts such as polka dots or highlights stay
            bg = bg | keep[labels]
            idx = ndimage.distance_transform_edt(~bg, return_distances=False, return_indices=True)
            local = rgb[idx[0], idx[1]].astype(np.float32)
            dist = np.sqrt(((f - local) ** 2).sum(axis=2))
    a = np.clip((dist - lo) / (hi - lo), 0.0, 1.0)
    near = ndimage.binary_dilation(bg, iterations=3)   # soft edges only next to the background
    a = np.where(bg, 0.0, np.where(near, a, 1.0))
    safe = np.maximum(a, 1e-3)[..., None]
    fg = np.clip((f - (1.0 - a)[..., None] * local) / safe, 0, 255)
    fg[a < 1e-3] = 0
    info["bg_fraction"] = float(bg.mean())
    return np.dstack([fg, a * 255.0]), info


def punch_centre_holes(rgb: np.ndarray, alpha: np.ndarray, boxes: list[tuple[int, int, int, int]], min_frac: float = 0.03) -> int:
    """Frames: the generator rarely leaves the middle plain white - it paints a soft smudge, a vignette or stray white shards there.  The drawn frame is
    made of dark outlines and saturated colours, the middle is only light or grey.  So the region of 'not drawn' pixels that contains the middle of each
    picture and does not reach the picture's edge is the inside of the frame; it becomes transparent.  Returns how many holes were punched."""
    f = rgb.astype(np.int32)
    lum = (f @ np.array([299, 587, 114])) // 1000
    chroma = f.max(axis=2) - f.min(axis=2)
    drawn = (lum < 170) | (chroma > 55)
    import cv2
    n = 0
    big = np.ascontiguousarray(rgb).copy()                    # OpenCV needs a writable array
    for x0, y0, x1, y1 in boxes:
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        crop = big[y0:y1, x0:x1].copy()
        regions = []
        # (1) not-drawn pixels (light or grey) connected to the middle: catches stray white shards
        labels, _ = ndimage.label(~drawn[y0:y1, x0:x1])
        lab = labels[cy - y0, cx - x0]
        if lab:
            regions.append(labels == lab)
        # (2) a growth over gentle colour steps from the middle: catches a smooth dark smudge
        mask = np.zeros((crop.shape[0] + 2, crop.shape[1] + 2), np.uint8)
        cv2.floodFill(crop, mask, (cx - x0, cy - y0), (0, 0, 0), (8,) * 3, (8,) * 3, 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8))
        regions.append(mask[1:-1, 1:-1] > 0)
        union = np.zeros((y1 - y0, x1 - x0), bool)
        for k, r in enumerate(regions):
            touches = r[0, :].any() or r[-1, :].any() or r[:, 0].any() or r[:, -1].any()
            # a frame with gaps (flowers, clouds) lets the light middle run out to the picture's edge: fine for the light-pixel region as long as it is not nearly the whole picture
            ok = (r.sum() < 0.9 * r.size) if k == 0 else not touches
            if ok and r.sum() >= min_frac * r.size:
                union |= r
        if not union.any():
            continue
        # also take the pale anti-aliasing fringe next to the hole, but never a thin drawn part (a dotted line) that sits right beside it
        union = union | (ndimage.binary_dilation(union, iterations=3) & ~drawn[y0:y1, x0:x1])
        alpha[y0:y1, x0:x1][union] = 0
        n += 1
    return n


def clean_alpha(alpha: np.ndarray) -> np.ndarray:
    """Remove isolated alpha specks, fill pinholes inside solid regions."""
    solid = alpha > 200
    holes = ndimage.binary_fill_holes(solid) & ~solid
    # a hole that is nearly transparent but fully surrounded by solid colour is a pinhole only when tiny
    labels, n = ndimage.label(holes)
    if n:
        sizes = ndimage.sum(holes, labels, index=np.arange(1, n + 1))
        tiny = np.isin(labels, np.where(sizes < 40)[0] + 1)
        alpha = np.where(tiny, 255.0, alpha)
    return alpha


def find_boxes(alpha: np.ndarray, min_area_frac: float = 0.004, merge_frac: float = 0.02) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (x0, y0, x1, y1) of the illustrations: pixels merged within merge_frac of the sheet's short side."""
    h, w = alpha.shape
    mask = alpha > 40
    r = int(min(h, w) * merge_frac)
    merged = ndimage.binary_dilation(mask, structure=np.ones((3, 3), bool), iterations=r) if r > 0 else mask
    labels, n = ndimage.label(merged)
    boxes = []
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        ys, xs = sl
        area = int((mask[sl] & (labels[sl] == i)).sum())
        if area < min_area_frac * h * w * 0.25:   # a speck far from everything: dropped
            continue
        boxes.append((xs.start, ys.start, xs.stop, ys.stop))
    return boxes


def boxes_by_grid(alpha: np.ndarray, cols: int, rows: int, min_area_frac: float = 0.0003) -> list[tuple[int, int, int, int]]:
    """For pictures made of far-apart parts (a paddle and its shuttlecock): every connected piece goes to the grid cell holding its centre,
    and a cell's pieces form one picture.  Returns [] unless every cell got something."""
    h, w = alpha.shape
    mask = alpha > 40
    labels, n = ndimage.label(mask)
    cells: dict[tuple[int, int], list[int]] = {}
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        area = int((labels[sl] == i).sum())
        if area < min_area_frac * h * w:
            continue
        ys, xs = sl
        cx, cy = (xs.start + xs.stop) / 2, (ys.start + ys.stop) / 2
        key = (min(rows - 1, int(cy / (h / rows))), min(cols - 1, int(cx / (w / cols))))
        b = cells.setdefault(key, [xs.start, ys.start, xs.stop, ys.stop])
        b[0], b[1], b[2], b[3] = min(b[0], xs.start), min(b[1], ys.start), max(b[2], xs.stop), max(b[3], ys.stop)
    if len(cells) != rows * cols:
        return []
    return [tuple(cells[(r, c)]) for r in range(rows) for c in range(cols)]


def order_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Reading order: rows by vertical centre (rows split where the centre jumps by more than half the median height), then left to right."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    med_h = float(np.median([b[3] - b[1] for b in boxes]))
    rows: list[list[tuple[int, int, int, int]]] = [[boxes[0]]]
    for b in boxes[1:]:
        cy = (b[1] + b[3]) / 2
        last_cy = np.mean([(q[1] + q[3]) / 2 for q in rows[-1]])
        if cy - last_cy > med_h * 0.5:
            rows.append([b])
        else:
            rows[-1].append(b)
    return [b for row in rows for b in sorted(row, key=lambda q: q[0])]


def slice_sheet(path: Path, cols: int | None = None, rows: int | None = None, key_hex: str | None = None,
                max_side: int = 1024, pad_frac: float = 0.04, holes: bool = False) -> tuple[list[Piece], dict]:
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im)
    h, w = rgb.shape[:2]
    key = np.array([int(key_hex[i:i + 2], 16) for i in (1, 3, 5)], np.float32) if key_hex else estimate_key(rgb)
    frame = np.concatenate([rgb[:6].reshape(-1, 3), rgb[-6:].reshape(-1, 3), rgb[:, :6].reshape(-1, 3), rgb[:, -6:].reshape(-1, 3)]).astype(np.float32)
    off_key = float((np.sqrt(((frame - key) ** 2).sum(axis=1)) > 40).mean())
    info = {"sheet": (w, h), "key": tuple(int(round(v)) for v in key), "expected": (cols * rows) if cols and rows else None, "border_off_key": off_key, "method": "key"}
    light = min(key) > 200                              # white or near-white: pale parts of the art are close to it, so decide by growth from the frame, not by colour distance
    if off_key > 0.02 or light:
        # grow the background from the frame (a vignette, glow or white paper): an outline is a sharp step and stops it
        chroma = (max(key) - min(key)) > 120             # a key colour never occurs inside the art, so enclosed pockets can be removed
        rgba, finfo = flood_alpha(rgb, pockets=holes or chroma)
        info.update(method="flood", **finfo)
        if finfo["bg_fraction"] < 0.35:
            info["count_problem"] = f"background could not be separated (only {finfo['bg_fraction']:.0%} of the sheet is background; outline too close to the background colour?)"
    else:
        rgba = key_to_alpha(rgb, key)
    rgba[..., 3] = clean_alpha(rgba[..., 3])
    rgba[:3, :, 3] = rgba[-3:, :, 3] = 0           # generators often leave a hairline along the sheet's own edge
    rgba[:, :3, 3] = rgba[:, -3:, 3] = 0
    want = cols * rows if cols and rows else None
    for mf in (0.02, 0.012, 0.006, 0.003, 0.0):     # parts of one picture (a sparkle, a Zzz) are merged while neighbouring pictures stay apart
        boxes = order_boxes(find_boxes(rgba[..., 3], merge_frac=mf))
        if want is None or len(boxes) == want:
            break
    if want is not None and len(boxes) != want:
        grid_boxes = boxes_by_grid(rgba[..., 3], cols, rows)
        if grid_boxes:
            boxes = grid_boxes
            info["grouped_by_grid"] = True
    info["found"] = len(boxes)
    if holes and boxes:
        info["holes_punched"] = punch_centre_holes(rgb, rgba[..., 3], boxes)
    pieces: list[Piece] = []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        crop = rgba[y0:y1, x0:x1]
        a = crop[..., 3] > 8
        ys, xs = np.where(a)
        if len(xs) == 0:
            continue
        cx0, cx1, cy0, cy1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        crop = crop[cy0:cy1, cx0:cx1]
        ph, pw = crop.shape[:2]
        pad = max(2, int(max(ph, pw) * pad_frac))
        canvas = np.zeros((ph + 2 * pad, pw + 2 * pad, 4), np.float32)
        canvas[pad:pad + ph, pad:pad + pw] = crop
        img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGBA")
        if max(img.size) > max_side:
            s = max_side / max(img.size)
            img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
        x0, y0, x1, y1 = x0 + int(cx0), y0 + int(cy0), x0 + int(cx1), y0 + int(cy1)     # the real extent (the search box was widened by the merge)
        piece = Piece(i, img, (x0, y0, x1, y1))
        # problems
        edge = 3
        if x0 <= 3 or y0 <= 3 or x1 >= w - 3 or y1 >= h - 3:
            piece.problems.append("touches the sheet edge (probably cut off)")
        arr = np.asarray(img)
        solid = arr[..., 3] > 200
        if solid.any() and not light:
            fg = arr[..., :3][solid].astype(np.float32)
            near = (np.sqrt(((fg - key) ** 2).sum(axis=1)) < 60).mean()
            if near > 0.01:
                piece.problems.append(f"{near:.1%} of the opaque pixels are close to the key colour (spill or a key-coloured part)")
        frac = solid.mean()
        if frac < 0.04:
            piece.problems.append(f"very little opaque area ({frac:.0%})")
        pieces.append(piece)
    # neighbouring boxes overlapping means two illustrations were merged or touch
    real = [pc.bbox for pc in pieces]
    for a_i, a in enumerate(real):
        for b_i, b in enumerate(real):
            if b_i <= a_i:
                continue
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                for idx in (a_i, b_i):
                    if idx < len(pieces):
                        pieces[idx].problems.append("overlaps another illustration's box")
    if info["expected"] is not None and info["expected"] != len(pieces) and "count_problem" not in info:
        info["count_problem"] = f"expected {info['expected']} illustrations, found {len(pieces)}"
    return pieces, info


def save_pieces(pieces: list[Piece], out: Path, names: list[str] | None = None, prefix: str = "item") -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for p in pieces:
        name = names[p.index] if names and p.index < len(names) else f"{prefix}-{p.index + 1:02d}"
        dst = out / f"{name}.webp"
        p.image.save(dst, "WEBP", quality=92, method=6, exact=True)
        paths.append(dst)
    return paths


def contact_sheet(pieces: list[Piece], dst: Path, cell: int = 220, cols: int = 6) -> None:
    """A checkerboard preview of the cut pieces (for a quick human/AI look)."""
    n = len(pieces)
    rows = max(1, -(-n // cols))
    sheet = Image.new("RGB", (cols * cell, rows * cell), (255, 255, 255))
    tile = np.indices((cell, cell)).sum(axis=0) // 14 % 2
    checker = Image.fromarray(np.where(tile[..., None], 232, 250).astype(np.uint8).repeat(3, axis=2), "RGB")
    for i, p in enumerate(pieces):
        cx, cy = (i % cols) * cell, (i // cols) * cell
        sheet.paste(checker, (cx, cy))
        im = p.image.copy()
        im.thumbnail((cell - 12, cell - 12))
        sheet.paste(im, (cx + (cell - im.width) // 2, cy + (cell - im.height) // 2), im)
    sheet.save(dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--cols", type=int)
    ap.add_argument("--rows", type=int)
    ap.add_argument("--key", help="key colour like #FF00FF (default: estimated from the border)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="item")
    ap.add_argument("--max-side", type=int, default=1024)
    a = ap.parse_args()
    pieces, info = slice_sheet(Path(a.sheet), a.cols, a.rows, a.key, a.max_side)
    paths = save_pieces(pieces, Path(a.out), prefix=a.prefix)
    contact_sheet(pieces, Path(a.out) / "_contact.png")
    print(info)
    for p, path in zip(pieces, paths):
        print(path.name, p.image.size, "; ".join(p.problems) or "ok")
    if info.get("count_problem"):
        sys.exit(info["count_problem"])


if __name__ == "__main__":
    main()
