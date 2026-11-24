"""Drop-in replacement for inference_psd_quantized.run_layerdiff with a growing head crop.

Original: head crop = head.png box + 1/5 margin on each side, head pass runs once.
Here:     after each head pass, every side where a head layer touches the crop border (and the
          border is not the image edge) is pushed out by GROW_STEP x head size, and the head pass
          is run again from the same generator state, so only the crop changes. Stops when nothing
          touches, after MAX_ITERS extra passes, or when a side reaches MAX_MARGIN x head size.

Env (set by run_seethrough.ps1 -HeadGrow N):
  HEAD_GROW_ITERS   extra head passes allowed (0 = original behaviour)
  HEAD_GROW_STEP    growth per touching side, fraction of head w/h (default 0.25)
  HEAD_GROW_MAX     max margin per side, fraction of head w/h (default 1.0)
  HEAD_GROW_MINPX   border pixels needed to count as touching (default 8)

Writes, besides the usual files: head_grow/src_head_<i>.png, head_grow/<i>_<tag>.png (crop-local
results of every pass) and head_grow.json (boxes in input-image and 1024 coords, touching sides).

Derived from `run_layerdiff` in See-through inference/scripts/inference_psd_quantized.py
(https://github.com/mitmul/see-through, commit e4cb250, Apache License 2.0).
Changes: per-side margins, repeated head pass with a growing crop, debug outputs, head_grow.json.
"""
import json
import os
import os.path as osp

import cv2
import numpy as np
import torch
from PIL import Image

from utils.cv import center_square_pad_resize, smart_resize

BODY = ['front hair', 'back hair', 'head', 'neck', 'neckwear', 'topwear', 'handwear', 'bottomwear',
        'legwear', 'footwear', 'tail', 'wings', 'objects']
HEAD = ['headwear', 'face', 'irides', 'eyebrow', 'eyewhite', 'eyelash', 'eyewear', 'ears', 'earwear',
        'nose', 'mouth']


def _pass(pipeline, steps, rng, tags, fullpage, group):
    return pipeline(strength=1.0, num_inference_steps=steps, batch_size=1, generator=rng,
                    guidance_scale=1.0, prompt=tags, negative_prompt='', fullpage=fullpage,
                    group_index=group).images


def run_layerdiff(pipeline, imgp, save_dir, seed, num_inference_steps, resolution):
    iters = int(os.environ.get('HEAD_GROW_ITERS', '0'))
    step = float(os.environ.get('HEAD_GROW_STEP', '0.25'))
    max_m = float(os.environ.get('HEAD_GROW_MAX', '1.0'))
    min_px = int(os.environ.get('HEAD_GROW_MINPX', '8'))

    saved = osp.join(save_dir, osp.splitext(osp.basename(imgp))[0])
    dbg = osp.join(saved, 'head_grow')
    os.makedirs(dbg, exist_ok=True)
    input_img = np.array(Image.open(imgp).convert('RGBA'))
    fullpage, pad_size, pad_pos = center_square_pad_resize(input_img, resolution, return_pad_info=True)
    scale = pad_size[0] / resolution
    Image.fromarray(fullpage).save(osp.join(saved, 'src_img.png'))
    rng = torch.Generator(device=pipeline.unet.device).manual_seed(seed)

    images = _pass(pipeline, num_inference_steps, rng, BODY, fullpage, 0)
    for rst, tag in zip(images, BODY):
        Image.fromarray(rst).save(osp.join(saved, f'{tag}.png'))
    head_img = images[2]

    # head box in input-image coords (same math as the original)
    hx0, hy0, hw, hh = cv2.boundingRect(cv2.findNonZero((head_img[..., -1] > 15).astype(np.uint8)))
    hx, hy = int(hx0 * scale) - pad_pos[0], int(hy0 * scale) - pad_pos[1]
    hw, hh = int(hw * scale), int(hh * scale)
    IH, IW = input_img.shape[:2]
    # per-side margins; the original adds w//5, h//5 only when the head is smaller than half the image
    m = {'left': hw // 5 if hw < IW // 2 else 0, 'right': hw // 5 if hw < IW // 2 else 0,
         'top': hh // 5 if hh < IH // 2 else 0, 'bottom': hh // 5 if hh < IH // 2 else 0}
    cap = {'left': int(max_m * hw), 'right': int(max_m * hw), 'top': int(max_m * hh), 'bottom': int(max_m * hh)}

    rng_state = rng.get_state()
    log = {'head_xywh_input': [hx, hy, hw, hh], 'scale': scale, 'pad_pos': list(pad_pos),
           'iters_allowed': iters, 'step': step, 'max_margin': max_m, 'passes': []}
    for it in range(iters + 1):
        x1, x2 = max(hx - m['left'], 0), min(hx + hw + m['right'], IW)
        y1, y2 = max(hy - m['top'], 0), min(hy + hh + m['bottom'], IH)
        input_head = input_img[y1:y2, x1:x2]
        ih, iw = input_head.shape[:2]
        head_page, hpad_size, hpad_pos = center_square_pad_resize(input_head, resolution, return_pad_info=True)
        Image.fromarray(head_page).save(osp.join(dbg, f'src_head_{it}.png'))
        rng.set_state(rng_state)  # same noise every pass -> only the crop differs
        outs = _pass(pipeline, num_inference_steps, rng, HEAD, head_page, 1)

        # crop-local results (input-image scale / `scale` = 1024 page units), as the original pastes them
        py1, py2, px1, px2 = (np.array([hpad_pos[1], hpad_pos[1] + ih, hpad_pos[0], hpad_pos[0] + iw]) / scale).astype(np.int64)
        ssize = (int(hpad_size[0] / scale), int(hpad_size[1] / scale))
        locs = [smart_resize(r, ssize)[py1:py2, px1:px2] for r in outs]

        touch = {}
        for tag, r in zip(HEAD, locs):
            a = r[..., 3] > 15
            if not a.any():
                continue
            k = 2
            sides = {'left': a[:, :k].sum(), 'right': a[:, -k:].sum(), 'top': a[:k].sum(), 'bottom': a[-k:].sum()}
            for s, n in sides.items():
                if n >= min_px:
                    touch.setdefault(s, []).append([tag, int(n)])
            Image.fromarray(r).save(osp.join(dbg, f'{it}_{tag}.png'))
        at_edge = {'left': x1 == 0, 'right': x2 == IW, 'top': y1 == 0, 'bottom': y2 == IH}
        grow = [s for s in touch if not at_edge[s] and m[s] < cap[s]]
        hx1 = int(x1 / scale + pad_pos[0] / scale)
        hy1 = int(y1 / scale + pad_pos[1] / scale)
        log['passes'].append({'pass': it, 'crop_input': [x1, y1, x2, y2],
                              'crop_1024': [hx1, hy1, hx1 + locs[0].shape[1], hy1 + locs[0].shape[0]],
                              'margins': dict(m), 'touching': touch, 'grow': grow})
        print(f'[head_grow] pass {it}: crop {[x1, y1, x2, y2]} touching {sorted(touch)} -> grow {grow}', flush=True)
        if not grow or it == iters:
            break
        for s in grow:
            m[s] = min(m[s] + int(step * (hw if s in ('left', 'right') else hh)), cap[s])

    Image.fromarray(head_page).save(osp.join(saved, 'src_head.png'))
    canvas = np.zeros((resolution, resolution, 4), dtype=np.uint8)
    for r, tag in zip(locs, HEAD):
        full = canvas.copy()
        full[hy1:hy1 + r.shape[0], hx1:hx1 + r.shape[1]] = r[:resolution - hy1, :resolution - hx1]
        Image.fromarray(full).save(osp.join(saved, f'{tag}.png'))
    log['final_pass'] = it
    json.dump(log, open(osp.join(saved, 'head_grow.json'), 'w'), indent=1)
