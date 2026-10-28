"""みんなのイラスト: find the bits of a neighbouring picture that a cut-out leaves at the edge of a picture (2026-10-28: 14 pictures had them).

A stray piece is a small separate part of the picture (under 12% of the main figure and under 6,000 pixels) that touches the edge of the file; a sparkle or a heart inside the
frame is part of the picture and is not one.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def stray_pieces(path: Path) -> list[int]:
    """Sizes (pixels) of the stray pieces of a picture file; [] when it is clean."""
    with Image.open(path) as im:
        a = np.array(im.convert("RGBA"))[:, :, 3] > 128
    lab, k = ndimage.label(ndimage.binary_dilation(a, iterations=2))
    if k < 2:
        return []
    sizes = ndimage.sum(a, lab, range(1, k + 1))
    main = int(sizes.argmax()) + 1
    border = set(np.unique(np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]]))) - {0}
    return [int(sizes[i - 1]) for i in range(1, k + 1) if i != main and i in border and sizes[i - 1] < 0.12 * sizes[main - 1] and sizes[i - 1] < 6000]
