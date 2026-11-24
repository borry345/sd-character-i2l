"""Same layers from several mix_layers outputs, side by side (each layer alone on a checkerboard).

  env\\Scripts\\python.exe tools\\compare_variants.py --v "A srccolor=seethrough_test/mix/miku_pick2_srccolor" \
      --v "C owner=seethrough_test/mix/miku_pick2_owner" --layers face,legwear --out cmp.png
"""
import argparse
import glob

import numpy as np
from PIL import Image, ImageDraw


def checker(w, h, s=12):
    y, x = np.mgrid[:h, :w]
    c = np.where(((x // s) + (y // s)) % 2 == 0, 255, 215).astype(np.uint8)
    return Image.fromarray(np.stack([c] * 3 + [np.full_like(c, 255)], -1), 'RGBA')


ap = argparse.ArgumentParser()
ap.add_argument('--v', action='append', required=True)
ap.add_argument('--layers', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--cell', type=int, default=330)
a = ap.parse_args()
vs = [v.split('=', 1) for v in a.v]
names = a.layers.split(',')
T = a.cell
im = Image.new('RGB', (T * len(vs), len(names) * (T + 20) + 20), 'white')
dr = ImageDraw.Draw(im)
for j, (lab, _) in enumerate(vs):
    dr.text((j * T + 5, 4), lab, fill=(0, 0, 0))
for i, n in enumerate(names):
    arrs = [np.array(Image.open(glob.glob(f'{d}/layers/*_{n}.png')[0]).convert('RGBA')) for _, d in vs]
    al = np.zeros(arrs[0].shape[:2], bool)
    for x in arrs:
        al |= x[..., 3] > 15
    ys, xs = np.nonzero(al)
    box = (xs.min() - 5, ys.min() - 5, xs.max() + 5, ys.max() + 5)
    for j, x in enumerate(arrs):
        c = Image.fromarray(x).crop(box)
        s = T / max(c.size)
        c = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.NEAREST)
        bg = checker(T, T)
        bg.alpha_composite(c)
        im.paste(bg.convert('RGB'), (j * T, 40 + i * (T + 20)))
    dr.text((5, 24 + i * (T + 20)), n, fill=(0, 0, 200))
im.save(a.out)
print(a.out)
