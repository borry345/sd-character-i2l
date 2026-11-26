"""Which holes does the miku_v2 rig show when it moves?  -> seethrough_test/rig/hole_diag/

Two kinds of hole, both drawn in a pose and counted where they end up VISIBLE (nothing opaque in front):
  A. layer hole  : transparent pixels inside a layer's own outline (closing with a CLOSE_PX disc + fill holes,
                   minus the layer). Drawn magenta at that layer's place in the order, moving with its bone.
  B. open gap    : pixels covered at rest, inside the closed outline of the layers that did NOT move in that pose,
                   that show the background in the pose (e.g. the body behind a raised arm). Drawn orange.
  Only what is NEW compared with the rest pose counts: a hole already visible at rest is in the original
  picture too (e.g. gaps between hair strands that the closing filled).
Poses come from the motion list (walk, sit, kneel, sing, cheer, dragged, sleep is not a pose of the rig).
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_fill_holes

I2L = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(I2L)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_sheet as V  # noqa: E402  (rig, img, world)

OUT = 'seethrough_test/rig/hole_diag'
CLOSE_PX = 15
F = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 18)
F2 = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
POSES = [
    ('기본', {}),
    ('걷기', {'thigh_l': -25, 'shin_l': 30, 'thigh_r': 20, 'upperarm_l': 25, 'upperarm_r': -25, 'forearm_l': 20,
            'tail_left_mid': 8, 'tail_left_tip': 8, 'tail_right_mid': 8, 'tail_right_tip': 8}),
    ('의자에 앉기', {'thigh_l': -80, 'shin_l': 80, 'thigh_r': -80, 'shin_r': 80}),
    ('무릎 꿇기', {'thigh_l': -20, 'shin_l': 110, 'thigh_r': -20, 'shin_r': 110}),
    ('노래 (마이크)', {'upperarm_l': -60, 'forearm_l': -70, 'head': 5}),
    ('환호 (두 팔 위)', {'upperarm_l': -150, 'forearm_l': -20, 'upperarm_r': 150, 'forearm_r': 20}),
    ('들려서 옮겨짐', {'upperarm_l': -40, 'upperarm_r': 40, 'thigh_l': 10, 'thigh_r': -10, 'shin_l': 20, 'shin_r': -20,
                 'tail_left_root': -10, 'tail_left_mid': -15, 'tail_left_tip': -15,
                 'tail_right_root': 10, 'tail_right_mid': 15, 'tail_right_tip': 15}),
    ('머리 기울기 + 트윈테일', {'head': -8, 'tail_left_mid': 15, 'tail_left_tip': 15, 'tail_right_mid': -15,
                       'tail_right_tip': -15}),
]


def warp(a, M, nearest=False):
    if np.allclose(M, np.eye(3)):
        return a
    Mi = np.linalg.inv(M)
    flag = cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR
    return cv2.warpAffine(a, Mi[:2], (a.shape[1], a.shape[0]), flags=flag | cv2.WARP_INVERSE_MAP)


def holes_of(alpha):
    m = alpha > 128
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * CLOSE_PX + 1,) * 2)
    closed = binary_fill_holes(cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool))
    return closed & ~(alpha > 16)


def main():
    os.makedirs(OUT, exist_ok=True)
    L = V.rig['layers_front_to_back']
    alphas = [np.asarray(V.img(l['file']))[..., 3] for l in L]
    holes = [holes_of(a).astype(np.uint8) for a in alphas]
    rest_cover = np.zeros(alphas[0].shape, bool)
    for a in alphas:
        rest_cover |= a > 128
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * CLOSE_PX + 1,) * 2)
    rest_closed = binary_fill_holes(cv2.morphologyEx(rest_cover.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool))
    report = {'close_px': CLOSE_PX, 'layer_holes_at_rest': {l['name']: int(h.sum()) for l, h in zip(L, holes) if h.sum()},
              'poses': {}}
    cells = []
    rest_label = None
    for title, ang in POSES:
        H, W = alphas[0].shape
        label = np.full((H, W), -1, np.int32)  # front-most owner: k = layer k, 1000+k = hole of layer k
        comp = Image.new('RGBA', (W, H), (255, 255, 255, 255))
        for k_ in range(len(L) - 1, -1, -1):  # back to front
            M = V.world(L[k_]['bone'], ang)
            hm = warp(holes[k_], M, nearest=True).astype(bool)
            label[hm] = 1000 + k_
            im = np.asarray(V.img(L[k_]['file']))
            w = warp(im, M)
            label[w[..., 3] > 128] = k_
            if hm.any():
                hole_rgba = np.zeros((H, W, 4), np.uint8)
                hole_rgba[hm] = (255, 0, 255, 255)
                comp.alpha_composite(Image.fromarray(hole_rgba))
            comp.alpha_composite(Image.fromarray(w))
        if rest_label is None:
            rest_label = label.copy()
        # hole visible now that was NOT visible at rest, compared in the layer's own frame (it may have moved)
        new = np.zeros((H, W), bool)
        seen = {}
        for k_ in range(len(L)):
            ys, xs = np.nonzero(label == 1000 + k_)
            if not len(ys):
                continue
            Mi = np.linalg.inv(V.world(L[k_]['bone'], ang))
            q = Mi @ np.stack([xs, ys, np.ones_like(xs)]).astype(float)
            qx = np.clip(np.round(q[0]).astype(int), 0, W - 1)
            qy = np.clip(np.round(q[1]).astype(int), 0, H - 1)
            nn = rest_label[qy, qx] != 1000 + k_
            new[ys[nn], xs[nn]] = True
            if nn.sum():
                seen[L[k_]['name']] = int(nn.sum())
        static = np.zeros((H, W), bool)
        for k_ in range(len(L)):
            if np.allclose(V.world(L[k_]['bone'], ang), np.eye(3)):
                static |= alphas[k_] > 128
        st_closed = binary_fill_holes(cv2.morphologyEx(static.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool))
        gap = rest_cover & st_closed & (label < 0)
        c = np.asarray(comp.convert('RGB')).copy()
        old = (label >= 1000) & ~new
        c[old] = (255, 255, 255)  # holes already visible at rest are not problems: show as background
        c[gap] = (255, 140, 0)
        report['poses'][title] = {'layer_holes_visible': seen, 'open_gap_px': int(gap.sum())}
        cells.append((title, Image.fromarray(c), seen, int(gap.sum())))
        print(title, seen, 'gap', int(gap.sum()))
    json.dump(report, open(f'{OUT}/report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    box = (120, 120, 920, 920)
    cw = 400
    S = Image.new('RGB', (cw * 4, (cw + 90) * 2), 'white')
    d = ImageDraw.Draw(S)
    for i, (t, im, seen, gp) in enumerate(cells):
        x, y = (i % 4) * cw, (i // 4) * (cw + 90)
        S.paste(im.crop(box).resize((cw, cw), Image.LANCZOS), (x, y + 90))
        d.text((x + 6, y + 4), t, font=F, fill='black')
        top = sorted(seen.items(), key=lambda kv: -kv[1])[:3]
        d.text((x + 6, y + 30), '구멍(자홍): ' + (', '.join(f'{k} {v}px' for k, v in top) if top else '없음'), font=F2,
               fill=(170, 0, 170))
        d.text((x + 6, y + 54), f'틈(주황): {gp}px', font=F2, fill=(200, 100, 0))
    S.save(f'{OUT}/poses.png')
    # layer holes at rest, one cell per layer that has any
    hl = [(l['name'], np.asarray(V.img(l['file'])), h) for l, h in zip(L, holes) if h.sum() >= 30]
    if hl:
        cw2 = 220
        S2 = Image.new('RGB', (cw2 * min(6, len(hl)), (cw2 + 30) * ((len(hl) + 5) // 6)), 'white')
        d2 = ImageDraw.Draw(S2)
        for i, (n, im, h) in enumerate(hl):
            ys, xs = np.nonzero((im[..., 3] > 16) | h.astype(bool))
            b = (max(xs.min() - 10, 0), max(ys.min() - 10, 0), min(xs.max() + 10, 1024), min(ys.max() + 10, 1024))
            bg = Image.new('RGBA', (1024, 1024), (255, 255, 255, 255))
            hm = np.zeros((1024, 1024, 4), np.uint8)
            hm[h.astype(bool)] = (255, 0, 255, 255)
            bg.alpha_composite(Image.fromarray(hm))
            bg.alpha_composite(Image.fromarray(im))
            c = bg.crop(b)
            c.thumbnail((cw2, cw2))
            x, y = (i % 6) * cw2, (i // 6) * (cw2 + 30)
            S2.paste(c.convert('RGB'), (x, y + 30))
            d2.text((x + 4, y + 4), f'{n} {int(h.sum())}px', font=F2, fill='black')
        S2.save(f'{OUT}/layer_holes.png')


if __name__ == '__main__':
    main()
