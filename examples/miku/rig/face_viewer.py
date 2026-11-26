"""Face check page: swap expression parts quickly on the miku_v2 layers -> seethrough_test/rig/face_viewer/index.html

One self-contained HTML file (images inlined as PNG data URLs, cropped to the face area), opens offline in a browser.
  - base layers   : final/miku_v2/rig.json layers_front_to_back (default expression = v1 parts)
  - expressions   : seethrough_test/rig/face_v2/<expr>/ (face_parts.py output: eyes l/r, eyebrows, mouth,
                    marks blush / sweat / tears)
  - input pictures: each run's src_img.png (same 1024 page), to compare with the input
Each part group (eyes, eyebrows, mouth, marks) can take a different expression, left/right eyes too.
"""
import base64
import io
import json
import os

from PIL import Image

I2L = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(I2L)
V2 = 'final/miku_v2'
FACE = 'seethrough_test/rig/face_v2'
OUT = 'seethrough_test/rig/face_viewer/index.html'
BOX = (330, 150, 730, 530)  # face + hair around it, on the 1024 page
EXPR = [('calm', '평온'), ('smile', '웃음'), ('ah', '아'), ('ee', '이'), ('oh', '오'), ('surprised', '놀람'),
        ('sleeping', '잠'), ('pet', '쓰다듬'), ('crying', '울음'), ('question', '물음표'), ('angry', '화남')]
RUN = {e: f'seethrough_test/expr/{e}_seed1/miku_chibi_{e}' for e, _ in EXPR}
RUN['base'] = 'seethrough_test/miku_grow_seed1/miku_chibi_sprite'
PARTS = ['eyelash_l', 'eyelash_r', 'irides_l', 'irides_r', 'eyewhite_l', 'eyewhite_r', 'eyebrow_l', 'eyebrow_r',
         'mouth', 'blush', 'sweat', 'tears', 'anger']


def uri(path, white=False):
    im = Image.open(path).convert('RGBA').crop(BOX)
    if not white and im.getchannel('A').getbbox() is None:
        return None
    if white:
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg.convert('RGB')
    b = io.BytesIO()
    im.save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


def main():
    rig = json.load(open(f'{V2}/rig.json', encoding='utf-8'))
    layers = []
    for L in rig['layers_front_to_back']:
        u = uri(f"{V2}/{L['file']}")
        layers.append({'name': L['name'], 'src': u})
    sets = {'base': {'label': '기본 (v1)', 'parts': {p: next((l['src'] for l in layers if l['name'] == p), None)
                                                    for p in PARTS}, 'input': uri(f"{RUN['base']}/src_img.png", True)}}
    for e, ko in EXPR:
        d = f'{FACE}/{e}'
        if not os.path.isdir(d):
            continue
        parts = {p: (uri(f'{d}/{p}.png') if os.path.exists(f'{d}/{p}.png') else None) for p in PARTS}
        sets[e] = {'label': ko, 'parts': parts, 'input': uri(f'{RUN[e]}/src_img.png', True)}
    # parts the user does not use: leave them out, a whole set borrows that part from another expression
    ex = json.load(open(f'{FACE}/exclude.json', encoding='utf-8')) if os.path.exists(f'{FACE}/exclude.json') else {}
    groups = {'eyes': [f'{t}_{s}' for t in ('eyelash', 'irides', 'eyewhite') for s in 'lr'],
              'eyebrows': ['eyebrow_l', 'eyebrow_r'], 'mouth': ['mouth']}
    for g, m in ex.items():
        if g not in groups:
            continue
        for e, use in m.items():
            if e not in sets:
                continue
            for p in groups[g]:
                sets[e]['parts'][p] = sets[use]['parts'][p]
                sets[e].setdefault('borrowed', {})[p] = use
    # where each part is (union over all sets), in crop coordinates: thumbnails in the side list zoom to it
    pbox = {}
    for p in PARTS:
        bb = None
        files = {l['name']: l['file'] for l in rig['layers_front_to_back']}
        for e in sets:
            if e == 'base' and p not in files:
                continue
            fn = f'{V2}/{files[p]}' if e == 'base' else f'{FACE}/{e}/{p}.png'
            if not os.path.exists(fn):
                continue
            b = Image.open(fn).convert('RGBA').crop(BOX).getchannel('A').point(lambda v: 255 if v > 16 else 0).getbbox()
            if b:
                bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
        if bb:
            pbox[p] = list(bb)
    data = {'box': BOX, 'layers': [l for l in layers if l['src'] or l['name'] in PARTS], 'sets': sets,
            'order': ['base'] + [e for e, _ in EXPR if e in sets], 'pbox': pbox}
    html = open(os.path.join(os.path.dirname(__file__), 'face_viewer_template.html'), encoding='utf-8').read()
    html = html.replace('/*DATA*/null', json.dumps(data, ensure_ascii=False))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)
    print(OUT, f'{len(html) / 1e6:.2f} MB', len(data['layers']), 'layers', list(sets))


if __name__ == '__main__':
    main()
