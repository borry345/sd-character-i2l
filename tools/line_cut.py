"""Cut a layer along lines a person drew on a copy of it, keep the piece in between.

  python line_cut.py --lined cut_lined_handwear-l.png --layer 00_handwear-l.png --out cloth_l.png

  - The lined copy has the same size as the layer. Drawn lines are walls: yellow lines everywhere, red lines
    only in the top half (with --red_top_only, the default: red at the bottom is a guide, the yellow curve
    cuts there). Red pixels that match the layer itself (e.g. a red tattoo) are not walls.
  - The layer (without the drawn lines, original colours) is split by the walls; the kept piece is the one
    with the most dark pixels (--keep dark; the sleeve cloth) or the biggest (--keep big). Wall pixels next
    to it go back to it with their original colours.
"""
import argparse

import cv2
import numpy as np
from PIL import Image


def line_cut(lined, org, red_top_only=True, keep='dark'):
    a = lined.astype(int)
    r, g, b, al = [a[..., i] for i in range(4)]
    red = (r > 150) & (g < 110) & (b < 110) & (al > 60)
    yel = (r > 150) & (g > 150) & (b < 120) & (al > 60)
    diff = np.abs(a[..., :3] - org[..., :3].astype(int)).max(2) > 30  # drawn pixels differ from the layer
    oy = np.nonzero(org[..., 3] > 16)[0]
    ymid = (oy.min() + oy.max()) // 2
    walls = yel & diff
    n, cc, st, _ = cv2.connectedComponentsWithStats(red.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        m = cc == i
        if red_top_only and st[i][1] + st[i][3] // 2 > ymid:
            continue
        if (diff & m).sum() > 0.5 * m.sum():
            walls |= m
    walls = cv2.dilate(walls.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    body = (org[..., 3] > 16) & ~walls
    n, cc, st, _ = cv2.connectedComponentsWithStats(body.astype(np.uint8), connectivity=4)
    order = np.argsort(-st[1:, 4]) + 1
    lum = org[..., :3].mean(2)
    if keep == 'dark':
        best = max(order[:5], key=lambda i: ((cc == i) & (lum < 80)).sum())
    else:
        best = order[0]
    kept = cc == best
    kept |= walls & (org[..., 3] > 16) & cv2.dilate(kept.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    out = org.copy()
    out[~kept] = 0
    return out, [int(st[i, 4]) for i in order[:5]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lined', required=True, help='copy of the layer with red/yellow cut lines drawn on it')
    ap.add_argument('--layer', required=True, help='the clean layer (same size)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--red_everywhere', action='store_true', help='red lines cut in the bottom half too')
    ap.add_argument('--keep', choices=['dark', 'big'], default='dark')
    a = ap.parse_args()
    lined = np.asarray(Image.open(a.lined).convert('RGBA'))
    org = np.asarray(Image.open(a.layer).convert('RGBA'))
    out, pieces = line_cut(lined, org, not a.red_everywhere, a.keep)
    Image.fromarray(out).save(a.out)
    print(f'[line_cut] pieces {pieces} -> kept {int((out[..., 3] > 16).sum())}px -> {a.out}')


if __name__ == '__main__':
    main()
