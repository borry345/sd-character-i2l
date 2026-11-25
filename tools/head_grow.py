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
  HEAD_BOX          x0,y0,x1,y1: fixed head crop on the 1024 page (src_img.png), set by the person instead of
                    growing it; the head pass is redrawn with new noise (seed + 1000 x try) until every HEAD_NEED
                    tag comes out (run_seethrough.ps1 -HeadBox)
  HEAD_NEED         with HEAD_BOX: tag:min_px,... that must come out and not touch the crop border (-HeadNeed)
  HEAD_TRIES        with HEAD_BOX: max head passes (default 5); if none has everything, the best try is used
                    (all tags from ONE try: tags of different noise do not fit together)
  HEAD_GROW_KEEP    which pass each head tag comes from: max (default) = the last pass, unless the tag shrank
                    there below HEAD_GROW_KEEP_RATIO (default 0.5) x its biggest pass -> that biggest pass;
                    last = the last pass for every tag (behaviour before 2026-11-26)

Writes, besides the usual files: head_grow/src_head_<i>.png, head_grow/<i>_<tag>.png (crop-local
results of every pass), head_grow/pass<i>/<tag>.png (every pass on the 1024 page) and head_grow.json
(boxes in input-image and 1024 coords, touching sides, tag_pass = pass used per tag, tag_px).

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

    keep = os.environ.get('HEAD_GROW_KEEP', 'max')
    # fixed box: the person sets the head crop (1024 page coords, = src_img.png); the head pass is redrawn with
    # new noise until every HEAD_NEED tag has its pixels and does not touch the crop border
    fixed = None
    if os.environ.get('HEAD_BOX'):
        bx = [float(v) for v in os.environ['HEAD_BOX'].split(',')]
        fixed = [max(int(bx[0] * scale) - pad_pos[0], 0), max(int(bx[1] * scale) - pad_pos[1], 0),
                 min(int(bx[2] * scale) - pad_pos[0], input_img.shape[1]), min(int(bx[3] * scale) - pad_pos[1], input_img.shape[0])]
        iters = max(int(os.environ.get('HEAD_TRIES', '5')) - 1, 0)
    need = {}
    for item in filter(None, os.environ.get('HEAD_NEED', '').split(',')):
        tg, _, n = item.partition(':')
        need[tg.strip()] = int(n or 1)
    tries = []
    passes = []
    rng_state = rng.get_state()
    log = {'head_xywh_input': [hx, hy, hw, hh], 'scale': scale, 'pad_pos': list(pad_pos),
           'iters_allowed': iters, 'step': step, 'max_margin': max_m, 'passes': []}
    for it in range(iters + 1):
        if fixed:
            x1, y1, x2, y2 = fixed
        else:
            x1, x2 = max(hx - m['left'], 0), min(hx + hw + m['right'], IW)
            y1, y2 = max(hy - m['top'], 0), min(hy + hh + m['bottom'], IH)
        input_head = input_img[y1:y2, x1:x2]
        ih, iw = input_head.shape[:2]
        head_page, hpad_size, hpad_pos = center_square_pad_resize(input_head, resolution, return_pad_info=True)
        Image.fromarray(head_page).save(osp.join(dbg, f'src_head_{it}.png'))
        if fixed and it > 0:
            rng.manual_seed(seed + 1000 * it)  # fixed box: new noise every try
        else:
            rng.set_state(rng_state)  # growing box: same noise every pass -> only the crop differs
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
        passes.append((locs, hx1, hy1))
        if fixed:
            px = {tag: int((r[..., 3] > 15).sum()) for tag, r in zip(HEAD, locs)}
            touching = {tg for s in touch.values() for tg, _ in s}
            miss = {tg: px.get(tg, 0) for tg, n in need.items() if px.get(tg, 0) < n or tg in touching}
            score = sum(min(px.get(tg, 0) / n, 1.0) - (0.5 if tg in touching else 0) for tg, n in need.items())
            tries.append(score)
            log['passes'][-1].update({'noise': 'seed' if it == 0 else f'seed+{1000 * it}', 'need_missing': miss, 'grow': []})
            print(f'[head_grow] try {it}: box {[x1, y1, x2, y2]} missing {miss or "none"}', flush=True)
            if not miss or it == iters:
                break
            continue
        print(f'[head_grow] pass {it}: crop {[x1, y1, x2, y2]} touching {sorted(touch)} -> grow {grow}', flush=True)
        if not grow or it == iters:
            break
        for s in grow:
            m[s] = min(m[s] + int(step * (hw if s in ('left', 'right') else hh)), cap[s])

    Image.fromarray(head_page).save(osp.join(saved, 'src_head.png'))
    pages = [[paste(r, x, y, resolution) for r in locs_] for locs_, x, y in passes]
    for i, pg in enumerate(pages):  # every pass on the 1024 page, so a pass can be picked later (mix_layers "png")
        os.makedirs(osp.join(dbg, f'pass{i}'), exist_ok=True)
        for full, tag in zip(pg, HEAD):
            if full[..., 3].any():
                Image.fromarray(full).save(osp.join(dbg, f'pass{i}', f'{tag}.png'))
    if fixed:  # one whole try (different noise: tags of different tries do not fit together)
        best = max(range(len(tries)), key=lambda i: (tries[i], -i))
        choice = [best] * len(HEAD)
        log.update({'mode': 'fixed_box', 'head_box_1024': os.environ['HEAD_BOX'], 'need': need, 'used_try': best})
    else:
        choice = None
    choice = choice or pick_passes([[int((f[..., 3] > 15).sum()) for f in pg] for pg in pages], keep,
                         float(os.environ.get('HEAD_GROW_KEEP_RATIO', '0.5')))
    for k, tag in enumerate(HEAD):
        Image.fromarray(pages[choice[k]][k]).save(osp.join(saved, f'{tag}.png'))
    log['final_pass'] = it
    log['keep'] = keep
    log['tag_pass'] = {tag: choice[k] for k, tag in enumerate(HEAD)}
    log['tag_px'] = {tag: [int((pg[k][..., 3] > 15).sum()) for pg in pages] for k, tag in enumerate(HEAD)}
    json.dump(log, open(osp.join(saved, 'head_grow.json'), 'w'), indent=1)


def paste(r, x, y, resolution):
    full = np.zeros((resolution, resolution, 4), dtype=np.uint8)
    full[y:y + r.shape[0], x:x + r.shape[1]] = r[:resolution - y, :resolution - x]
    return full


def pick_passes(px, keep='max', ratio=0.5):
    """px[pass][tag] = pixel count -> pass index per tag.
    keep='last': every tag from the last pass (original behaviour).
    keep='max' : a tag stays in the last pass unless it shrank there below `ratio` x its biggest pass; then
                 it comes from that biggest pass. A wider crop redraws every head tag, and a tag can vanish in
                 the later pass (miku seed3: headwear 9,991px -> 0, seed8: face 35,280px -> 0). Small changes
                 (eyebrow 494 -> 428) keep the last pass, so eyes are not mixed from different passes."""
    last = len(px) - 1
    out = []
    for k in range(len(px[0])):
        best = max(range(len(px)), key=lambda i: (px[i][k], i))
        out.append(best if keep == 'max' and px[last][k] < ratio * px[best][k] else last)
    return out
