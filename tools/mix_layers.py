"""Build one PSD from tag layers picked out of several See-through runs (seeds).

All runs share the same 1024 page (same source image), so layers can be mixed freely.
Spec (JSON):
  {"src": "seethrough_test/miku_chibi_sprite/miku_chibi_sprite/src_img.png",
   "layers": [
     {"name": "front hair", "run": "seethrough_test/miku_grow_seed9", "tag": "front hair"},
     {"name": "tail_left", "run": "...seed0", "tag": "back hair", "split": "left"},
     {"name": "back_center", "run": "...", "tag": "back hair",
      "minus": [{"run": "...seed0", "tag": "back hair"}], "minus_grow": 4, "keep": "largest"},
     {"name": "neck", "run": "...seed2", "tag": "neck", "hidden": true}]}

  split      left/right: connected pieces whose centre is left/right of the layer's centre (image left/right)
  minus      remove pixels covered by other runs' layers (grown by minus_grow px)
  keep       "largest": keep only the largest connected piece
  depth      fixed depth instead of the median (mouth in front of face)
  rgb_from   "src": keep the layer alpha, take colour from the original (mouth/nose halo fix)
  (top level) "visible_rgb": "src" = shown layers take the original colour on the pixels they show
             (down through semi-transparent edges to the first opaque layer); hidden parts keep generated colour
  keep_rgb   true: leave this layer out of visible_rgb (keeps its generated colour)
  (top level) "visible_rgb": "owner" = each original pixel goes to ONE layer chosen by colour (see
             owner_assign); composite ~ original, layers keep only their own lines. "rgb_thr" (60),
             "owner_r" (2 px; outlines search 2x). Per layer "owner_guard": false = always take the
             original colour (eye layers, whose detail is all lines)
             "line_front" N: an outline pixel inside a back layer goes to the nearest front layer within N px
             "bd_guard" N: within N px of another part, a pixel the original would make darker keeps the
             generated colour (no other part's line); "guard_hand" N: such pixels go to the nearest front
             layer within N px instead (composite keeps the line)
  (top level) "align": "flow" | "sam2" | "flow+sam2" (shift layers onto the original first),
             "blend": "poisson" | "poisson_seam" (smooth the visible/hidden colour seam)
  despill    "magenta": recolour key-mode magenta leftovers with the nearest clean colour
  erase      mask png (white = remove): cleared from this layer at the very end
  hidden     put in the PSD but switched off, and leave out of the composite check
Depth = median of the run's <tag>_depth.png over the layer's own pixels (0 = near). PSD bottom = far.

  env\\Scripts\\python.exe tools\\mix_layers.py --spec <spec.json> --out <dir>
Writes <dir>/layers/NN_name.png (NN = front-to-back), mix.psd, mix.json, sheet.png, check.png,
hidden.png (each layer alone, green = covered by layers in front).
"""
import argparse
import json
import os
import os.path as osp

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys
sys.path.insert(0, osp.dirname(osp.abspath(__file__)))
from layer_common import rgb_from_src  # noqa: E402

try:  # labels on check images are Korean -> a Hangul font
    FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 13)
except OSError:
    FONT = ImageFont.load_default()


def mid_dir(run):
    psds = [f for f in os.listdir(run) if f.endswith('.psd') and not f.endswith('_depth.psd')]
    return osp.join(run, psds[0][:-4])


def load(run, tag):
    return np.array(Image.open(osp.join(mid_dir(run), f'{tag}.png')).convert('RGBA'))


def checker(w, h, s=16):
    y, x = np.mgrid[:h, :w]
    c = np.where(((x // s) + (y // s)) % 2 == 0, 255, 225).astype(np.uint8)
    return Image.fromarray(np.stack([c] * 3 + [np.full_like(c, 255)], -1), 'RGBA')


def build(L, src_rgba):
    # "png": use this file instead of the run's tag PNG (e.g. an amodal-completed layer); depth still
    # comes from run/tag
    im = np.array(Image.open(L['png']).convert('RGBA')) if 'png' in L else load(L['run'], L['tag'])
    a = im[..., 3] > 15
    if 'minus' in L:
        k = 2 * L.get('minus_grow', 0) + 1
        for mm in L['minus']:
            o = (load(mm['run'], mm['tag'])[..., 3] > 15).astype(np.uint8)
            if k > 1:
                o = cv2.dilate(o, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            a &= ~o.astype(bool)
    if 'split' in L or L.get('keep') == 'largest':
        n, lab, st, cen = cv2.connectedComponentsWithStats(a.astype(np.uint8), connectivity=8)
        keep = np.zeros_like(a)
        if L.get('keep') == 'largest' and n > 1:
            keep = lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        if 'split' in L:
            # "left" / "right" / "top" / "bottom" or a pair like "top-left": pieces whose centre is on
            # that side of the layer's box centre
            ys, xs = np.nonzero(a)
            mx, my = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
            want = L['split'].split('-')
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] < 50:
                    continue
                side = {'left': cen[i, 0] < mx, 'right': cen[i, 0] >= mx, 'top': cen[i, 1] < my, 'bottom': cen[i, 1] >= my}
                if all(side[w] for w in want):
                    keep |= lab == i
            if L.get('split_cut') and want[0] in ('left', 'right') and len(want) == 1:
                # pieces touch (e.g. two legs meeting at the thighs): cut at the column with the fewest
                # layer pixels in the middle 40% of the box instead of by connected pieces
                x0, x1 = xs.min(), xs.max()
                lo, hi = int(x0 + 0.3 * (x1 - x0)), int(x0 + 0.7 * (x1 - x0))
                col = a[:, lo:hi + 1].sum(0)
                c = lo + int(np.argmin(col))
                L['split_cut_x'], L['split_cut_px'] = c, int(col.min())
                keep = a.copy()
                if want[0] == 'left':
                    keep[:, c:] = False
                else:
                    keep[:, :c] = False
        a = keep
    out = im.copy()
    out[~a] = 0
    if L.get('rgb_from') == 'src':  # colour from the original (mouth/nose whiskers, layer_common.py)
        out = rgb_from_src(out, src_rgba, a)
    if L.get('despill') == 'magenta':  # key-mode leftovers: magenta-ish pixels take the nearest clean colour
        from scipy.ndimage import distance_transform_edt
        o = out.astype(int)
        mag = a & (o[..., 0] > o[..., 1] + 30) & (o[..., 2] > o[..., 1] + 30)
        if mag.any():
            _, (iy, ix) = distance_transform_edt(~(a & ~mag), return_indices=True)
            out[mag, :3] = out[iy[mag], ix[mag], :3]
            L['despilled_px'] = int(mag.sum())
    dep = np.array(Image.open(osp.join(mid_dir(L['run']), f"{L['tag']}_depth.png")).convert('L'))
    d = float(np.median(dep[a])) / 255 if a.any() else 1.0
    if 'depth' in L:  # manual order fix (e.g. mouth in front of face, as See-through forces)
        d = float(L['depth'])
    return out, d


def line_mask(src_rgba, dark=90, hat=25):
    """Outline pixels of the original: dark (max channel < dark) or darker than their surroundings by
    > hat (black-hat, 7px) - the second catches the anti-aliased grey fringe of an outline."""
    w = (src_rgba[..., :3].astype(float) * (src_rgba[..., 3:] / 255) + 255 * (1 - src_rgba[..., 3:] / 255))
    g = cv2.cvtColor(w.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    return (src_rgba[..., 3] > 15) & ((src_rgba[..., :3].max(-1) < dark) | (bh > hat))


def flow_align(items, src_rgba, max_px=8.0):
    """align "flow": shift every generated layer onto the original with one dense optical flow.

    Flow is measured between the composite of the generated layers (generated colours) and the original,
    both on white, so the outlines line up; every layer (hidden parts too) is resampled with it.
    """
    shown = [it for it in items if not it.get('hidden')]
    H, W = src_rgba.shape[:2]
    comp = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    for it in reversed(shown):
        comp.alpha_composite(Image.fromarray(it['img']))
    white = lambda x: (x[..., :3].astype(float) * (x[..., 3:] / 255) + 255 * (1 - x[..., 3:] / 255))
    g_src = cv2.cvtColor(white(src_rgba).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    g_gen = cv2.cvtColor(np.array(comp)[..., :3], cv2.COLOR_RGB2GRAY)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    f = dis.calc(g_src, g_gen, None)           # src(p) ~ gen(p + f(p))
    f = cv2.GaussianBlur(f, (0, 0), 1.5)
    mag = np.linalg.norm(f, axis=-1)
    f *= np.minimum(1, max_px / np.maximum(mag, 1e-6))[..., None]
    y, x = np.mgrid[:H, :W].astype(np.float32)
    mx, my = x + f[..., 0], y + f[..., 1]
    for it in items:
        im = it['img'].astype(np.float32)
        pm = im.copy()
        pm[..., :3] *= im[..., 3:] / 255   # premultiplied, so edges do not pick up black
        w = cv2.remap(pm, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = w[..., 3:]
        w[..., :3] = np.where(a > 0, w[..., :3] * 255 / np.maximum(a, 1e-6), 0)
        it['img'] = np.clip(w + 0.5, 0, 255).astype(np.uint8)
    sil = src_rgba[..., 3] > 15
    return {'flow_mean_px': round(float(mag[sil].mean()), 2), 'flow_p95_px': round(float(np.percentile(mag[sil], 95)), 2)}


def sam_refine(shown, src_rgba, owner, sil, grow=6):
    """align "sam2": SAM2 re-cuts every layer's visible part from the original image.

    Prompts per layer: box + up to 5 points deep inside its current visible part (positive) and up to
    5 deep inside other layers' visible parts in that box (negative); of the 3 masks the one closest to
    the current visible part is kept if IoU >= 0.5. A pixel goes to the front-most layer whose SAM mask
    has it and whose generated shape is within `grow` px; pixels no accepted mask claims keep the
    colour-based owner.
    """
    import torch
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    white = (src_rgba[..., :3].astype(float) * (src_rgba[..., 3:] / 255) + 255 * (1 - src_rgba[..., 3:] / 255))
    pred = SAM2ImagePredictor.from_pretrained('facebook/sam2.1-hiera-large', device='cuda')
    pred.set_image(white.astype(np.uint8))
    n = len(shown)
    vis = [(owner == k) for k in range(n)]
    core = [cv2.distanceTransform(v.astype(np.uint8), cv2.DIST_L2, 5) for v in vis]

    def pick(d, box, k):
        x0, y0, x1, y1 = box
        sub = d[y0:y1, x0:x1].copy()
        pts = []
        for _ in range(k):
            i = np.argmax(sub)
            if sub.flat[i] < 3:
                break
            yy, xx = np.unravel_index(i, sub.shape)
            pts.append([x0 + xx, y0 + yy])
            r = max(int(sub.flat[i] * 2), 8)
            sub[max(yy - r, 0):yy + r, max(xx - r, 0):xx + r] = 0
        return pts

    cand = np.zeros((n,) + owner.shape, bool)
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1))
    for k, it in enumerate(shown):
        v = vis[k]
        it['sam_iou'] = None
        if v.sum() < 30:
            continue
        ys, xs = np.nonzero(v)
        box = [max(xs.min() - 3, 0), max(ys.min() - 3, 0), min(xs.max() + 4, owner.shape[1]), min(ys.max() + 4, owner.shape[0])]
        pos = pick(core[k], box, 5)
        other = np.max(np.stack([core[j] for j in range(n) if j != k]), 0)
        neg = pick(other, box, 5)
        if not pos:
            continue
        pc = np.array(pos + neg, np.float32)
        pl = np.array([1] * len(pos) + [0] * len(neg), np.int32)
        ms, sc, _ = pred.predict(point_coords=pc, point_labels=pl, box=np.array(box, np.float32), multimask_output=True)
        ious = [(m.astype(bool) & v).sum() / max((m.astype(bool) | v).sum(), 1) for m in ms]
        j = int(np.argmax(ious))
        it['sam_iou'] = round(float(ious[j]), 3)
        if ious[j] < 0.5:
            continue
        near = cv2.dilate((it['img'][..., 3] > 15).astype(np.uint8), k5).astype(bool)
        cand[k] = ms[j].astype(bool) & near & sil
    del pred
    torch.cuda.empty_cache()
    has = cand.any(0)
    new = np.where(has, np.argmax(cand, 0), owner)
    new[~sil] = -1
    for k, it in enumerate(shown):
        it['sam_changed_px'] = int(((new == k) & (owner != k)).sum())
    return new


def poisson_seam_blend(it, src_rgba, seam_px=8, max_step=80):
    """blend "poisson_seam": like poisson, but the generated texture (its gradients) is faded out near the
    visible part: weight 0 at the border -> 1 at seam_px. Edges the generated layer drew just under the
    visible part (e.g. s1 face's pink 'hair here' area, while the hair layer is from s9) are dropped and
    the hidden part continues the visible colour smoothly there; deeper hidden detail is kept.
    Solves sum_j (u_i - u_j) = sum_j w_ij (gen_i - gen_j) on hidden pixels, u_j = original on bordering
    visible pixels (except line/fill steps > max_step -> no constraint)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    im, gen, own = it['img'], it['gen'], it['own_mask']
    G = (im[..., 3] > 15) & ~own
    if not G.any() or not own.any():
        return
    H, W = G.shape
    idx = -np.ones((H, W), np.int64)
    ys, xs = np.nonzero(G)
    idx[ys, xs] = np.arange(len(ys))
    src = src_rgba[..., :3].astype(float)
    g = gen[..., :3].astype(float)
    okb = own & ~line_mask(src_rgba) & (np.abs(src - np.where((gen[..., 3:] > 15), g, src)).max(-1) <= max_step)
    dist = cv2.distanceTransform((~own).astype(np.uint8), cv2.DIST_L2, 5)
    wpx = np.clip(dist / seam_px, 0, 1)
    eps = 1e-4
    rows, cols, vals = [], [], []
    diag = np.full(len(ys), eps)
    rhs = np.zeros((len(ys), 3))
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ny, nx = ys + dy, xs + dx
        inb = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        ny, nx = np.clip(ny, 0, H - 1), np.clip(nx, 0, W - 1)
        nG = inb & G[ny, nx]
        nB = inb & okb[ny, nx] & ~G[ny, nx]
        use = nG | nB
        diag += use
        w = np.minimum(wpx[ys, xs], wpx[ny, nx])[:, None]
        gj = np.where((gen[ny, nx, 3] > 15)[:, None], g[ny, nx], g[ys, xs])
        rhs[use] += (w * (g[ys, xs] - gj))[use]
        rows.append(np.nonzero(nG)[0]); cols.append(idx[ny[nG], nx[nG]]); vals.append(-np.ones(nG.sum()))
        rhs[nB] += src[ny[nB], nx[nB]]
    # eps pulls toward the generated colour where nothing constrains a piece
    rhs += eps * g[ys, xs]
    A = coo_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(len(ys))]),
                    np.concatenate(cols + [np.arange(len(ys))]))), shape=(len(ys), len(ys))).tocsr()
    u = spsolve(A, rhs)
    out = im[..., :3].astype(float)
    out[ys, xs] = u
    im[..., :3] = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    it['blend_mean_abs'] = round(float(np.abs(u - g[ys, xs]).mean()), 2)


def poisson_blend(it, src_rgba, max_step=80):
    """blend "poisson": hidden (generated) part of a layer is shifted in colour so it meets the
    original-coloured visible part without a seam. Correction d solves Laplace(d) = 0 on the generated
    pixels, d = original - generated on the bordering visible pixels (skipped where the step is > max_step,
    i.e. a line meets fill), and d -> 0 where nothing borders (tiny pull to 0)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    im, gen, own = it['img'], it['gen'], it['own_mask']
    G = (im[..., 3] > 15) & ~own
    if not G.any():
        return
    H, W = G.shape
    idx = -np.ones((H, W), np.int64)
    ys, xs = np.nonzero(G)
    idx[ys, xs] = np.arange(len(ys))
    step = src_rgba[..., :3].astype(float) - gen[..., :3].astype(float)
    okb = own & ~line_mask(src_rgba) & (gen[..., 3] > 15) & (np.abs(step).max(-1) <= max_step)
    eps = 1e-3
    rows, cols, vals = [], [], []
    diag = np.full(len(ys), eps)
    rhs = np.zeros((len(ys), 3))
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ny, nx = ys + dy, xs + dx
        inb = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        ny, nx = np.clip(ny, 0, H - 1), np.clip(nx, 0, W - 1)
        nG = inb & G[ny, nx]
        nB = inb & okb[ny, nx]
        diag += nG | nB
        rows.append(np.nonzero(nG)[0]); cols.append(idx[ny[nG], nx[nG]]); vals.append(-np.ones(nG.sum()))
        rhs[nB] += step[ny[nB], nx[nB]]
    A = coo_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(len(ys))]),
                    np.concatenate(cols + [np.arange(len(ys))]))), shape=(len(ys), len(ys))).tocsr()
    d = spsolve(A, rhs)
    out = im[..., :3].astype(float)
    out[ys, xs] += d
    im[..., :3] = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    it['blend_mean_abs'] = round(float(np.abs(d).mean()), 2)


def extra_edges(it):
    """Edges inside the layer (>= 3px from its border) that its own generated version does not have
    (within 2px): other parts' lines and colour seams. Returns (count, mask)."""
    def edges(x):
        w = (x[..., :3].astype(float) * (x[..., 3:] / 255) + 255 * (1 - x[..., 3:] / 255)).astype(np.uint8)
        return cv2.Canny(cv2.cvtColor(w, cv2.COLOR_RGB2GRAY), 40, 120) > 0
    im, gen = it['img'], it['gen']
    inner = cv2.erode(((im[..., 3] > 128) & (gen[..., 3] > 128)).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    eg = cv2.dilate(edges(gen).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    m = edges(im) & ~eg & inner
    return int(m.sum()), m


def owner_assign(items, src_rgba, thr, R, sam=False, guard=True, line_front=0, bd_px=0, hand_px=0,
                 lf_dark=25.0, lf_in=None):
    """visible_rgb "owner": every original pixel gets exactly one owner layer, chosen by colour.

    Layer shapes from generation are 1-3px off the original, so "which layer covers this pixel" alone
    hands a neighbour's outline to the wrong layer. Here, per layer, score = smallest colour difference
    between the original pixel and the layer's own generated pixels within R px (alpha >= 128).
    Owner = the front-most layer with score <= thr (an outline next to two parts goes to the front part);
    if none, the layer with the lowest score; if no layer is within R px, the nearest layer.
    Then: owner gets the original RGBA there; layers in front of the owner are cleared there (their
    misplaced edge would hide it); layers behind keep their generated colour (hidden part), except on
    semi-transparent original edges and outside the original silhouette, where they are cleared.
    """
    from scipy.ndimage import distance_transform_edt
    shown = [it for it in items if not it.get('hidden')]
    H, W = src_rgba.shape[:2]
    srgb = src_rgba[..., :3].astype(np.int16)
    sil = src_rgba[..., 3] > 15
    BIG = 999
    RL = 2 * R  # outline (dark) pixels search further: a part's generated outline can sit 3-4px off
    line = line_mask(src_rgba)
    scores = []
    for it in shown:
        im = it['img']
        sc = np.full((H, W), BIG, np.int16)
        pad = RL
        g = np.pad(im[..., :3].astype(np.int16), ((pad, pad), (pad, pad), (0, 0)))
        ga = np.pad(im[..., 3] >= 128, pad)
        cov = im[..., 3] > 15
        for dy in range(-RL, RL + 1):
            for dx in range(-RL, RL + 1):
                r2 = dy * dy + dx * dx
                if r2 > RL * RL + 1:
                    continue
                gs = g[pad + dy:pad + dy + H, pad + dx:pad + dx + W]
                ok = ga[pad + dy:pad + dy + H, pad + dx:pad + dx + W].copy()
                if r2 > R * R + 1:  # far search only for line pixels this layer already covers
                    ok &= line & cov
                d = np.abs(gs - srgb).max(-1)
                d[~ok] = BIG
                np.minimum(sc, d, out=sc)
        scores.append(sc)
    S = np.stack(scores)                       # (n, H, W), front first
    good = S <= thr
    first_good = np.argmax(good, 0)
    any_good = good.any(0)
    best = np.argmin(S, 0)
    any_near = (S < BIG).any(0)
    dists = np.stack([distance_transform_edt(it['img'][..., 3] > 15) for it in shown])  # depth inside
    nearest = np.argmin(np.stack([distance_transform_edt(~(it['img'][..., 3] > 15)) for it in shown]), 0)
    owner = np.where(any_good, first_good, np.where(any_near, best, nearest))
    # a pixel deep inside a layer (> R+1 px from its edge) is not an edge misplacement: the front-most
    # such layer keeps it even if the colour differs, so no hole is punched into it
    deep = dists > R + 1
    first_deep = np.where(deep.any(0), np.argmax(deep, 0), len(shown))
    it_deep = first_deep < owner
    owner = np.where(it_deep, first_deep, owner)
    owner[~sil] = -1
    for k, it in enumerate(shown):
        it['own_deep_px'] = int((it_deep & (owner == k)).sum())
    if sam:
        owner = sam_refine(shown, src_rgba, owner, sil)
    if line_front > 0:
        # line hand-off: an outline pixel that landed inside a layer (> R px from its edge) where that
        # layer's generated colour is clearly lighter is a FRONT part's outline (its generated shape is a
        # few px smaller than the original). Give it to the nearest layer in front whose shape is within
        # line_front px -> composite unchanged, the back layer stays clean, the front layer grows a little.
        wf = lambda x: (x[..., :3].astype(np.float32) * (x[..., 3:] / 255) + 255 * (1 - x[..., 3:] / 255)) @ np.float32([0.299, 0.587, 0.114])
        Ls = wf(src_rgba)
        GL = np.stack([wf(it['img']) for it in shown])
        yy, xx = np.mgrid[:H, :W]
        oc = np.clip(owner, 0, None)
        lf_in = R if lf_in is None else lf_in
        cand = line & (owner > 0) & (GL[oc, yy, xx] - Ls > lf_dark) & (dists[oc, yy, xx] > lf_in)
        dout = np.stack([distance_transform_edt(~(it['img'][..., 3] >= 128)).astype(np.float32) for it in shown])
        dout[np.arange(len(shown))[:, None, None] >= owner[None]] = np.inf
        dout[dout > line_front] = np.inf
        bestf = np.argmin(dout, 0)
        okf = cand & np.isfinite(dout.min(0))
        owner = np.where(okf, bestf, owner)
        for k, it in enumerate(shown):
            it['line_in_px'] = int((okf & (bestf == k)).sum())
            it['line_out_px'] = int((okf & (oc == k)).sum())
        del GL, dout
    soft = sil & (src_rgba[..., 3] < 250)
    # part boundaries of the final owner map (bd_px around a change of owner): used by bd_guard
    if bd_px:
        o32 = owner.astype(np.float32)
        ker = np.ones((2 * bd_px + 1, 2 * bd_px + 1), np.uint8)
        near_bd = (cv2.dilate(o32, ker) != -cv2.dilate(-o32, ker)) & sil
        wf2 = lambda x: (x[..., :3].astype(np.float32) * (x[..., 3:] / 255) + 255 * (1 - x[..., 3:] / 255)) @ np.float32([0.299, 0.587, 0.114])
        Ls2 = wf2(src_rgba)
    # guard masks per layer (computed on the owner map before hand-off)
    guards = []
    for k, it in enumerate(shown):
        im = it['img']
        inside = dists[k] > R
        far = np.abs(srgb - im[..., :3].astype(np.int16)).max(-1) > thr
        # stamp guard: inside the layer (> R px from its edge), an original outline pixel far from the
        # generated colour is another part's line -> do not copy it here
        gk = (owner == k) & (im[..., 3] >= 128) & inside & far & line
        if bd_px:  # bd_guard: next to another part, a pixel the original would make darker
            gk |= (owner == k) & (im[..., 3] >= 128) & inside & near_bd & (wf2(im) - Ls2 > 25)
        if not guard or not it.get('owner_guard', True):  # eyes: detail is all lines
            gk[:] = False
        guards.append(gk)
    handed = np.zeros(owner.shape, bool)
    if hand_px:
        # guarded pixels go to the nearest layer in front within hand_px (grown there with the original
        # colour) -> composite keeps the line, the back layer keeps its generated colour (hidden part)
        dout = np.stack([distance_transform_edt(~(it['img'][..., 3] >= 128)).astype(np.float32) for it in shown])
        for k in range(1, len(shown)):
            g = guards[k]
            if not g.any():
                continue
            dk = dout[:k][:, g]                     # (k, npx) distances of front layers
            j = np.argmin(dk, 0)
            ok = dk[j, np.arange(dk.shape[1])] <= hand_px
            gy, gx = np.nonzero(g)
            owner[gy[ok], gx[ok]] = j[ok]
            handed[gy[ok], gx[ok]] = True
            guards[k][gy[ok], gx[ok]] = False       # k is now behind the owner: keeps generated colour
        del dout
    for k, it in enumerate(shown):
        im = it['img']
        before = im[..., 3] > 15
        mine = owner == k
        front_of_owner = sil & (owner > k)     # owner is behind this layer -> this layer must not cover
        behind_soft = soft & (owner < k)
        keep_gen = guards[k] & mine
        im[front_of_owner | behind_soft | ~sil] = 0
        cp = mine & ~keep_gen
        im[cp] = src_rgba[cp]
        it['own_mask'] = cp
        it['kept_gen_px'] = int(keep_gen.sum())
        it['handed_in_px'] = int((handed & mine).sum())
        it['own_px'] = int(mine.sum())
        it['own_fallback_px'] = int((mine & ~any_good).sum())
        it['grown_px'] = int((mine & ~before).sum())
        it['cut_px'] = int((before & ~(im[..., 3] > 15)).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding='utf-8'))
    os.makedirs(osp.join(a.out, 'layers'), exist_ok=True)
    src_rgba = np.array(Image.open(spec['src']).convert('RGBA'))
    items = []
    for L in spec['layers']:
        im, d = build(L, src_rgba)
        items.append({**L, 'depth_median': round(d, 3), 'px': int((im[..., 3] > 15).sum()), 'img': im})
    items.sort(key=lambda x: x['depth_median'])  # front first
    align = spec.get('align', '')
    flow_info = flow_align(items, src_rgba) if 'flow' in align else None
    for it in items:
        it['gen'] = it['img'].copy()  # generated (and aligned) layer before any original colour
    if spec.get('visible_rgb') == 'owner':
        owner_assign(items, src_rgba, int(spec.get('rgb_thr', 60)), int(spec.get('owner_r', 2)),
                     sam='sam2' in align, guard=spec.get('owner_guard', True), line_front=int(spec.get('line_front', 0)),
                     bd_px=int(spec.get('bd_guard', 0)), hand_px=int(spec.get('guard_hand', 0)))
        bl = spec.get('blend')
        for it in items:
            if 'own_mask' in it and bl == 'poisson':
                poisson_blend(it, src_rgba)
            elif 'own_mask' in it and bl == 'poisson_seam':
                poisson_seam_blend(it, src_rgba, int(spec.get('seam_px', 8)))
    elif spec.get('visible_rgb') == 'src':
        # front to back, every shown layer takes the original colour on the pixels it shows; a
        # semi-transparent edge lets the next layer show through, so that layer takes it too, until an
        # opaque layer (alpha >= 250) closes the pixel. Removes generated edge lines/halos; parts hidden
        # under opaque layers keep their generated colour.
        # Guard (rgb_thr, default 60): the original colour is copied only where it is close to the
        # generated one. A big difference means the original shows another part there (a neighbour's
        # outline, because layer shapes from other seeds are off by 1-3px) -> copying would stamp that
        # line onto this layer, so the generated colour stays. A big difference on a semi-transparent
        # edge pixel is a generated halo -> that pixel is cleared instead.
        thr = int(spec.get('rgb_thr', 60))
        open_ = src_rgba[..., 3] > 15  # outside the original: nothing to copy
        for it in items:
            if it.get('hidden'):
                continue
            im = it['img']
            al = im[..., 3]
            own = (al >= 16) & open_
            if not it.get('keep_rgb'):  # keep_rgb: leave this layer's colour alone
                diff = np.abs(src_rgba[..., :3].astype(int) - im[..., :3]).max(-1)
                ok = own & (diff <= thr)
                halo = own & (diff > thr) & (al < 200)
                im[ok, :3] = src_rgba[ok, :3]
                im[halo] = 0
                it['src_px'], it['halo_px'], it['kept_px'] = int(ok.sum()), int(halo.sum()), int((own & ~ok & ~halo).sum())
            open_ &= ~(im[..., 3] >= 250)
    # "fill_missing" (give uncovered original pixels to the nearest layer) was removed on 2026-11-24:
    # generated layers sit 1-2px off the original, so the copied pixels became dotted outline slivers on
    # the layers. Uncovered original pixels now stay empty (missing_px in check.png / mix.json).
    if spec.get('fill_missing') or any(L.get('no_fill') for L in spec['layers']):
        print('[mix_layers] note: "fill_missing" / "no_fill" were removed and are ignored', flush=True)
    for it in items:
        if it.get('erase'):  # user mask (white = remove), applied last so nothing refills it
            em = np.array(Image.open(it['erase']).convert('L')) > 127
            it['erased_px'] = int((em & (it['img'][..., 3] > 15)).sum())
            it['img'][em] = 0
    os.makedirs(osp.join(a.out, 'gen'), exist_ok=True)
    for d in ('layers', 'gen'):
        for f in os.listdir(osp.join(a.out, d)):
            os.remove(osp.join(a.out, d, f))
    for i, it in enumerate(items):
        it['file'] = f"layers/{i:02d}_{it['name'].replace(' ', '_')}.png"
        Image.fromarray(it['img']).save(osp.join(a.out, it['file']))
        # gen/: the same layer as generated (+ aligned), before original colour -> reference for marks
        Image.fromarray(it['gen']).save(osp.join(a.out, it['file'].replace('layers/', 'gen/')))

    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    H, W = items[0]['img'].shape[:2]
    psd = PSDImage.new('RGBA', (W, H))
    for it in reversed(items):
        lay = PixelLayer.frompil(Image.fromarray(it['img']), psd, it['name'])
        if it.get('hidden'):
            lay.visible = False
        psd.append(lay)
    psd.save(osp.join(a.out, 'mix.psd'))

    comp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for it in reversed(items):
        if not it.get('hidden'):
            comp.alpha_composite(Image.fromarray(it['img']))
    comp.save(osp.join(a.out, 'composite.png'))
    src = np.array(Image.open(spec['src']).convert('RGBA'))
    c = np.array(comp)
    sa, ca = src[..., 3] > 15, c[..., 3] > 15
    white = lambda x: x[..., :3].astype(float) * (x[..., 3:] / 255) + 255 * (1 - x[..., 3:] / 255)
    mse = ((white(src) - white(c)) ** 2).mean()
    psnr = 10 * np.log10(255 ** 2 / mse)
    miss, extra = sa & ~ca, ca & ~sa
    diff = sa & ca & (np.abs(src[..., :3].astype(int) - c[..., :3]).max(-1) > 40)
    vis = (white(src).mean(-1, keepdims=True).repeat(3, -1) * 0.25 + 190).astype(np.uint8)
    vis[diff] = (240, 200, 0)
    vis[miss] = (230, 0, 0)
    vis[extra] = (0, 90, 230)
    ys, xs = np.nonzero(sa | ca)
    box = (max(xs.min() - 20, 0), max(ys.min() - 20, 0), min(xs.max() + 20, W), min(ys.max() + 20, H))
    panels = [Image.fromarray(src).crop(box), comp.crop(box), Image.fromarray(vis).crop(box).convert('RGBA')]
    pw, ph = panels[0].size
    chk = Image.new('RGB', (pw * 3, ph + 24), (255, 255, 255))
    for j, p in enumerate(panels):
        bg = checker(pw, ph)
        bg.alpha_composite(p)
        chk.paste(bg.convert('RGB'), (j * pw, 24))
    dr = ImageDraw.Draw(chk)
    for j, t in enumerate(['원본', '조합 합성',
                           f'빨강=빠짐 {int(miss.sum())}px  파랑=넘침 {int(extra.sum())}px  노랑=색 차이>40  PSNR {psnr:.1f}dB']):
        dr.text((j * pw + 4, 2), t, fill=(0, 0, 0), font=FONT)
    chk.save(osp.join(a.out, 'check.png'))

    T, cols = 200, 6
    rows = (len(items) + cols - 1) // cols
    sh = Image.new('RGB', (cols * T, rows * (T + 30)), (255, 255, 255))
    dr = ImageDraw.Draw(sh)
    for i, it in enumerate(items):
        al = it['img'][..., 3] > 15
        ys, xs = np.nonzero(al)
        if not len(xs):  # emptied layer (e.g. all its pixels went to another layer)
            ys, xs = np.array([0, H - 1]), np.array([0, W - 1])
        cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
        s = max(xs.max() - xs.min(), ys.max() - ys.min()) // 2 + 10
        cell = checker(T, T)
        cell.alpha_composite(Image.fromarray(it['img']).crop((cx - s, cy - s, cx + s, cy + s)).resize((T, T)))
        x, y = (i % cols) * T, (i // cols) * (T + 30)
        sh.paste(cell.convert('RGB'), (x, y + 30))
        run = osp.basename(it['run'].rstrip('/\\')).replace('miku_grow_', '').replace('miku_chibi_sprite', 'oldPC42')
        dr.text((x + 3, y + 0), f"{i:02d} {it['name']}{' (꺼짐)' if it.get('hidden') else ''}", fill=(0, 0, 0), font=FONT)
        dr.text((x + 3, y + 14), f"{run} 깊이={it['depth_median']:.2f}", fill=(0, 0, 200), font=FONT)
    sh.save(osp.join(a.out, 'sheet.png'))

    # hidden.png: each layer alone; green tint = the part covered by shown layers in front of it
    # (what appears when those layers move). A hole would show as checkerboard inside the outline.
    hs = Image.new('RGB', (cols * T, rows * (T + 30)), (255, 255, 255))
    dr = ImageDraw.Draw(hs)
    front = np.zeros(src_rgba.shape[:2], bool)
    for i, it in enumerate(items):
        al = it['img'][..., 3] > 15
        hid = al & front
        it['hidden_pct'] = round(100 * hid.sum() / max(al.sum(), 1), 1)
        v = it['img'].copy()
        v[hid, :3] = (v[hid, :3] * 0.45 + np.array([40, 200, 60]) * 0.55).astype(np.uint8)
        ys, xs = np.nonzero(al)
        if not len(xs):
            ys, xs = np.array([0, H - 1]), np.array([0, W - 1])
        cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
        s = max(xs.max() - xs.min(), ys.max() - ys.min()) // 2 + 10
        cell = checker(T, T)
        cell.alpha_composite(Image.fromarray(v).crop((cx - s, cy - s, cx + s, cy + s)).resize((T, T)))
        x, y = (i % cols) * T, (i // cols) * (T + 30)
        hs.paste(cell.convert('RGB'), (x, y + 30))
        dr.text((x + 3, y + 0), f"{i:02d} {it['name']}", fill=(0, 0, 0), font=FONT)
        dr.text((x + 3, y + 14), f"가려짐 {it['hidden_pct']:.0f}%{' (꺼짐)' if it.get('hidden') else ''}", fill=(0, 140, 0), font=FONT)
        if not it.get('hidden'):
            front |= it['img'][..., 3] >= 128
    hs.save(osp.join(a.out, 'hidden.png'))

    marks = 0
    for it in items:
        if not it.get('hidden'):
            it['marks_px'], _ = extra_edges(it)
            marks += it['marks_px']
    meta = [{k: v for k, v in it.items() if k not in ('img', 'gen', 'own_mask')} for it in items]
    json.dump({'spec': a.spec, 'psnr_white_db': round(psnr, 2), 'missing_px': int(miss.sum()),
               'extra_px': int(extra.sum()), 'marks_px': marks, 'flow': flow_info, 'layers_front_to_back': meta},
              open(osp.join(a.out, 'mix.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(items)} layers, PSNR {psnr:.1f}dB, missing {int(miss.sum())}px, extra {int(extra.sum())}px, '
          f'marks {marks}px, flow {flow_info} -> {a.out}')
    for i, it in enumerate(items):
        print(f"  {i:02d} {it['name']:14s} d={it['depth_median']:.3f} {it['px']:7d}px {osp.basename(it['run'])}")


if __name__ == '__main__':
    main()
