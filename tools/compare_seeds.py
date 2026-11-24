"""Side-by-side sheet of the same See-through tag layers from several runs (seeds / PCs).

Rows = tags that are non-empty in at least one run, columns = runs. Each cell is the layer on a
checkerboard, cropped to the union box of that tag over all runs, with its pixel count.

  env\\Scripts\\python.exe tools\\compare_seeds.py --out seethrough_test\\seed_compare.png \
      --run old42=seethrough_test\\miku_chibi_sprite --run new42=seethrough_test\\miku_tblr \
      --run new0=seethrough_test\\miku_seed0
"""
import argparse
import os
import os.path as osp

import numpy as np
from PIL import Image, ImageDraw

TAGS = ['front hair', 'back hair', 'head', 'neck', 'neckwear', 'topwear', 'handwear', 'bottomwear',
        'legwear', 'footwear', 'tail', 'wings', 'objects',
        'headwear', 'face', 'irides', 'eyebrow', 'eyewhite', 'eyelash', 'eyewear', 'ears', 'earwear',
        'nose', 'mouth']


def mid_dir(run):
    psds = [f for f in os.listdir(run) if f.endswith('.psd') and not f.endswith('_depth.psd')]
    return osp.join(run, psds[0][:-4])


def checker(size, s=12):
    w, h = size
    y, x = np.mgrid[:h, :w]
    c = np.where(((x // s) + (y // s)) % 2 == 0, 255, 225).astype(np.uint8)
    return Image.fromarray(np.stack([c] * 3 + [np.full_like(c, 255)], -1), 'RGBA')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='append', required=True, help='label=run_dir')
    ap.add_argument('--out', required=True)
    ap.add_argument('--cell', type=int, default=220)
    a = ap.parse_args()
    runs = [(s.partition('=')[0], mid_dir(s.partition('=')[2])) for s in a.run]
    T, H0, L = a.cell, 18, 90
    rows = []
    for t in TAGS:
        ims = []
        for _, m in runs:
            p = osp.join(m, f'{t}.png')
            ims.append(np.array(Image.open(p).convert('RGBA')) if osp.exists(p) else None)
        alphas = [im[..., 3] > 15 for im in ims if im is not None]
        if not alphas or not any(x.any() for x in alphas):
            continue
        u = np.any(np.stack(alphas), 0)
        ys, xs = np.nonzero(u)
        cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
        s = max(xs.max() - xs.min(), ys.max() - ys.min()) // 2 + 12
        rows.append((t, ims, (cx - s, cy - s, cx + s, cy + s)))
    W = Image.new('RGB', (L + len(runs) * T, H0 + len(rows) * (T + H0)), (255, 255, 255))
    d = ImageDraw.Draw(W)
    for j, (lab, _) in enumerate(runs):
        d.text((L + j * T + 4, 3), lab, fill=(0, 0, 200))
    for i, (t, ims, box) in enumerate(rows):
        y = H0 + i * (T + H0)
        d.text((4, y + T // 2), t, fill=(0, 0, 0))
        for j, im in enumerate(ims):
            x = L + j * T
            px = 0 if im is None else int((im[..., 3] > 15).sum())
            d.text((x + 4, y + 3), f'{px:,}px', fill=(200, 0, 0) if px == 0 else (0, 0, 0))
            cell = checker((T, T))
            if im is not None:
                cell.alpha_composite(Image.fromarray(im).crop(box).resize((T, T)))
            W.paste(cell.convert('RGB'), (x, y + H0))
            d.rectangle([x, y + H0, x + T - 1, y + H0 + T - 1], outline=(180, 180, 180))
    W.save(a.out)
    print('saved', a.out, f'{len(rows)} tags x {len(runs)} runs')


if __name__ == '__main__':
    main()
