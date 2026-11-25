"""final/miku_v2 preview: poses (bones from rig.json), expressions, hand shapes -> final/miku_v2/sheet.png"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

I2L = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(I2L)
D = 'final/miku_v2'
rig = json.load(open(f'{D}/rig.json', encoding='utf-8'))
F = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 20)
CACHE = {}


def img(p):
    if p not in CACHE:
        CACHE[p] = Image.open(f'{D}/{p}').convert('RGBA')
    return CACHE[p]


def rot(deg, c):
    """matrix of a turn by deg (PIL sign: + = counter-clockwise on screen) around c, on [x, y, 1]"""
    t = np.deg2rad(deg)
    co, si = np.cos(t), np.sin(t)
    R = np.array([[co, si, 0], [-si, co, 0], [0, 0, 1]])
    T = np.array([[1, 0, c[0]], [0, 1, c[1]], [0, 0, 1]])
    Ti = np.array([[1, 0, -c[0]], [0, 1, -c[1]], [0, 0, 1]])
    return T @ R @ Ti


def world(bone, angles):
    b = rig['bones'][bone]
    M = rot(angles.get(bone, 0), b['pivot'])
    return M if b['parent'] is None else world(b['parent'], angles) @ M


def render(angles=None, swap=None, hide=()):
    angles, swap = angles or {}, swap or {}
    out = Image.new('RGBA', tuple(rig['canvas']), (255, 255, 255, 255))
    for L in reversed(rig['layers_front_to_back']):
        n = L['name']
        if n in hide:
            continue
        p = swap.get(n, L['file'])
        if p is None:
            continue
        im = img(p)
        M = world(L['bone'], angles)
        if not np.allclose(M, np.eye(3)):
            Mi = np.linalg.inv(M)
            im = im.transform(im.size, Image.AFFINE, tuple(Mi[:2].ravel()), resample=Image.BILINEAR)
        out.alpha_composite(im)
    return out


def expr_swap(e):
    parts = rig['slots']['face']['swap'][e]
    sw = {k: parts.get(k) for k in rig['slots']['face']['layers']}
    return sw, [k for k in parts if k not in sw]  # extras: blush, sweat


def render_expr(e):
    sw, extra = expr_swap(e)
    im = render(swap=sw)
    if extra:  # blush / sweat right in front of the face: redraw everything in front of the face on top
        base = Image.new('RGBA', im.size, (255, 255, 255, 255))
        order = rig['layers_front_to_back']
        fi = [L['name'] for L in order].index('face')
        for L in reversed(order):
            p = sw.get(L['name'], L['file']) if L['name'] in sw else L['file']
            if p is None:
                continue
            base.alpha_composite(img(p))
            if L['name'] == 'face':
                for k in extra:
                    base.alpha_composite(img(rig['slots']['face']['swap'][e][k]))
        im = base
        _ = fi
    return im


def main():
    rows = []
    poses = [('기본 (v1과 같음)', {}),
             ('걷기 느낌', {'thigh_l': -20, 'shin_l': 25, 'thigh_r': 15, 'upperarm_l': 20, 'upperarm_r': -20,
                        'forearm_l': 20, 'tail_left_mid': 6, 'tail_left_tip': 6, 'tail_right_mid': 6, 'tail_right_tip': 6}),
             ('팔 들기 + 무릎', {'upperarm_l': -70, 'forearm_l': -30, 'upperarm_r': 60, 'shin_l': 40, 'shin_r': -30}),
             ('머리 기울기 + 트윈테일', {'head': 6, 'tail_left_mid': -10, 'tail_left_tip': -10, 'tail_right_mid': 10,
                                'tail_right_tip': 10})]
    cells = [(t, render(a)) for t, a in poses]
    rows.append(('자세 (rig.json 뼈)', cells, (150, 150, 900, 840)))
    rows.append(('표정 (face 슬롯)', [(e, render_expr(e)) for e in ['calm', 'smile', 'ah', 'ee', 'oh', 'surprised', 'sleeping']],
                 (380, 240, 680, 470)))
    hs = rig['slots']['hand_l']['swap']
    hr = rig['slots']['hand_r']['swap']
    hc = []
    for h in ['default', 'fist', 'open', 'mic', 'peace', 'relax', 'point']:
        sw = {}
        if h in hs:
            sw['hand_l'] = hs[h]
        if h in hr:
            sw['hand_r'] = hr[h]
        hc.append((h, render(swap=sw)))
    rows.append(('손 (hand 슬롯)', hc, (370, 560, 720, 720)))
    tw = rig['slots']['tails']['whole']
    sw = {f'tail_{s}_{k}': None for s in ('left', 'right') for k in ('root', 'mid', 'tip')}
    tl = render(swap=sw)
    for s in ('right', 'left'):
        pass
    whole = Image.new('RGBA', tl.size, (255, 255, 255, 255))
    for L in reversed(rig['layers_front_to_back']):
        n = L['name']
        if n.startswith('tail_'):
            if n.endswith('_root'):
                whole.alpha_composite(img(tw['left' if 'left' in n else 'right']))
            continue
        whole.alpha_composite(img(L['file']))
    rows.append(('트윈테일', [('3조각 (기본)', render()), ('안 자른 버전', whole)], (150, 150, 900, 840)))

    H = 0
    W = 0
    layout = []
    for title, cells, box in rows:
        cw = box[2] - box[0]
        sc = min(1.0, 1400 / (cw * len(cells))) if len(cells) > 4 else min(1.0, 1400 / (cw * len(cells)))
        w = int(cw * sc)
        h = int((box[3] - box[1]) * sc)
        layout.append((title, cells, box, w, h))
        W = max(W, w * len(cells))
        H += h + 60
    S = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(S)
    y = 0
    for title, cells, box, w, h in layout:
        d.text((6, y + 4), title, font=F, fill='black')
        for i, (t, im) in enumerate(cells):
            S.paste(im.crop(box).convert('RGB').resize((w, h), Image.LANCZOS), (i * w, y + 56))
            d.text((i * w + 6, y + 30), t, font=F, fill=(60, 60, 60))
        y += h + 60
    S.save(f'{D}/sheet.png')
    print(S.size)


if __name__ == '__main__':
    main()
