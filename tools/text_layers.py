"""Text-prompted layer split (unmerge-style, fully local).

  1. Grounding DINO finds each part from a text description (box).
  2. SAM2 turns each box into a mask; every opaque pixel is given to exactly one part.
  3. Layers behind other layers are extended under them and the hidden band is
     filled with the anime LaMa inpainter, so nothing gaps when parts move.
  4. Writes one RGBA PNG per part (full canvas), a layered PSD and debug images.

Usage (front-most part first):
  python text_layers.py --image in.png --out outdir \
      --part "back_head=head" --part "tail_left=twin tail@left" --part "tail_right=twin tail@right"

  "@left" / "@right" picks the left-most / right-most detected box for that text.
"""
import argparse
import json
import os
import sys

ROOT = os.environ.get('I2L_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # i2l folder (tools/..)
os.environ.setdefault('HF_HOME', os.path.join(ROOT, 'hf_cache'))
os.environ.setdefault('TORCH_HOME', os.path.join(ROOT, 'hf_cache', 'torch'))
sys.path.insert(0, os.path.join(ROOT, 'see-through'))  # for annotators.lama_inpainter

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

COLORS = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180),
          (70, 240, 240), (240, 50, 230), (210, 245, 60), (250, 190, 190), (0, 128, 128)]


def parse_parts(specs):
    parts = []
    for s in specs:
        name, _, prompt = s.partition('=')
        side = None
        if prompt.endswith('@left') or prompt.endswith('@right'):
            prompt, _, side = prompt.rpartition('@')
        parts.append({'name': name.strip(), 'prompt': prompt.strip(), 'side': side})
    return parts


def detect(rgb, prompts, box_thr, text_thr):
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    mid = 'IDEA-Research/grounding-dino-base'
    proc = AutoProcessor.from_pretrained(mid)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(mid).to('cuda').eval()
    img = Image.fromarray(rgb)
    out = {}
    for p in sorted(set(prompts) - {'*'}):
        inputs = proc(images=img, text=p.lower().rstrip('.') + '.', return_tensors='pt').to('cuda')
        with torch.no_grad():
            o = model(**inputs)
        r = proc.post_process_grounded_object_detection(
            o, inputs.input_ids, threshold=box_thr, text_threshold=text_thr,
            target_sizes=[img.size[::-1]])[0]
        out[p] = [(b.tolist(), float(s)) for b, s in zip(r['boxes'], r['scores'])]
    del model
    torch.cuda.empty_cache()
    return out


def pick_box(cands, side):
    if not cands:
        return None
    if side is None:
        return max(cands, key=lambda c: c[1])[0]
    best = max(c[1] for c in cands)
    good = [c for c in cands if c[1] >= 0.5 * best]
    key = lambda c: (c[0][0] + c[0][2]) / 2
    return (min(good, key=key) if side == 'left' else max(good, key=key))[0]


def segment(rgb, boxes):
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    pred = SAM2ImagePredictor.from_pretrained('facebook/sam2.1-hiera-large', device='cuda')
    pred.set_image(rgb)
    masks = []
    for b in boxes:
        if b is None:
            masks.append(None)
            continue
        m, s, _ = pred.predict(box=np.array(b), multimask_output=False)
        masks.append(m[0].astype(bool))
    del pred
    torch.cuda.empty_cache()
    return masks


def assign(masks, opaque):
    """Label map: -1 = transparent; every opaque pixel gets exactly one part.
    Overlaps go to the front-most part; leftovers go to the nearest part."""
    h, w = opaque.shape
    label = np.full((h, w), -1, np.int32)
    for i, m in enumerate(masks):
        if m is not None:
            label[(label == -1) & m & opaque] = i
    left = opaque & (label == -1)
    if left.any():
        dists = []
        for i, m in enumerate(masks):
            seed = (label == i).astype(np.uint8)
            if seed.any():
                d = cv2.distanceTransform(1 - seed, cv2.DIST_L2, 5)
            else:
                d = np.full((h, w), 1e9, np.float32)
            dists.append(d)
        nearest = np.argmin(np.stack(dists), axis=0)
        label[left] = nearest[left]
    return label


def clean_islands(label, n_parts, min_frac=0.05, min_px=500):
    """Give small pieces that are cut off from a part's main body to the part around them."""
    ring_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    moved = 0
    for i in range(n_parts):
        m = (label == i).astype(np.uint8)
        n, cc, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        if n <= 2:
            continue
        areas = st[1:, cv2.CC_STAT_AREA]
        keep = max(min_px, min_frac * areas.max())
        for c in range(1, n):
            if st[c, cv2.CC_STAT_AREA] >= keep:
                continue
            piece = cc == c
            ring = cv2.dilate(piece.astype(np.uint8), ring_k).astype(bool) & ~piece & (label >= 0) & (label != i)
            if ring.any():
                label[piece] = np.bincount(label[ring]).argmax()
                moved += int(piece.sum())
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--part', action='append', required=True, help='name=text[@left|@right], front-most first')
    ap.add_argument('--box_thr', type=float, default=0.25)
    ap.add_argument('--text_thr', type=float, default=0.25)
    ap.add_argument('--fill_px', type=int, default=48, help='how far a back layer extends under front layers')
    ap.add_argument('--grow_px', type=int, default=5, help="grow detected masks so they keep their outline ('*' mode)")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    parts = parse_parts(a.part)
    rgba = np.asarray(Image.open(a.image).convert('RGBA'))
    alpha = rgba[..., 3].astype(np.float32) / 255
    opaque = rgba[..., 3] > 8
    rgb_white = (rgba[..., :3] * alpha[..., None] + 255 * (1 - alpha[..., None])).astype(np.uint8)

    # 1. detect
    dets = detect(rgb_white, [p['prompt'] for p in parts], a.box_thr, a.text_thr)
    dets['*'] = []
    for p in parts:
        p['box'] = pick_box(dets[p['prompt']], p['side'])
        print(f"[detect] {p['name']:12s} '{p['prompt']}'{'@'+p['side'] if p['side'] else ''}: "
              f"{len(dets[p['prompt']])} boxes -> {None if p['box'] is None else [round(v) for v in p['box']]}")
    dbg = Image.fromarray(rgb_white).convert('RGB')
    d = ImageDraw.Draw(dbg)
    font = ImageFont.load_default(size=20)
    for prompt, cands in dets.items():
        for b, s in cands:
            d.rectangle(b, outline=(160, 160, 160), width=1)
    for i, p in enumerate(parts):
        if p['box'] is not None:
            d.rectangle(p['box'], outline=COLORS[i % 10], width=4)
            d.text((p['box'][0] + 4, p['box'][1] + 4), p['name'], fill=COLORS[i % 10], font=font)
    dbg.save(os.path.join(a.out, 'debug_boxes.png'))

    # 2. segment + assign
    masks = segment(rgb_white, [p['box'] for p in parts])
    rest = [i for i, p in enumerate(parts) if p['prompt'] == '*']
    if rest:  # '*' part = every opaque pixel no detected part claims
        # SAM masks tend to stop just inside the line art; grow them a little so a part keeps its
        # own outline instead of handing it to the '*' part.
        grow = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.grow_px + 1, 2 * a.grow_px + 1))
        claimed = np.zeros_like(opaque)
        for i, m in enumerate(masks):
            if m is not None:
                masks[i] = cv2.dilate(m.astype(np.uint8), grow).astype(bool) & opaque
                claimed |= masks[i]
        masks[rest[0]] = opaque & ~claimed
    label = assign(masks, opaque)
    moved = clean_islands(label, len(parts))
    print(f'[clean] moved {moved}px of cut-off pieces to the surrounding part')
    over = np.asarray(Image.fromarray(rgb_white).convert('RGB')).astype(np.float32)
    for i in range(len(parts)):
        over[label == i] = over[label == i] * 0.45 + np.array(COLORS[i % 10]) * 0.55
    Image.fromarray(over.astype(np.uint8)).save(os.path.join(a.out, 'debug_labels.png'))

    # 3. layers + hidden-band fill for back layers
    from annotators.lama_inpainter import apply_inpaint
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.fill_px + 1, 2 * a.fill_px + 1))
    layers, stats = [], []
    for i, p in enumerate(parts):
        own = label == i
        lay = np.zeros_like(rgba)
        lay[own] = rgba[own]
        front = np.isin(label, list(range(i)))  # parts in front of this one
        band = cv2.dilate(own.astype(np.uint8), kernel).astype(bool) & front
        if own.any():  # stay inside the part's own convex outline
            pts = cv2.findNonZero(own.astype(np.uint8))
            hull = np.zeros(own.shape, np.uint8)
            cv2.fillConvexPoly(hull, cv2.convexHull(pts), 1)
            band &= hull.astype(bool)
        filled = 0
        if band.any() and own.any():
            # Context = this part only: every other pixel takes the colour of the nearest pixel of
            # this part, so LaMa refines the band from the part's own colours (not the front part,
            # not the background).
            from scipy.ndimage import distance_transform_edt
            lum = rgb_white.astype(np.float32).mean(axis=2)
            core = cv2.erode(own.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
            chroma = rgb_white.max(axis=2).astype(np.int16) - rgb_white.min(axis=2)
            src = core & (lum > 70) & (lum < 235) & (chroma > 30)  # skip line art, pale fringe, greys
            if src.sum() < 0.2 * core.sum():  # grey/monochrome part: drop the colour test
                src = core & (lum > 70) & (lum < 235)
            if not src.any():
                src = own
            _, (iy, ix) = distance_transform_edt(~src, return_indices=True)
            ctx = rgb_white[iy, ix]
            inp = apply_inpaint(ctx, (band * 255).astype(np.uint8))
            lay[band, :3] = inp[band]
            lay[band, 3] = 255
            filled = int(band.sum())
        layers.append(lay)
        stats.append({'name': p['name'], 'prompt': p['prompt'], 'side': p['side'], 'box': p['box'],
                      'visible_px': int(own.sum()), 'filled_px': filled})
        Image.fromarray(lay).save(os.path.join(a.out, f"{i:02d}_{p['name']}.png"))
        print(f"[layer] {p['name']:12s} visible {int(own.sum()):7d}px  filled under front {filled:6d}px")

    # 4. PSD (bottom = back-most part)
    try:
        from psd_tools import PSDImage
        from psd_tools.api.layers import PixelLayer
        h, w = label.shape
        psd = PSDImage.new('RGBA', (w, h))
        for i in reversed(range(len(parts))):
            psd.append(PixelLayer.frompil(Image.fromarray(layers[i]), psd, parts[i]['name']))
        psd.save(os.path.join(a.out, 'layers.psd'))
        print('[psd] layers.psd written')
    except Exception as e:  # PNGs are the primary output
        print('[psd] skipped:', repr(e))

    json.dump(stats, open(os.path.join(a.out, 'parts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
