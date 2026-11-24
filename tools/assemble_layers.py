"""Assemble final layers at the original image size.

  python assemble_layers.py --src original.png --out dir --layer front_hair=a.png --layer face=b.png ...
  (layers listed front-most first; each is a full 1024x1024 See-through-space PNG)

  1. Undo See-through's centre-pad + resize (1024 square -> original size).
  2. Wherever a layer is the top-most opaque layer, its pixels are replaced with the original's,
     so visible colours match the input exactly; hidden/generated parts stay as they are.
  3. Writes NN_name.png, layers.psd (bottom = last layer) and visible_owner.png (who owns each pixel).
"""
import argparse
import os

import numpy as np
from PIL import Image

COLORS = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180), (70, 240, 240)]


def unpad(layer, W, H):
    sz = max(W, H)
    px, py = (sz - W) // 2, (sz - H) // 2
    big = Image.fromarray(layer).resize((sz, sz), Image.LANCZOS)
    return np.asarray(big)[py:py + H, px:px + W].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--layer', action='append', required=True, help='name=path, front-most first')
    # Low on purpose: the soft edge of an upper layer (its line art) belongs to that layer, so it
    # takes those original pixels and the layer below keeps its own clean pixels there.
    ap.add_argument('--alpha_thr', type=int, default=16)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    src = np.asarray(Image.open(a.src).convert('RGBA'))
    H, W = src.shape[:2]
    names, layers = [], []
    for spec in a.layer:
        n, _, p = spec.partition('=')
        lay = np.asarray(Image.open(p).convert('RGBA'))
        if lay.shape[:2] != (H, W):
            lay = unpad(lay, W, H)
        names.append(n)
        layers.append(lay.copy())

    # nothing may stick out of the original silhouette (it would show in the composite);
    # hidden/generated parts always sit under another layer, i.e. inside the silhouette
    src_on = src[..., 3] > 0
    for lay in layers:
        lay[~src_on, 3] = 0

    # top-most opaque layer per pixel
    owner = np.full((H, W), -1, np.int32)
    for i, lay in enumerate(layers):
        owner[(owner == -1) & (lay[..., 3] >= a.alpha_thr)] = i
    uncovered = src_on & (owner == -1)
    print(f'[check] original pixels no layer covered before the fix: {int(uncovered.sum())}')
    if uncovered.any() and (owner >= 0).any():  # give them to the nearest layer
        from scipy.ndimage import distance_transform_edt
        _, (iy, ix) = distance_transform_edt(owner < 0, return_indices=True)
        owner[uncovered] = owner[iy[uncovered], ix[uncovered]]
    for i, lay in enumerate(layers):
        vis = (owner == i) & src_on
        lay[vis, :3] = src[vis, :3]
        lay[vis, 3] = src[vis, 3]
        print(f'[layer] {i:02d} {names[i]:11s} opaque {int((lay[..., 3] >= a.alpha_thr).sum()):7d}px  '
              f'visible (from original) {int(vis.sum()):7d}px')
        Image.fromarray(lay).save(os.path.join(a.out, f'{i:02d}_{names[i]}.png'))
    vis_img = np.full((H, W, 3), 255, np.uint8)
    for i in range(len(layers)):
        vis_img[owner == i] = COLORS[i % len(COLORS)]
    vis_img[uncovered] = (0, 0, 0)
    Image.fromarray(vis_img).save(os.path.join(a.out, 'visible_owner.png'))

    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new('RGBA', (W, H))
    for i in reversed(range(len(layers))):
        psd.append(PixelLayer.frompil(Image.fromarray(layers[i]), psd, names[i]))
    psd.save(os.path.join(a.out, 'layers.psd'))
    print('[psd] written')


if __name__ == '__main__':
    main()
