"""Count marks (other parts' lines, colour seams) per layer of mix_layers outputs and draw them.

mark = an edge inside the layer (>= 3px from its border) that the layer's own generated version does not
have within 2px (mix_layers.extra_edges). Reference = <mix>/gen/ (written by mix_layers), or --gen <dir>
(e.g. the clean variant's layers for an old output without gen/).

  env\\Scripts\\python.exe tools\\layer_marks.py --v "A=seethrough_test/mix/miku_pick2_srccolor:seethrough_test/mix/miku_pick2_clean/layers" \
      --v "C=seethrough_test/mix/miku_pick2_owner" --base A --out marks.png
Prints a table (px per layer, % of --base) and saves marks.png (rows = variants, red = marks).
"""
import argparse
import glob
import os
import os.path as osp
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, osp.dirname(osp.abspath(__file__)))
from mix_layers import extra_edges  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--v', action='append', required=True, help='label=mixdir[:gendir]')
ap.add_argument('--base', default=None)
ap.add_argument('--out', required=True)
ap.add_argument('--cell', type=int, default=180)
a = ap.parse_args()

res = {}
names = None
for v in a.v:
    lab, rest = v.split('=', 1)
    d, g = rest.split(':', 1) if ':' in rest else (rest, None)  # relative paths only
    g = g or osp.join(d, 'gen')
    files = sorted(glob.glob(osp.join(d, 'layers', '*.png')))
    names = names or [osp.basename(f)[3:-4] for f in files]
    res[lab] = {}
    # part boundaries of the composite: front-most layer with alpha >= 128 per pixel; a pixel whose 7x7
    # neighbourhood shows another part is near a boundary. Only lines there count (the original's own
    # strokes inside a part, e.g. hair strands, are its content, not another part's line).
    lay = [np.array(Image.open(f).convert('RGBA')) for f in files]
    vis_owner = np.full(lay[0].shape[:2], -1, np.int32)
    for k in range(len(lay) - 1, -1, -1):
        if names[k] != 'neck':
            vis_owner[lay[k][..., 3] >= 128] = k
    mx = cv2.dilate(vis_owner.astype(np.float32), np.ones((7, 7), np.uint8))
    mn = -cv2.dilate(-vis_owner.astype(np.float32), np.ones((7, 7), np.uint8))
    near_bd = (mx != mn)
    for n in names:
        im = np.array(Image.open(glob.glob(osp.join(d, 'layers', f'*_{n}.png'))[0]).convert('RGBA'))
        gen = np.array(Image.open(glob.glob(osp.join(g, f'*_{n}.png'))[0]).convert('RGBA'))
        c, m = extra_edges({'img': im, 'gen': gen})
        # line = a mark where the layer is darker than its generated version by > 40 (within 1px):
        # another part's outline stamped on. The rest = colour seam (two colourings meeting).
        lum = lambda x: (x[..., :3].astype(float) * (x[..., 3:] / 255) + 255 * (1 - x[..., 3:] / 255)) @ [0.299, 0.587, 0.114]
        inner = cv2.erode(((im[..., 3] > 128) & (gen[..., 3] > 128)).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        dark = (lum(gen) - lum(im)) > 40  # this pixel itself got darker than generated
        ml = dark & inner & near_bd  # stamped line pixels
        m = m & ~cv2.dilate(ml.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)  # seams = other new edges
        res[lab][n] = (int(ml.sum()), int((m & ~ml).sum()), ml, m & ~ml, im)

labs = list(res)
base = a.base or labs[0]
for t, ti in (('LINES (dark, other parts)', 0), ('SEAMS (colour)', 1)):
    print(f'== {t}')
    print('layer'.ljust(14) + ''.join(l.rjust(9) for l in labs))
    for n in names:
        print(n.ljust(14) + ''.join(str(res[l][n][ti]).rjust(9) for l in labs))
    tot = {l: sum(res[l][n][ti] for n in names if n != 'neck') for l in labs}
    print('TOTAL'.ljust(14) + ''.join(str(tot[l]).rjust(9) for l in labs))
    print(('% of ' + base).ljust(14) + ''.join(f'{100 * tot[l] / max(tot[base], 1):8.0f}%' for l in labs))
tot = {l: (sum(res[l][n][0] for n in names if n != 'neck'), sum(res[l][n][1] for n in names if n != 'neck')) for l in labs}

show = [n for n in names if n != 'neck']
T = a.cell
sheet = Image.new('RGB', (T * len(show) + 60, (T + 16) * len(labs) + 16), 'white')
dr = ImageDraw.Draw(sheet)
for j, n in enumerate(show):
    dr.text((60 + j * T + 3, 2), n, fill=(0, 0, 0))
for i, l in enumerate(labs):
    dr.text((3, 16 + i * (T + 16) + T // 2), f'{l}\nL {tot[l][0]}\nS {tot[l][1]}', fill=(0, 0, 0))
    for j, n in enumerate(show):
        cl, cs, ml, ms, im = res[l][n]
        al = np.zeros(im.shape[:2], bool)
        for l2 in labs:
            al |= res[l2][n][4][..., 3] > 15
        ys, xs = np.nonzero(al)
        cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
        s = max(xs.max() - xs.min(), ys.max() - ys.min()) // 2 + 6
        v = im.astype(float)
        w = v[..., :3] * (v[..., 3:] / 255) + 235 * (1 - v[..., 3:] / 255)
        w = (w * 0.55 + 255 * 0.45)
        k3 = np.ones((3, 3), np.uint8)
        w[cv2.dilate(ms.astype(np.uint8), k3) > 0] = (255, 170, 0)
        w[cv2.dilate(ml.astype(np.uint8), k3) > 0] = (230, 0, 0)
        cell = Image.fromarray(w.astype(np.uint8)).crop((cx - s, cy - s, cx + s, cy + s)).resize((T, T), Image.BILINEAR)
        sheet.paste(cell, (60 + j * T, 16 + i * (T + 16)))
        dr.text((60 + j * T + 3, 16 + i * (T + 16) + T + 1), f'L{cl} S{cs}', fill=(200, 0, 0))
sheet.save(a.out)
print(a.out)
