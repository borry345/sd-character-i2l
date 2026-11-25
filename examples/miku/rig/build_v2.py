"""miku_v1 + rig pieces -> final/miku_v2 (layers, variants, rig.json, PSD, composite, sheet).

  env\\Scripts\\python.exe seethrough_test\\rig\\build_v2.py

Default pose = v1 picture (composite must equal v1 except where pieces were remade: bare arm under the sleeve,
cloth-only sleeves). v1 layers replaced: handwear-l/r -> 7 arm layers each, eyes/mouth -> l/r parts,
legwear-l/r -> thigh/shin/joint_line, tail_left/right -> root/mid/tip (split3).
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

I2L = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(I2L)
sys.path.insert(0, 'tools')
from split_chain import pose as chain_pose  # noqa: E402,F401

V1 = 'final/miku_v1/layers'
R = 'seethrough_test/rig'
OUT = 'final/miku_v2'
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 18)
EXPR = ['calm', 'smile', 'ah', 'ee', 'oh', 'surprised', 'sleeping']
HANDS = ['default', 'fist', 'open', 'mic', 'peace', 'relax', 'point']
EYE_SPLIT = 540


def A(p):
    return np.asarray(Image.open(p).convert('RGBA'))


def split_lr(img):
    l, r = img.copy(), img.copy()
    l[:, EYE_SPLIT:] = 0
    r[:, :EYE_SPLIT] = 0
    return l, r


def arm(s):
    a = f'{R}/arms/final/{s}'
    return [(f'cloth_lower_{s}', f'{a}/cloth/cloth_lower_{s}.png', f'forearm_{s}'),
            (f'cloth_upper_{s}', f'{a}/cloth/cloth_upper_{s}.png', f'upperarm_{s}'),
            (f'cloth_lower_{s}_joint_line', f'{a}/cloth/cloth_lower_{s}_joint_line.png', f'forearm_{s}'),
            (f'hand_{s}', f'{a}/hand/hand_{s}.png', f'forearm_{s}'),
            (f'forearm_{s}', f'{a}/hand/forearm2_{s}.png', f'forearm_{s}'),
            (f'upperarm_{s}', f'{a}/arm/upperarm_{s}.png', f'upperarm_{s}'),
            (f'forearm_{s}_joint_line', f'{a}/arm/forearm_{s}_joint_line.png', f'forearm_{s}')]


def leg(s):
    d = f'{R}/legs/legwear-{s}'
    return [(f'shin_{s}', f'{d}/shin_{s}.png', f'shin_{s}'), (f'thigh_{s}', f'{d}/thigh_{s}.png', f'thigh_{s}'),
            (f'shin_{s}_joint_line', f'{d}/shin_{s}_joint_line.png', f'shin_{s}')]


def tail(s):
    d = f'{R}/tails/split3/{s}'
    return [(f'tail_{s}_{k}', f'{d}/tail_{s}_{k}.png', f'tail_{s}_{k}') for k in ('root', 'mid', 'tip')]


def main():
    v1 = sorted(os.listdir(V1))
    layers = []  # front to back: (name, array, bone)
    for f in v1:
        nm = f[3:-4]
        p = f'{V1}/{f}'
        if nm == 'handwear-l':
            layers += [(n, A(q), b) for n, q, b in arm('l')]
        elif nm == 'handwear-r':
            layers += [(n, A(q), b) for n, q, b in arm('r')]
        elif nm in ('eyelash', 'irides', 'eyewhite', 'eyebrow'):
            l, r = split_lr(A(p))  # v1 alpha (cleaned) split at the eye column
            layers += [(f'{nm}_l', l, 'head'), (f'{nm}_r', r, 'head')]
        elif nm == 'legwear-l':
            layers += [(n, A(q), b) for n, q, b in leg('l')]
        elif nm == 'legwear-r':
            layers += [(n, A(q), b) for n, q, b in leg('r')]
        elif nm == 'tail_left':
            layers += [(n, A(q), b) for n, q, b in tail('left')]
        elif nm == 'tail_right':
            layers += [(n, A(q), b) for n, q, b in tail('right')]
        else:
            bone = 'head' if nm in ('front_hair', 'mouth', 'face', 'back_center') or nm.startswith('headwear') else 'body'
            layers.append((nm, A(p), bone))
        if nm == 'face':  # expression-only extras go right in front of the face
            pass
    H, W = layers[0][1].shape[:2]

    # pivots
    def top_c(img, down=10):
        ys, xs = np.nonzero(img[..., 3] > 16)
        m = ys < ys.min() + 12
        return [round(float(xs[m].mean()), 1), int(ys.min() + down)]
    L = {n: a for n, a, _ in layers}
    arms_rig = json.load(open(f'{R}/arms/final/arms_rig.json'))
    fy, fx = np.nonzero(L['face'][..., 3] > 16)
    bones = {
        'body': {'parent': None, 'pivot': [512, 640], 'from': 'chosen by hand (rough hip height, centre of the picture)', 'note': 'root (hips); whole character'},
        'head': {'parent': 'body', 'pivot': [round(float(fx[fy > fy.max() - 6].mean()), 1), int(fy.max())],
                 'from': 'estimated: centre of the lowest 6 rows of the face layer',
                 'note': 'neck (bottom of face). Small tilts only: the neck was not lengthened (user: skip neck work)'},
        'upperarm_l': {'parent': 'body', 'pivot': [488.3, 480], 'from': 'estimated: centre of the top 12 rows of upperarm_l, about 10px down'},
        'forearm_l': {'parent': 'upperarm_l', 'pivot': arms_rig['l']['elbow_pivot'], 'from': 'elbow line drawn by the person (middle of the line inside the arm)'},
        'upperarm_r': {'parent': 'body', 'pivot': [565, 480], 'from': 'estimated: centre of the top rows of upperarm_r (also used to raise the arm for the pointing hand)'},
        'forearm_r': {'parent': 'upperarm_r', 'pivot': arms_rig['r']['elbow_pivot'], 'from': 'elbow line drawn by the person (middle of the line inside the arm)'},
    }
    for s in ('l', 'r'):
        j = json.load(open(f'{R}/legs/legwear-{s}/joint.json'))
        bones[f'thigh_{s}'] = {'parent': 'body', 'pivot': top_c(L[f'thigh_{s}']), 'from': 'estimated: centre of the top 12 rows of the thigh, 10px down'}
        bones[f'shin_{s}'] = {'parent': f'thigh_{s}', 'pivot': j['pivot'], 'from': 'knee line drawn by the person (middle of the line inside the leg)'}
    for s in ('left', 'right'):
        c = json.load(open(f'{R}/tails/split3/{s}/chain.json'))
        bones[f'tail_{s}_root'] = {'parent': 'head', 'pivot': top_c(L[f'tail_{s}_root'], 6), 'from': 'estimated: centre of the top rows of the tail'}
        bones[f'tail_{s}_mid'] = {'parent': f'tail_{s}_root', 'pivot': c['joints'][0]['pivot'], 'from': 'V line drawn by the person (middle of its two ends)'}
        bones[f'tail_{s}_tip'] = {'parent': f'tail_{s}_mid', 'pivot': c['joints'][1]['pivot'], 'from': 'V line drawn by the person (middle of its two ends)'}

    # write
    keep = {}
    for f in ('README.md',):  # hand-written files in OUT survive a rebuild
        if os.path.exists(f'{OUT}/{f}'):
            keep[f] = open(f'{OUT}/{f}', 'rb').read()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(f'{OUT}/layers')
    for f, b in keep.items():
        open(f'{OUT}/{f}', 'wb').write(b)
    names = []
    for i, (n, a, b) in enumerate(layers):
        fn = f'{i:02d}_{n}.png'
        Image.fromarray(a).save(f'{OUT}/layers/{fn}')
        names.append({'name': n, 'file': f'layers/{fn}', 'bone': b})
    # variants
    var = {'expressions': {}, 'hands': {'l': {}, 'r': {}}, 'tails_whole': {}}
    for e in EXPR:
        d = f'{OUT}/variants/expressions/{e}'
        os.makedirs(d)
        parts = {}
        for f in sorted(os.listdir(f'{R}/face/{e}')):
            a = A(f'{R}/face/{e}/{f}').copy()
            a[a[..., 3] <= 15] = 0  # same clean-up as v1 (alpha <= 15 removed)
            Image.fromarray(a).save(f'{d}/{f}')
            parts[f[:-4]] = f'variants/expressions/{e}/{f}'
        var['expressions'][e] = parts
    for s in ('l', 'r'):
        d = f'{OUT}/variants/hands/{s}'
        os.makedirs(d)
        for h in HANDS:
            src = f'{R}/arms/final/{s}/hands/hand_{h}_{s}.png'
            if os.path.exists(src):
                shutil.copy(src, f'{d}/hand_{h}_{s}.png')
                var['hands'][s][h] = f'variants/hands/{s}/hand_{h}_{s}.png'
    os.makedirs(f'{OUT}/variants/tails_whole')
    for s, i in (('left', 14), ('right', 18)):
        shutil.copy(f'{R}/tails/whole/tail_{s}.png', f'{OUT}/variants/tails_whole/tail_{s}.png')
        var['tails_whole'][s] = f'variants/tails_whole/tail_{s}.png'
    os.makedirs(f'{OUT}/effects', exist_ok=True)
    shutil.copy('effects/sweat_drop/sweat_drop.png', f'{OUT}/effects/sweat_drop.png')

    rig = {
        'canvas': [W, H], 'view': 'side view facing left only; facing right = mirror the whole rig horizontally',
        'l_r': 'l/r and left/right = viewer side (image left / image right)',
        'layers_front_to_back': names, 'bones': bones,
        'slots': {
            'hand_l': {'layer': 'hand_l', 'swap': var['hands']['l'],
                       'note': 'hands are swapped, not rotated; all cut at the same wrist line (mic_r = fist, no mic)'},
            'hand_r': {'layer': 'hand_r', 'swap': var['hands']['r']},
            'face': {'layers': ['eyelash_l', 'eyelash_r', 'irides_l', 'irides_r', 'eyewhite_l', 'eyewhite_r',
                                'eyebrow_l', 'eyebrow_r', 'mouth'],
                     'swap': var['expressions'],
                     'note': 'replace these layers with the expression set; a part missing in a set (e.g. irides in calm, '
                             'closed eyes) = hide it. blush (smile) and sweat (surprised): draw right in front of face'},
            'tails': {'default': 'split3 (root/mid/tip)', 'whole': var['tails_whole'],
                      'note': 'whole = one piece per tail; use instead of the 3 tail_* layers (same place in the order)'},
        },
        'joint_lines': 'a *_joint_line layer moves with its bone but is drawn behind the piece above it (see order)',
        'sources': {'v1': 'final/miku_v1', 'arms': f'{R}/arms/final/arms_rig.json', 'legs': f'{R}/legs',
                    'face': f'{R}/face/face_parts.json', 'tails': f'{R}/tails/README.md'},
    }
    json.dump(rig, open(f'{OUT}/rig.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    comp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for n, a, b in reversed(layers):
        comp.alpha_composite(Image.fromarray(a))
    comp.save(f'{OUT}/composite.png')
    write_psd(layers, var, W, H)
    compare_v1(comp)
    print(f'{len(layers)} layers, bones {len(bones)} -> {OUT}')


def write_psd(layers, var, W, H):
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer
    psd = PSDImage.new('RGBA', (W, H))
    # variants first (bottom), hidden
    vg = Group.new(psd, 'variants (hidden)', open_folder=False)
    for e, parts in var['expressions'].items():
        g = Group.new(vg, f'expr_{e}', open_folder=False)
        for k, p in parts.items():
            g.append(PixelLayer.frompil(Image.open(f'{OUT}/{p}'), psd, k))
        g.visible = False
    for s in ('l', 'r'):
        g = Group.new(vg, f'hands_{s}', open_folder=False)
        for h, p in var['hands'][s].items():
            g.append(PixelLayer.frompil(Image.open(f'{OUT}/{p}'), psd, f'hand_{h}_{s}'))
        g.visible = False
    g = Group.new(vg, 'tails_whole', open_folder=False)
    for s, p in var['tails_whole'].items():
        g.append(PixelLayer.frompil(Image.open(f'{OUT}/{p}'), psd, f'tail_{s}'))
    g.visible = False
    vg.visible = False
    for n, a, b in reversed(layers):  # psd: bottom first
        psd.append(PixelLayer.frompil(Image.fromarray(a), psd, n))
    psd.save(f'{OUT}/miku_v2.psd')


def compare_v1(comp):
    v1 = A('final/miku_v1/composite.png').astype(int)
    c = np.asarray(comp).astype(int)
    if v1.shape[2] == 3:
        v1 = np.dstack([v1, np.full(v1.shape[:2], 255)])
    d = np.abs(c - v1).max(2)
    diff = d > 24
    ys, xs = np.nonzero(diff)
    info = {'pixels_diff_gt24': int(diff.sum()),
            'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if diff.any() else None}
    json.dump(info, open(f'{OUT}/v1_diff.json', 'w'), indent=1)
    vis = (np.asarray(Image.open('final/miku_v1/composite.png').convert('RGB')) * 0.35 + 165).astype(np.uint8)
    vis[diff] = (255, 0, 0)
    Image.fromarray(vis).save(f'{OUT}/v1_diff.png')
    print('v1 diff', info)


if __name__ == '__main__':
    main()
