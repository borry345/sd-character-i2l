"""Cut a long part (twin tail, ...) into a chain of pieces along lines a person drew (any shape: V, curve),
for a rig where each piece swings around the top of the cut above it.

  python split_chain.py --layer 14_tail_left.png --lined lined_tail_left.png --out_dir tail_l --names root,mid,tip

  - The lined copy has the same size as the layer. Red lines (R>150, G,B<110, different from the layer)
    are the cuts; each line should run across the whole part (a line that stops short of the outline is
    carried on along its end direction until it leaves the part).
  - Pieces are numbered from the top. --front top (default): the upper piece is drawn in front (root over
    mid over tip); --front bottom the other way.
  - The BACK piece of each cut also keeps the front piece's original pixels within --overlap px of the
    line (hidden behind the front piece when straight). Swung, it fills the gap that would open on the
    outer side of the bend.
  - Pivot of each cut = middle of the line's two ends (where it meets the outline); the lower piece and
    everything below turn around it.
  - Writes <out_dir>/<name>.png (full canvas, alpha-bled), chain.json (pivots, order) and chain_check.png
    (straight, then swings of the whole chain).
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layer_common import bleed  # noqa: E402

FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 14)


def red_lines(lined, org):
    a = lined.astype(int)
    red = (a[..., 0] > 150) & (a[..., 1] < 110) & (a[..., 2] < 110) & (a[..., 3] > 60)
    red &= np.abs(a[..., :3] - org[..., :3].astype(int)).max(2) > 30
    red = cv2.dilate(red.astype(np.uint8), np.ones((3, 3), np.uint8))
    n, cc, st, _ = cv2.connectedComponentsWithStats(red, connectivity=8)
    lines = [cc == i for i in range(1, n) if st[i, 4] >= 20]
    lines.sort(key=lambda m: np.nonzero(m)[0].mean())
    return lines


def extend(line, alpha, steps=60):
    """carry each end of the line on (along the direction of its last 10px) until it leaves the part"""
    ys, xs = np.nonzero(line)
    pts = np.stack([xs, ys], 1).astype(float)
    out = line.copy()
    ends = []
    for side in (0, 1):
        i = np.argmin(xs) if side == 0 else np.argmax(xs)
        p = pts[i]
        near = pts[np.linalg.norm(pts - p, axis=1) < 12]
        d = p - near.mean(0)
        d = d / (np.linalg.norm(d) + 1e-6)
        q = p.copy()
        for _ in range(steps):
            x, y = int(round(q[0])), int(round(q[1]))
            if not (0 <= x < alpha.shape[1] and 0 <= y < alpha.shape[0]) or not alpha[y, x]:
                break
            cv2.circle(out.view(np.uint8), (x, y), 1, 1, -1)
            q += d
        ends.append(q.copy())
    return out.astype(bool), ends


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--lined', required=True)
    ap.add_argument('--out_dir', required=True)
    ap.add_argument('--names', default=None, help='comma separated, top to bottom (default piece0,piece1,...)')
    ap.add_argument('--front', choices=['top', 'bottom'], default='top')
    ap.add_argument('--overlap', type=int, default=14)
    ap.add_argument('--feather', type=int, default=8, help='front piece fades out over N px past the cut (0 = hard cut)')
    a = ap.parse_args()
    org = np.asarray(Image.open(a.layer).convert('RGBA'))
    lined = np.asarray(Image.open(a.lined).convert('RGBA'))
    alpha = org[..., 3] > 16
    lines = red_lines(lined, org)
    walls = np.zeros_like(alpha)
    pivots = []
    for ln in lines:
        ext, ends = extend(ln, alpha)
        walls |= ext
        pivots.append(((ends[0] + ends[1]) / 2).tolist())
    n, cc, st, _ = cv2.connectedComponentsWithStats((alpha & ~walls).astype(np.uint8), connectivity=4)
    order = np.argsort(-st[1:, 4])[:len(lines) + 1] + 1
    if len(order) < len(lines) + 1 or st[order[-1], 4] < 200:
        raise SystemExit(f'lines do not split the part into {len(lines) + 1} pieces: sizes {sorted(st[1:, 4])[::-1][:6]}')
    order = sorted(order, key=lambda i: st[i, 1] + st[i, 3] / 2)  # top to bottom
    lab = np.zeros(alpha.shape, int) - 1
    for k, i in enumerate(order):
        lab[cc == i] = k
    # every other pixel of the part (walls, small bits) goes to the nearest piece
    from scipy.ndimage import distance_transform_edt
    _, (iy, ix) = distance_transform_edt(lab < 0, return_indices=True)
    rest = alpha & (lab < 0)
    lab[rest] = lab[iy[rest], ix[rest]]
    names = a.names.split(',') if a.names else [f'piece{k}' for k in range(len(order))]
    assert len(names) == len(order), f'{len(order)} pieces, {len(names)} names'
    os.makedirs(a.out_dir, exist_ok=True)
    pieces = []
    for k in range(len(order)):
        m = alpha & (lab == k)
        out = np.zeros_like(org)
        out[m] = org[m]
        pieces.append(out)
    # back piece keeps the front piece's pixels within --overlap of the cut
    for c in range(len(lines)):
        up, lo = c, c + 1
        front, back = (up, lo) if a.front == 'top' else (lo, up)
        fm = alpha & (lab == front)
        d = distance_transform_edt(~(alpha & (lab == back)))
        add = fm & (d <= a.overlap)
        pieces[back][add] = org[add]
        if a.feather > 0:
            # front piece fades out over --feather px past the cut (over the back piece's own pixels, so it looks
            # the same straight); swung, the seam and the outline step blend instead of a hard edge
            bm = alpha & (lab == back)
            df = distance_transform_edt(~fm)
            fade = bm & (df <= a.feather)
            w = np.clip(1 - (df - 0.5) / a.feather, 0, 1)
            pieces[front][fade, :3] = org[fade, :3]
            pieces[front][fade, 3] = (org[fade, 3] * w[fade]).astype(np.uint8)
    for k, nm in enumerate(names):
        pieces[k] = bleed(pieces[k])
        Image.fromarray(pieces[k]).save(os.path.join(a.out_dir, nm + '.png'))
    draw_order = names if a.front == 'top' else names[::-1]
    info = {'layer': os.path.basename(a.layer), 'lined': os.path.basename(a.lined), 'names_top_to_bottom': names,
            'order_front_to_back': draw_order, 'overlap_px': a.overlap,
            'joints': [{'parent': names[c], 'child': names[c + 1], 'pivot': [round(v, 1) for v in pivots[c]]}
                       for c in range(len(lines))],
            'pieces_px': {nm: int((pieces[k][..., 3] > 16).sum()) for k, nm in enumerate(names)},
            'note': 'each child turns around its pivot, together with everything below it'}
    json.dump(info, open(os.path.join(a.out_dir, 'chain.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))
    check(a.out_dir, org, pieces, names, pivots, a.front == 'top', lines)


def pose(pieces, pivots, angles, top_front=True):
    """angles[c] = turn at joint c (degrees, PIL sign); a joint's turn moves every piece below it,
    pivots below move with it"""
    ims = [Image.fromarray(p) for p in pieces]
    piv = [np.array(p, float) for p in pivots]
    for c, ang in enumerate(angles):
        if ang == 0:
            continue
        cen = tuple(piv[c])
        t = np.deg2rad(ang)
        for k in range(c + 1, len(ims)):
            ims[k] = ims[k].rotate(ang, Image.BILINEAR, center=cen)
        for j in range(c + 1, len(piv)):
            r = piv[j] - piv[c]
            piv[j] = piv[c] + np.array([r[0] * np.cos(t) + r[1] * np.sin(t), -r[0] * np.sin(t) + r[1] * np.cos(t)])
    comp = Image.new('RGBA', ims[0].size, (0, 0, 0, 0))
    for im in (ims[::-1] if top_front else ims):
        comp.alpha_composite(im)
    return comp


def check(out_dir, org, pieces, names, pivots, top_front, lines):
    ys, xs = np.nonzero(org[..., 3] > 16)
    pad = 170
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - 20)
    x1, y1 = min(org.shape[1], xs.max() + pad), min(org.shape[0], ys.max() + 40)

    def chk(im):
        im = np.asarray(im)
        h, w = im.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        bg = np.where(((yy // 8 + xx // 8) % 2)[..., None] == 0, 255, 215).astype(np.uint8).repeat(3, 2)
        out = Image.fromarray(bg).convert('RGBA')
        out.alpha_composite(Image.fromarray(im))
        return out.convert('RGB')

    cells = []
    o = chk(org); d = ImageDraw.Draw(o)
    for ln in lines:
        yy, xx = np.nonzero(ln)
        for x, y in zip(xx, yy):
            d.point((x, y), fill=(255, 0, 0))
    for p in pivots:
        d.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], outline=(255, 0, 0), width=2)
    cells.append(('원본 + 선', o))
    tint = [(255, 120, 120), (120, 200, 120), (120, 140, 255), (230, 180, 60)]
    sep = np.zeros_like(org)
    for k, p in enumerate(pieces):
        m = p[..., 3] > 16
        sep[m, :3] = tint[k % 4]; sep[m, 3] = 255
    cells.append(('조각 (' + ' / '.join(names) + ')', chk(sep)))
    nj = len(pivots)
    for t, angs in [('곧게', [0] * nj), ('-10° 씩', [-10] * nj), ('+10° 씩', [10] * nj),
                    ('-20° 씩', [-20] * nj), ('+20° 씩', [20] * nj)]:
        cells.append((t, chk(pose(pieces, pivots, angs, top_front))))
    cw, chh = x1 - x0, y1 - y0
    sheet = Image.new('RGB', (cw * len(cells), chh + 24), 'white')
    dr = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(cells):
        sheet.paste(im.crop((x0, y0, x1, y1)), (i * cw, 24))
        dr.text((i * cw + 4, 3), t, font=FONT, fill='black')
    sheet.save(os.path.join(out_dir, 'chain_check.png'))


if __name__ == '__main__':
    main()
