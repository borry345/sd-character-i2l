"""Keep only the cloth of a detached-sleeve layer: drop the skin above the sleeve's top trim (shoulder) and
thin left-over strokes. Use after split_hand.py has taken the hand off the bottom.

  python sleeve_cloth.py --layer sleeve_l.png --out cloth_l.png

  1. top trim = trim-coloured (teal) pixels in the upper half of the layer; per column, everything more
     than --keep_line px above the trim's top is removed, and light pixels (skin) between that and the
     trim too. The dark outline just above the trim stays with the cloth.
  2. thin strokes not part of the solid cloth (e.g. pieces of the hand's outline) are removed: morphological
     opening with a --open_px disc, keep the biggest piece, then give back 1px of the original edge
     (anti-aliasing).
  Columns without trim use the nearest trim column. Trim colour: G and B both > R + 40.

  --edge N | auto (recommended; auto = N from the black outline thickness on the sleeve's sides, works on the full sleeve layer, hand and shoulder skin included):
    both ends are set from the trims instead: the top edge N px above the top trim, the bottom edge N px
    below the bottom trim (per column, lightly smoothed, carried on past the trim's ends). The band between
    trim and edge is painted outline colour, so both sleeves get the same outline thickness, and the edge
    has a 1px soft (anti-aliased) cut: no staircase like a hand-drawn line cut.
"""
import argparse

import cv2
import numpy as np
from PIL import Image


def _trim_curve(trim, which):
    """per-column top (which='top') or bottom edge of the trim, filled across gaps and past both ends,
    smoothed over 5 columns but never moved into the trim"""
    ty, tx = np.nonzero(trim)
    xs = np.unique(tx)
    ys = np.array([ty[tx == x].min() if which == 'top' else ty[tx == x].max() for x in xs], np.float32)
    X = np.arange(trim.shape[1])
    full = np.interp(X, xs, ys).astype(np.float32)
    # past the ends: carry on along the trim's slope (fitted over its last 12 columns), not flat
    k = min(12, len(xs))
    if k >= 3:
        pl = np.polyfit(xs[:k], ys[:k], 1); pr = np.polyfit(xs[-k:], ys[-k:], 1)
        full[X < xs[0]] = np.polyval(pl, X[X < xs[0]])
        full[X > xs[-1]] = np.polyval(pr, X[X > xs[-1]])
    sm = np.convolve(np.pad(full, 2, mode='edge'), np.ones(5) / 5, mode='valid')
    return np.minimum(sm, full) if which == 'top' else np.maximum(sm, full)


def side_outline_px(im, thr=25, rows=(0.35, 0.75)):
    """median thickness of the black outline on the sleeve's left and right sides (middle rows)"""
    al = im[..., 3].astype(int); lum = im[..., :3].astype(int).mean(2)
    ys = np.nonzero(al.max(1) > 16)[0]; y0, y1 = ys.min(), ys.max()
    th = []
    for y in range(int(y0 + (y1 - y0) * rows[0]), int(y0 + (y1 - y0) * rows[1]), 2):
        xs = np.nonzero(al[y] > 16)[0]
        for side in (xs, xs[::-1]):
            n = 0
            for x in side:
                if lum[y, x] < thr:
                    n += 1
                elif n > 0 or al[y, x] > 128:
                    break
            th.append(n)
    return float(np.median(th))


def trim_edges(im, n=5, line=(12, 12, 12)):
    """cut the sleeve N px outside its top and bottom trims, outline colour in between, soft 1px edge"""
    al = im[..., 3] > 16
    r, g, b = [im[..., i].astype(int) for i in range(3)]
    teal = al & (g > r + 40) & (b > r + 40)
    ys, xs = np.nonzero(al)
    ymid = (ys.min() + ys.max()) // 2
    top_t = teal.copy(); top_t[ymid:] = False
    bot_t = teal.copy(); bot_t[:ymid] = False
    if not top_t.any() or not bot_t.any():
        raise SystemExit('need a top and a bottom trim (teal pixels in each half)')

    def biggest(m):  # the trim is one band; bluish highlights elsewhere are small separate bits
        n_, cc_, st_, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        return cc_ == 1 + int(np.argmax(st_[1:, 4])) if n_ > 2 else m
    top_t, bot_t = biggest(top_t), biggest(bot_t)
    H, W = al.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t_top = _trim_curve(top_t, 'top')[xx.astype(int)]
    t_bot = _trim_curve(bot_t, 'bottom')[xx.astype(int)]
    cov = np.clip(np.minimum((yy + 0.5) - (t_top - n), (t_bot + n) + 0.5 - yy), 0, 1)
    a = im[..., 3].astype(np.float32) / 255 * cov
    out = im.copy()
    band = (a > 0) & ((yy < t_top - 0.5) | (yy > t_bot + 0.5))
    out[band, :3] = line
    out[..., 3] = np.round(a * 255).astype(np.uint8)
    # anything not attached to the main cloth (e.g. a finger tip between the edges) goes
    n_, cc, st, _ = cv2.connectedComponentsWithStats((out[..., 3] > 16).astype(np.uint8), connectivity=8)
    if n_ > 2:
        out[(cc != 1 + int(np.argmax(st[1:, 4])))] = 0
    return out


def cloth_only(im, keep_line=6, open_px=7, light=90):
    al = im[..., 3] > 16
    r, g, b = [im[..., i].astype(int) for i in range(3)]
    teal = al & (g > r + 40) & (b > r + 40)
    ys, xs = np.nonzero(al)
    ymid = (ys.min() + ys.max()) // 2
    tt = teal.copy(); tt[ymid:] = False
    ty, tx = np.nonzero(tt)
    if len(ty) == 0:
        raise SystemExit('no top trim found (teal pixels in the upper half)')
    top = np.full(im.shape[1], -1)
    for x in np.unique(tx):
        top[x] = ty[tx == x].min()
    cols = np.nonzero(top >= 0)[0]
    for x in range(im.shape[1]):
        if top[x] < 0:
            top[x] = top[cols[np.argmin(np.abs(cols - x))]]
    yy, xx = np.mgrid[0:im.shape[0], 0:im.shape[1]]
    lum = (r + g + b) / 3
    skin_top = al & ((yy < top[xx] - keep_line) | ((yy < top[xx] - 1) & (lum > light)))
    cloth = al & ~skin_top
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_px, open_px))
    solid = cv2.morphologyEx(cloth.astype(np.uint8), cv2.MORPH_OPEN, k)
    n, cc, st, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    solid = (cc == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8)
    keep = cv2.dilate(solid, np.ones((3, 3), np.uint8)).astype(bool) & cloth
    out = im.copy()
    out[~keep] = 0
    return out, int(skin_top.sum()), int((cloth & ~keep).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--keep_line', type=int, default=6, help='px above the trim kept as outline (dark pixels only)')
    ap.add_argument('--open_px', type=int, default=7, help='strokes thinner than this are removed')
    ap.add_argument('--edge', default=None,
                    help='set both ends N px outside the trims (see top); "auto" = the side outline thickness')
    a = ap.parse_args()
    im = np.asarray(Image.open(a.layer).convert('RGBA')).copy()
    if a.edge is not None:
        # auto: same thickness as the black outline on the sleeve's sides (+0.5 for the soft last pixel)
        n = side_outline_px(im) + 0.5 if a.edge == 'auto' else float(a.edge)
        out = trim_edges(im, n)
        Image.fromarray(out).save(a.out)
        print(f'[sleeve_cloth] edges {n}px outside the trims, cloth {int((out[..., 3] > 16).sum())}px -> {a.out}')
        return
    out, skin, strokes = cloth_only(im, a.keep_line, a.open_px)
    Image.fromarray(out).save(a.out)
    print(f'[sleeve_cloth] removed skin {skin}px, strokes {strokes}px, cloth {int((out[..., 3] > 16).sum())}px -> {a.out}')


if __name__ == '__main__':
    main()
