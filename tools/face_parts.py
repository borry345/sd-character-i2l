"""Expression face parts for a rig: take eyes/mouth from See-through runs of expression edits of the same
picture (same pose and canvas), split the eyes into left/right, and pull extra marks (blush, sweat) that
See-through put into the face layer.

  python face_parts.py --base seethrough_test/miku_grow_seed1/miku_chibi_sprite \
      --expr calm=seethrough_test/expr/calm_seed1/miku_chibi_calm --expr smile=... \
      --out seethrough_test/rig/face --effects effects --char miku

  Output (full 1024 page canvas, same as the base layers):
    <out>/<expr>/eyelash_l.png, eyelash_r.png, irides_l/r, eyewhite_l/r, eyebrow_l/r, mouth.png
                (mouth: colour from the run's src_img.png, rgb_from_src, then the skin ring is cleaned)
    <out>/<expr>/blush.png    only if the expression's face is pinker than the base face on the cheeks
    <out>/<expr>/sweat.png    only if the expression's face has a sweat drop (bluish blob outside the skin)
    <out>/base/...            the same split for the base picture
    <out>/face_parts.json     eye split column, per-expression pixel counts, mark boxes
    <out>/check_swap.png      base face + each expression's parts (and marks), for checking
    <effects>/sweat_drop/sweat_drop.png + source.json   cropped reusable effect (any character)
  "_l" = left side of the picture (viewer's left), as for the other *-l layers.
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layer_common import rgb_from_src  # noqa: E402

EYES = ['eyelash', 'irides', 'eyewhite', 'eyebrow']
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 16)


def load(d, tag):
    p = os.path.join(d, tag + '.png')
    return np.asarray(Image.open(p).convert('RGBA')).copy() if os.path.exists(p) else np.zeros((1024, 1024, 4), np.uint8)


def lab(a):
    return cv2.cvtColor(np.ascontiguousarray(a[..., :3]), cv2.COLOR_RGB2LAB).astype(np.float32)


def eye_cut(runs):
    """column between the two eyes with the fewest eye pixels over all runs (middle 40% of the eye span)"""
    u = np.zeros((1024, 1024), np.int32)
    for d in runs:
        for t in EYES:
            u += load(d, t)[..., 3] > 16
    cols = u.sum(0)
    xs = np.nonzero(cols)[0]
    a, b = xs.min(), xs.max()
    lo, hi = int(a + (b - a) * 0.3), int(a + (b - a) * 0.7)
    return lo + int(np.argmin(cols[lo:hi])), int(cols[lo:hi].min())


def clean_mouth(m, skin_lab):
    """See-through sometimes keeps a ring of face skin (with a faint grey edge) around the mouth.
    Keep only the mouth itself: dark line or red/pink pixels, the holes they enclose (teeth, tongue),
    plus 1px for the anti-aliased edge."""
    al = m[..., 3] > 16
    if al.sum() < 200:  # tiny closed mouth: no skin ring, and its lip lines are separate pieces
        return m, 0
    L = lab(m)
    core = al & ((L[..., 0] < 90 * 2.55) & ((L[..., 0] < 60 * 2.55) | (L[..., 1] > 145)))
    core = core | (al & (L[..., 1] > 145))
    core = core.astype(np.uint8)
    # fill enclosed holes (teeth inside the dark line)
    ff = core.copy(); h, w = ff.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 1)
    filled = core | (1 - ff)
    # only the biggest piece (a stray arc of the skin ring's edge is a separate piece)
    n, cc, st, _ = cv2.connectedComponentsWithStats(filled, connectivity=8)
    if n > 2:
        filled = (cc == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8)
    keep = cv2.dilate(filled, np.ones((3, 3), np.uint8)).astype(bool) & al
    out = m.copy()
    out[~keep, 3] = 0
    return out, int((al & ~keep).sum())


def blush_of(face, base_face, eye_bottom):
    """cheek areas where the expression face is pinker (Lab a*) than the base: copy those pixels, feathered.
    Only below the eyes, away from the face edge (redrawn outlines shift there), and pink itself."""
    both = (face[..., 3] > 200) & (base_face[..., 3] > 200)
    edge_d = cv2.distanceTransform((base_face[..., 3] > 200).astype(np.uint8), cv2.DIST_L2, 3)
    yy = np.mgrid[0:1024, 0:1024][0]
    fl = lab(face)
    region = both & (edge_d > 10) & (yy > eye_bottom)
    da = (fl[..., 1] - lab(base_face)[..., 1]) * region
    sm = cv2.GaussianBlur(da, (0, 0), 4)
    m = (sm > 3.0) & (fl[..., 1] > 137)  # Lab a* (OpenCV, 128 = neutral): visibly pink
    n, cc, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    keep = np.zeros_like(m)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area >= 150 and w < 3.5 * h and h < 3.5 * w:  # roundish blobs, not the thin outline-shift streaks
            keep |= cc == i
    if keep.sum() == 0:
        return None, []
    keep = cv2.dilate(keep.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & both
    fd = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3)
    out = np.zeros_like(face)
    out[keep, :3] = face[keep, :3]
    out[..., 3] = (np.clip(fd / 5.0, 0, 1) * 255).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8))
    return out, [list(map(int, st[i][:4])) for i in range(1, n)]


def sweat_of(face, base_face):
    """a bluish blob with its outline, outside the base face skin"""
    blue = (face[..., 3] > 16) & (face[..., 2].astype(int) - face[..., 0] > 40)
    n, cc, st, _ = cv2.connectedComponentsWithStats(blue.astype(np.uint8))
    al = face[..., 3] > 16
    n2, cc2 = cv2.connectedComponents(al.astype(np.uint8))
    out = np.zeros_like(face)
    boxes = []
    for i in range(1, n):
        if st[i][4] < 10:
            continue
        lbl = np.unique(cc2[cc == i]); lbl = lbl[lbl > 0]
        piece = np.isin(cc2, lbl)
        if piece.sum() > 3000:  # the blob is part of the big face area: take a padded box instead
            x, y, w, h = st[i][:4]
            box = np.zeros_like(piece); box[y - 6:y + h + 7, x - 6:x + w + 7] = True
            skin = np.linalg.norm(lab(face) - lab(base_face), axis=2) < 12
            piece = box & al & ~(skin & (base_face[..., 3] > 200))
        out[piece] = face[piece]
        ys, xs = np.nonzero(piece)
        boxes.append([int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)])
    return (out if boxes else None), boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='See-through tag folder of the base picture')
    ap.add_argument('--expr', action='append', default=[], help='name=tag folder of an expression run')
    ap.add_argument('--out', required=True)
    ap.add_argument('--effects', default=None, help='folder for reusable effect assets (sweat drop)')
    ap.add_argument('--char', default='char', help='character name written in the effect source.json')
    a = ap.parse_args()
    runs = [('base', a.base)] + [tuple(e.split('=', 1)) for e in a.expr]
    cut, cut_px = eye_cut([d for _, d in runs])
    print(f'[eyes] split at x={cut} ({cut_px} eye px in that column over all runs)')
    base_face = load(a.base, 'face')
    skin_lab = np.median(lab(base_face)[cv2.erode((base_face[..., 3] > 200).astype(np.uint8), np.ones((9, 9))) > 0], axis=0)
    ew = load(a.base, 'eyewhite')[..., 3] > 16
    rows = np.nonzero(ew.any(1))[0]
    eye_bottom = int((rows.min() + rows.max()) // 2) if ew.any() else 0  # middle of the eyes: cheeks start here
    info = {'eye_split_x': cut, 'eye_split_px': cut_px, 'left': 'x < eye_split_x (viewer left)', 'runs': {}}
    for name, d in runs:
        od = os.path.join(a.out, name)
        os.makedirs(od, exist_ok=True)
        r = {}
        for t in EYES:
            im = load(d, t)
            for sfx, sel in (('l', slice(0, cut)), ('r', slice(cut, 1024))):
                part = np.zeros_like(im)
                part[:, sel] = im[:, sel]
                Image.fromarray(part).save(os.path.join(od, f'{t}_{sfx}.png'))
                r[f'{t}_{sfx}'] = int((part[..., 3] > 16).sum())
        m = load(d, 'mouth')
        src = load(d, 'src_img')  # the run's input picture on the page
        if src[..., 3].any():
            m = rgb_from_src(m, src)  # grey soft edge -> "whiskers" (layer_common.py)
            r['mouth_rgb_from_src'] = True
        m, rim = clean_mouth(m, skin_lab)
        Image.fromarray(m).save(os.path.join(od, 'mouth.png'))
        r['mouth'] = int((m[..., 3] > 16).sum()); r['mouth_rim_removed'] = rim
        if name != 'base':
            face = load(d, 'face')
            bl, bb = blush_of(face, base_face, eye_bottom)
            if bl is not None:
                Image.fromarray(bl).save(os.path.join(od, 'blush.png')); r['blush_boxes'] = bb
            sw, sb = sweat_of(face, base_face)
            if sw is not None:
                Image.fromarray(sw).save(os.path.join(od, 'sweat.png')); r['sweat_boxes'] = sb
                if a.effects:
                    x, y, w, h = sb[0]
                    ed = os.path.join(a.effects, 'sweat_drop'); os.makedirs(ed, exist_ok=True)
                    pad = 2
                    crop = sw[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
                    Image.fromarray(crop).save(os.path.join(ed, 'sweat_drop.png'))
                    json.dump({'what': 'sweat drop effect, transparent, cropped (usable for any character)',
                               'size': [int(crop.shape[1]), int(crop.shape[0])],
                               'made_from': f'{a.char} "{name}" expression, See-through face layer',
                               'placements': {a.char: {'page_xy': [max(0, x - pad), max(0, y - pad)], 'page': '1024 square'}}},
                              open(os.path.join(ed, 'source.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        info['runs'][name] = r
        print(name, r)
    json.dump(info, open(os.path.join(a.out, 'face_parts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    check(a, runs, base_face, cut)


def check(a, runs, base_face, cut):
    fb = Image.fromarray(base_face).getchannel('A').getbbox()
    box = (fb[0] - 30, fb[1] - 20, fb[2] + 30, fb[3] + 30)
    cells = []
    order = ['face', 'blush', 'eyewhite_l', 'eyewhite_r', 'irides_l', 'irides_r', 'eyelash_l', 'eyelash_r',
             'eyebrow_l', 'eyebrow_r', 'mouth', 'sweat']
    for name, _ in runs:
        c = Image.new('RGBA', (1024, 1024), (255, 255, 255, 255))
        for t in order:
            p = os.path.join(a.out, name, t + '.png')
            if t == 'face':
                c.alpha_composite(Image.fromarray(base_face))
            elif os.path.exists(p):
                c.alpha_composite(Image.open(p))
        dr = ImageDraw.Draw(c)
        dr.line([(cut, box[1]), (cut, box[1] + 12)], fill=(255, 0, 0), width=2)  # eye split mark
        cells.append((name, c.crop(box).convert('RGB').resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.LANCZOS)))
    w, h = cells[0][1].size
    cols = 4
    s = Image.new('RGB', (w * cols, (h + 26) * ((len(cells) + cols - 1) // cols)), 'white')
    d = ImageDraw.Draw(s)
    for i, (n, im) in enumerate(cells):
        x, y = (i % cols) * w, (i // cols) * (h + 26)
        s.paste(im, (x, y + 26)); d.text((x + 6, y + 4), n, font=FONT, fill='black')
    s.save(os.path.join(a.out, 'check_swap.png'))


if __name__ == '__main__':
    main()
