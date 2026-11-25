"""Complete only the hidden part of a layer that would really continue behind the layers in front.

  python amodal_complete.py --target tail.png --front a.png --front b.png --out tail_done.png --prompt "..."

  1. Visible part = target pixels not covered by any --front layer (whatever was filled under them
     before is dropped).
  2. Where the front layers were, near the visible part (--search_px), the canvas is a flat key colour
     (magenta) and SDXL inpaints there with a prompt that asks for the part on that flat background.
  3. The key colour is removed, so the drawn shape itself decides how far the part continues
     (the "mask 2"). Optional --shape mask limits where it may go (white = allowed).
  4. Only drawn pieces connected to the visible part are kept.

  --debug also saves the in-between masks at full size, next to --out, so a bad result can be traced
  to the step that caused it (the normal output does not change):
    <out>_dbg_01_visible.png       visible part (white)
    <out>_dbg_02_region.png        where it may draw (white)
    <out>_dbg_03_mask2[_seedN].png drawn shape = mask 2 (key: one per candidate seed)
    <out>_dbg_04_prefill.png       hull only: area painted with the nearest colours, before SDXL
    <out>_dbg.json                 pixel counts, crop box, candidate colour errors, picked seed
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mask_inpaint import REPO, generate  # noqa: E402


def checker(img):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.where(((yy // 16 + xx // 16) % 2)[..., None] == 0, 255, 205).astype(np.float32).repeat(3, 2)
    al = img[..., 3:].astype(np.float32) / 255
    return (img[..., :3] * al + bg * (1 - al)).astype(np.uint8)


class Debug:
    """--debug: write in-between images as <out>_dbg_*.png and a summary <out>_dbg.json"""

    def __init__(self, a):
        self.on = a.debug
        self.base = os.path.splitext(a.out)[0] + '_dbg'
        self.info = {'mode': a.mode, 'target': a.target, 'front': a.front, 'shape': a.shape,
                     'search_px': a.search_px, 'prompt': a.prompt, 'seed': a.seed, 'steps': a.steps, 'model': a.model or REPO}

    def mask(self, name, m):
        if self.on:
            Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).save(f'{self.base}_{name}.png')

    def rgba(self, name, img):
        if self.on:
            Image.fromarray(img).save(f'{self.base}_{name}.png')

    def save(self, **kw):
        if self.on:
            self.info.update(kw)
            with open(self.base + '.json', 'w', encoding='utf-8') as f:
                json.dump(self.info, f, ensure_ascii=False, indent=1)
            print(f'[debug] {self.base}_*.png, {self.base}.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True)
    ap.add_argument('--front', action='append', default=[], help='layers in front of the target')
    ap.add_argument('--out', required=True)
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--negative', default='head, face, skin, ribbon, hair tie, gradient background, white background, '
                                          'shadow, text, watermark, blurry, lowres')
    ap.add_argument('--search_px', type=int, default=90, help='how far behind the front layers the part may continue')
    ap.add_argument('--shape', default=None, help='optional mask: white = the part may be drawn there')
    ap.add_argument('--key', default='255,0,255')
    ap.add_argument('--margin', type=int, default=80)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--steps', type=int, default=30)
    ap.add_argument('--model', default=None, help='SDXL in diffusers format (default: SDXL inpainting 0.1; e.g. an anime SDXL)')
    ap.add_argument('--candidates', type=int, default=3, help='seeds to try; the one whose colours match best wins')
    ap.add_argument('--mode', choices=['key', 'hull'], default='key',
                    help='key: SDXL draws the shape on a magenta background; hull: shape = convex outline (colour-safe)')
    ap.add_argument('--strength', type=float, default=0.5, help='hull mode: how much SDXL repaints the pre-filled area')
    ap.add_argument('--line_px', type=int, default=2, help='hull mode: outline width')
    ap.add_argument('--debug', action='store_true', help='also save the in-between masks (<out>_dbg_*.png, <out>_dbg.json)')
    a = ap.parse_args()
    dbg = Debug(a)

    tgt = np.asarray(Image.open(a.target).convert('RGBA')).copy()
    H, W = tgt.shape[:2]
    cover = np.zeros((H, W), bool)
    for f in a.front:
        cover |= np.asarray(Image.open(f).convert('RGBA'))[..., 3] >= 16
    vis = (tgt[..., 3] > 0) & ~cover
    key = np.array([int(v) for v in a.key.split(',')], np.float32)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.search_px + 1, 2 * a.search_px + 1))
    region = cover & cv2.dilate(vis.astype(np.uint8), k).astype(bool)
    if a.shape:
        region &= np.asarray(Image.open(a.shape).convert('L')) > 127
    print(f'[region] visible {int(vis.sum())}px, may draw in {int(region.sum())}px')
    dbg.mask('01_visible', vis)
    dbg.mask('02_region', region)
    dbg.info.update(visible_px=int(vis.sum()), region_px=int(region.sum()))
    if a.mode == 'hull':
        return hull_mode(a, tgt, vis, region, dbg)

    ys, xs = np.nonzero(region)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    side = max(256, int(max(xs.max() - xs.min(), ys.max() - ys.min()) + 2 * a.margin))
    x0 = int(np.clip(cx - side / 2, 0, max(0, W - side))); y0 = int(np.clip(cy - side / 2, 0, max(0, H - side)))
    x1, y1 = min(W, x0 + side), min(H, y0 + side)

    # canvas: visible part over the key colour; everything else (incl. removed front area) = key
    al = (tgt[..., 3:].astype(np.float32) / 255) * vis[..., None]
    canvas = (tgt[..., :3] * al + key * (1 - al)).astype(np.uint8)
    gmask = cv2.dilate(region.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    crop = Image.fromarray(canvas[y0:y1, x0:x1]).resize((1024, 1024), Image.LANCZOS)
    mcrop = Image.fromarray((gmask[y0:y1, x0:x1] * 255).astype(np.uint8)).resize((1024, 1024), Image.NEAREST)
    print(f'[crop] ({x0},{y0})-({x1},{y1}) side {x1 - x0}px -> 1024')

    # reference colour of the part: visible, not line art
    lum_t = tgt[..., :3].astype(np.float32).mean(axis=2)
    ref_px = tgt[vis & (lum_t > 70), :3]
    ref_lab = cv2.cvtColor(ref_px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    ref_ab = np.median(ref_lab[:, 1:], axis=0)

    best = None
    cands = []
    for s in range(a.seed, a.seed + a.candidates):
        img = generate(crop, mcrop, a.prompt, a.negative, 0.99, a.steps, 7.0, s, a.model or REPO)
        res = finish(img, tgt, vis, region, key, x0, y0, x1, y1)
        out, drawn = res
        gm = drawn > 0.5
        lum = out[..., :3].astype(np.float32).mean(axis=2)
        px = out[gm & (lum > 70), :3]
        if len(px) < 50:
            err = 999.0
        else:
            lab = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
            err = float(np.median(np.linalg.norm(lab[:, 1:] - ref_ab, axis=1)))  # hue/chroma distance
        print(f'[candidate] seed {s}: drawn {int(gm.sum())}px, colour error {err:.1f}')
        save_check(os.path.splitext(a.out)[0] + f'_seed{s}_check.png', tgt, canvas, gmask, img, out, x0, y0, x1, y1)
        dbg.mask(f'03_mask2_seed{s}', drawn)
        cands.append({'seed': s, 'drawn_px': int(gm.sum()), 'colour_error': round(err, 2)})
        if best is None or err < best[0]:
            best = (err, s, out)
    err, s, out = best
    Image.fromarray(out).save(a.out)
    print(f'[done] picked seed {s} (colour error {err:.1f}) -> {a.out}')
    dbg.save(crop=[x0, y0, x1, y1], candidates=cands, picked_seed=s, picked_colour_error=round(err, 2))


def hull_mode(a, tgt, vis, region, dbg):
    """mask 2 = the part's own convex outline inside the hidden area: the edges are closed with
    straight-ish lines (like a tail whose side runs on behind the head). The new area is painted
    with the part's nearest colours, refined by SDXL at low strength, and outlined."""
    from scipy.ndimage import distance_transform_edt
    H, W = vis.shape
    hull = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(hull, cv2.convexHull(cv2.findNonZero(vis.astype(np.uint8))), 1)
    new = region & hull.astype(bool)
    if a.shape:
        new &= np.asarray(Image.open(a.shape).convert('L')) > 127
    # only the piece(s) that touch the visible part
    n, cc = cv2.connectedComponents((new | vis).astype(np.uint8), connectivity=8)
    t = np.unique(cc[vis]); new &= np.isin(cc, t[t > 0])
    print(f'[hull] mask 2 = {int(new.sum())}px')

    rgb = tgt[..., :3].copy()
    lum = rgb.astype(np.float32).mean(axis=2)
    src = vis & (tgt[..., 3] > 200) & (lum > 70)  # skip line art
    src_core = cv2.erode(src.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    if src_core.sum() > 100:
        src = src_core
    _, (iy, ix) = distance_transform_edt(~src, return_indices=True)
    pre = rgb.copy()
    pre[new] = rgb[iy[new], ix[new]]
    dbg.mask('03_mask2', new)
    pf = np.zeros_like(tgt); pf[vis] = tgt[vis]; pf[new, :3] = pre[new]; pf[new, 3] = 255
    dbg.rgba('04_prefill', pf)

    ys, xs = np.nonzero(new)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    side = max(256, int(max(xs.max() - xs.min(), ys.max() - ys.min()) + 2 * a.margin))
    x0 = int(np.clip(cx - side / 2, 0, max(0, W - side))); y0 = int(np.clip(cy - side / 2, 0, max(0, H - side)))
    x1, y1 = min(W, x0 + side), min(H, y0 + side)
    full = vis | new
    ctx = np.where(full[..., None], pre, 255).astype(np.uint8)
    crop = Image.fromarray(ctx[y0:y1, x0:x1]).resize((1024, 1024), Image.LANCZOS)
    mcrop = Image.fromarray((new[y0:y1, x0:x1] * 255).astype(np.uint8)).resize((1024, 1024), Image.NEAREST)
    img = generate(crop, mcrop, a.prompt, a.negative, a.strength, a.steps, 7.0, a.seed, a.model or REPO)
    gen = np.asarray(Image.fromarray(img).resize((x1 - x0, y1 - y0), Image.LANCZOS))

    out = np.zeros_like(tgt)
    out[vis] = tgt[vis]
    sub = new[y0:y1, x0:x1]
    reg = out[y0:y1, x0:x1]
    reg[sub, :3] = gen[sub]
    reg[sub, 3] = 255
    # outline on the new edge, in the part's own line colour
    dark = vis & (lum < 60) & (tgt[..., 3] > 200)
    line_col = np.median(rgb[dark], axis=0).astype(np.uint8) if dark.sum() > 20 else np.array([20, 20, 20], np.uint8)
    inner = cv2.erode(full.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.line_px + 1,) * 2)).astype(bool)
    line = full & ~inner & new
    out[line, :3] = line_col
    out[line, 3] = 255
    Image.fromarray(out).save(a.out)
    print(f'[done] mask 2 drawn {int(new.sum())}px, outline {int(line.sum())}px -> {a.out}')
    dbg.save(crop=[x0, y0, x1, y1], mask2_px=int(new.sum()), outline_px=int(line.sum()),
             strength=a.strength, picked_seed=a.seed)

    m2 = np.zeros((H, W, 4), np.uint8); m2[..., 3] = 255
    view = checker(tgt)
    view2 = view.copy(); view2[new] = (view2[new] * 0.4 + np.array([0, 200, 0]) * 0.6).astype(np.uint8)
    sheet = [view[y0:y1, x0:x1], view2[y0:y1, x0:x1], checker(out)[y0:y1, x0:x1]]
    w, h = x1 - x0, y1 - y0
    s = Image.new('RGB', (w * 3, h), 'white')
    for i, im in enumerate(sheet):
        s.paste(Image.fromarray(im), (i * w, 0))
    s.save(os.path.splitext(a.out)[0] + '_hull_check.png')


def finish(img, tgt, vis, region, key, x0, y0, x1, y1):
    H, W = vis.shape
    gen = np.asarray(Image.fromarray(img).resize((x1 - x0, y1 - y0), Image.LANCZOS)).astype(np.float32)

    # key out: distance to the key colour -> alpha, then remove key spill from soft edges
    d = np.linalg.norm(gen - key, axis=2)
    alpha = np.clip((d - 60) / 70, 0, 1)
    alpha[~region[y0:y1, x0:x1]] = 0
    safe = np.maximum(alpha, 1e-3)[..., None]
    col = np.clip((gen - (1 - alpha[..., None]) * key) / safe, 0, 255)

    drawn = np.zeros((H, W), np.float32)
    drawn[y0:y1, x0:x1] = alpha
    rgbg = np.zeros((H, W, 3), np.float32)
    rgbg[y0:y1, x0:x1] = col

    # keep only pieces touching the visible part
    solid = (drawn > 0.5) | vis
    n, cc = cv2.connectedComponents(solid.astype(np.uint8), connectivity=8)
    touching = np.unique(cc[vis])
    keep = np.isin(cc, touching[touching > 0])
    drawn[~keep] = 0
    drawn[vis] = 0  # visible pixels stay as they are

    out = np.zeros_like(tgt)
    out[vis] = tgt[vis]
    gm = drawn > 0
    out[gm, :3] = rgbg[gm].astype(np.uint8)
    out[gm, 3] = (drawn[gm] * 255).astype(np.uint8)
    return out, drawn


def save_check(path, tgt, canvas, gmask, img, out, x0, y0, x1, y1):
    before = checker(tgt[y0:y1, x0:x1])
    mid = canvas[y0:y1, x0:x1].copy()
    mid[gmask[y0:y1, x0:x1]] = (mid[gmask[y0:y1, x0:x1]] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)
    raw = np.asarray(Image.fromarray(img).resize((x1 - x0, y1 - y0), Image.LANCZOS))
    after = checker(out[y0:y1, x0:x1])
    w, h = x1 - x0, y1 - y0
    sheet = Image.new('RGB', (w * 4, h), 'white')
    for i, im in enumerate([before, mid, raw, after]):
        sheet.paste(Image.fromarray(im), (i * w, 0))
    sheet.save(path)


if __name__ == '__main__':
    main()
