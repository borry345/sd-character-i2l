"""See-through 결과를 단계별로 검토하는 이미지를 만든다 (모델 실행 없음, 기존 파일만 읽음).

  python review_seethrough.py --run seethrough_test\\miku_chibi_sprite [--src miku_chibi_sprite.png] [--res 1024]

--run  : run_seethrough.ps1의 -OutDir 폴더 (<이름>.psd, <이름>\\ 중간 파일이 있는 곳)
--src  : 원본 이미지. 생략하면 i2l\\<이름>.png
출력   : <run>\\review\\ 아래 PNG + review.md(파일 목록·만든 방법·수치)

  step20_preprocess.png   2-0 원본 vs src_img.png (정사각형 패딩·축소)
  step21_body_tags.png    2-1 LayerDiff 몸 단계 13태그 (빈 레이어는 빨간 글씨)
  step22_head_crop.png    2-2 head.png 범위(초록) · 실제 자르기 상자(빨강) · headwear(보라)
  step23_head_tags.png    2-3 LayerDiff 머리 단계 11태그
  step24_depth.png        2-4 PSD 레이어를 가까운 순서로, 깊이를 색으로(빨강=가까움, 파랑=멂)
  step25_psd_stack.png    2-5 PSD 레이어를 아래부터 쌓는 과정 + 레이어 픽셀 출처(생성/원본)
  step26_coverage.png     2-6 원본 vs PSD 합성: 빠진 곳(빨강)·남는 곳(파랑)·색 차이(노랑)
  step27_hidden_parts.png 8⑤ 레이어를 혼자 띄우고 앞 레이어에 가려지는 부분을 초록으로
  stages_strip.png        src_img · head · src_head · face_depth · back hair_depth · reconstruction
"""
import argparse
import json
import os
import os.path as osp

import cv2
import numpy as np
from PIL import Image, ImageDraw

I2L = osp.dirname(osp.dirname(osp.abspath(__file__)))
BODY = ['front hair', 'back hair', 'head', 'neck', 'neckwear', 'topwear', 'handwear',
        'bottomwear', 'legwear', 'footwear', 'tail', 'wings', 'objects']
HEAD = ['headwear', 'face', 'irides', 'eyebrow', 'eyewhite', 'eyelash', 'eyewear',
        'ears', 'earwear', 'nose', 'mouth']


def checker(w, h, cell=16):
    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(225, 225, 225, 255))
    return bg


def on_checker(im):
    bg = checker(*im.size)
    bg.alpha_composite(im.convert('RGBA'))
    return bg


def alpha_px(path):
    a = np.array(Image.open(path).convert('RGBA'))
    return int((a[..., 3] > 15).sum())


def flat_white(x):
    x = x.astype(np.float64)
    al = x[..., 3:] / 255
    return x[..., :3] * al + 255 * (1 - al)


def psnr(a, b):
    m = ((flat_white(a) - flat_white(b)) ** 2).mean()
    return float('inf') if m == 0 else 10 * np.log10(255 ** 2 / m)


def char_box(mid, margin=40):
    a = np.array(Image.open(osp.join(mid, 'src_img.png')).convert('RGBA'))[..., 3] > 15
    ys, xs = np.nonzero(a)
    s = max(xs.max() - xs.min(), ys.max() - ys.min()) // 2 + margin
    cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
    return (cx - s, cy - s, cx + s, cy + s)


def tag_sheet(mid, tags, box, out, cols=5, T=300):
    rows = (len(tags) + 1 + cols - 1) // cols
    W = Image.new('RGB', (cols * T, rows * (T + 22)), (255, 255, 255))
    d = ImageDraw.Draw(W)
    counts = {}
    items = [(t, osp.join(mid, f'{t}.png')) for t in tags] + [('(ref) src_img', osp.join(mid, 'src_img.png'))]
    for i, (t, p) in enumerate(items):
        x, y = (i % cols) * T, (i // cols) * (T + 22)
        if not osp.exists(p):
            d.text((x + 4, y + 5), f'{t}  (없음)', fill=(200, 0, 0))
            continue
        n = alpha_px(p)
        if not t.startswith('(ref)'):
            counts[t] = n
        im = on_checker(Image.open(p).convert('RGBA').crop(box).resize((T, T)))
        W.paste(im.convert('RGB'), (x, y + 22))
        d.rectangle([x, y + 22, x + T - 1, y + 22 + T - 1], outline=(160, 160, 160))
        color = (0, 0, 200) if t.startswith('(ref)') else (200, 0, 0) if n == 0 else (0, 0, 0)
        d.text((x + 4, y + 5), f'{t}  {n:,}px', fill=color)
    W.save(out)
    return counts


def head_crop_box(src, mid, res):
    """inference_psd_quantized.py run_layerdiff의 머리 자르기 계산을 그대로 재현."""
    H, W = src.shape[:2]
    S = max(H, W)
    scale = S / res
    padx, pady = (S - W) // 2, (S - H) // 2
    head = np.array(Image.open(osp.join(mid, 'head.png')).convert('RGBA'))
    x0, y0, w, h = cv2.boundingRect(cv2.findNonZero((head[..., 3] > 15).astype(np.uint8)))
    hx, hy = int(x0 * scale) - padx, int(y0 * scale) - pady
    hw, hh = int(w * scale), int(h * scale)
    x1, y1, x2, y2 = hx, hy, hx + hw, hy + hh
    if hw < W // 2:
        px = min(W - hx - hw, hx, hw // 5)
        x1, x2 = min(max(hx - px, 0), W), min(max(hx + hw + px, 0), W)
    if hh < H // 2:
        py = min(H - hy - hh, hy, hh // 5)
        y1, y2 = min(max(hy - py, 0), H), min(max(hy + hh + py, 0), H)
    crop1024 = [(x1 + padx) / scale, (y1 + pady) / scale, (x2 + padx) / scale, (y2 + pady) / scale]
    return (x0, y0, x0 + w, y0 + h), crop1024, (padx, pady)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--src', default=None)
    ap.add_argument('--res', type=int, default=1024)
    args = ap.parse_args()

    run = osp.abspath(args.run)
    psds = [f for f in os.listdir(run) if f.endswith('.psd') and not f.endswith('_depth.psd')]
    name = psds[0][:-4] if psds else osp.basename(run.rstrip('\\/'))  # image name, not run folder name
    mid = osp.join(run, name)
    src_path = args.src or osp.join(I2L, f'{name}.png')
    out = osp.join(run, 'review')
    os.makedirs(out, exist_ok=True)
    src = np.array(Image.open(src_path).convert('RGBA'))
    md = [f'# {name} See-through 단계별 검토', '',
          f'- 만든 도구: `tools/review_seethrough.py --run {args.run}` (모델 실행 없음, 기존 파일만 읽음)',
          f'- 원본: `{src_path}` ({src.shape[1]}x{src.shape[0]})', f'- 중간 파일: `{mid}`', '']

    # 2-0
    A = on_checker(Image.fromarray(src))
    A = A.resize((round(A.width * 512 / max(A.size)), round(A.height * 512 / max(A.size))))
    B = on_checker(Image.open(osp.join(mid, 'src_img.png'))).resize((512, 512))
    Wd = Image.new('RGB', (A.width + 552, 552), (255, 255, 255))
    Wd.paste(A.convert('RGB'), (0, 30))
    Wd.paste(B.convert('RGB'), (A.width + 40, 30))
    d = ImageDraw.Draw(Wd)
    d.text((4, 8), f'original {src.shape[1]}x{src.shape[0]}', fill=(0, 0, 0))
    d.text((A.width + 44, 8), f'src_img.png {args.res}x{args.res}', fill=(0, 0, 0))
    d.rectangle([A.width + 40, 30, A.width + 551, 541], outline=(255, 0, 0), width=2)
    Wd.save(osp.join(out, 'step20_preprocess.png'))
    S = max(src.shape[:2])
    md += ['## step20_preprocess.png (2-0 전처리)',
           f'- 긴 변 {S}에 맞춰 정사각형 패딩(좌우 {(S - src.shape[1]) // 2}px, 위아래 {(S - src.shape[0]) // 2}px) → {args.res}로 축소 ({args.res / S:.2f}배)', '']

    box = char_box(mid)

    # 2-1
    body = tag_sheet(mid, BODY, box, osp.join(out, 'step21_body_tags.png'))
    empty = [t for t, n in body.items() if n == 0]
    md += ['## step21_body_tags.png (2-1 LayerDiff 몸 단계)',
           '| 태그 | 픽셀 |', '|---|---|'] + [f'| {t} | {n:,} |' for t, n in body.items()] + \
          ['', f'- 빈 레이어 {len(empty)}개: {", ".join(empty) or "없음"}', '']

    # 2-2
    hb, crop, _ = head_crop_box(src, mid, args.res)
    hgp = osp.join(mid, 'head_grow.json')
    grow_passes = json.load(open(hgp))['passes'] if osp.exists(hgp) else []
    if grow_passes:  # head_grow run: real crop of the last pass (earlier passes drawn thin orange)
        crop = grow_passes[-1]['crop_1024']
    base = Image.new('RGBA', (args.res, args.res), (255, 255, 255, 255))
    base.alpha_composite(Image.open(osp.join(mid, 'src_img.png')).convert('RGBA'))
    hwp = osp.join(mid, 'headwear.png')
    cut = {}
    if osp.exists(hwp):
        hw = np.array(Image.open(hwp).convert('RGBA'))
        m = hw.copy()
        m[..., :3] = [255, 0, 255]
        m[..., 3] = (hw[..., 3] > 15) * 160
        base.alpha_composite(Image.fromarray(m))
        ys, xs = np.nonzero(hw[..., 3] > 15)
        if len(xs):
            hwb = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
            cx = [round(v) for v in crop]
            cut = {'left': hwb[0] <= cx[0] + 1, 'top': hwb[1] <= cx[1] + 1,
                   'right': hwb[2] >= cx[2] - 2, 'bottom': hwb[3] >= cx[3] - 2}
    d = ImageDraw.Draw(base)
    for gp_ in grow_passes[:-1]:
        d.rectangle(gp_['crop_1024'], outline=(255, 150, 0, 255), width=2)
    d.rectangle(crop, outline=(255, 0, 0, 255), width=4)
    d.rectangle(hb, outline=(0, 160, 0, 255), width=3)
    pad = 120
    cb = (max(int(crop[0]) - pad, 0), max(int(crop[1]) - pad, 0),
          min(int(crop[2]) + pad, args.res), min(int(crop[3]) + pad, args.res))
    base.crop(cb).convert('RGB').save(osp.join(out, 'step22_head_crop.png'))
    md += ['## step22_head_crop.png (2-2 머리 자르기)',
           '- 초록: head.png 범위 / 빨강: 실제 자르기 상자(여백 1/5, 코드 계산 재현) / 보라: headwear.png',
           f'- head 범위(1024): {hb}, 자르기 상자(1024): {[round(v) for v in crop]}',
           f'- headwear가 상자 경계에 닿은 쪽(잘림 의심): {", ".join(k for k, v in cut.items() if v) or "없음"}', ''] +           ([f'- head_grow {len(grow_passes)}회 (주황=이전 회차 상자): ' + ' → '.join(
              f"{p_['pass']}:{p_['crop_1024']} 닿음={sorted(p_['touching'])} 확장={p_['grow']}" for p_ in grow_passes), '']
           if grow_passes else [])

    # 2-3
    head = tag_sheet(mid, HEAD, box, osp.join(out, 'step23_head_tags.png'))
    empty = [t for t, n in head.items() if n == 0]
    md += ['## step23_head_tags.png (2-3 LayerDiff 머리 단계)',
           '| 태그 | 픽셀 |', '|---|---|'] + [f'| {t} | {n:,} |' for t, n in head.items()] + \
          ['', f'- 빈 레이어 {len(empty)}개: {", ".join(empty) or "없음"}', '']

    # 2-4
    pj = osp.join(run, f'{name}.psd.json')
    info = json.load(open(pj, encoding='utf-8'))['parts']
    order = sorted(info.items(), key=lambda kv: kv[1]['depth_median'])
    T, cols = 230, 7
    rows = (len(order) + cols - 1) // cols + 1
    Wd = Image.new('RGB', (cols * T, rows * (T + 20)), (255, 255, 255))
    d = ImageDraw.Draw(Wd)
    cm = lambda dep: cv2.applyColorMap(dep, cv2.COLORMAP_TURBO)[..., ::-1]
    for i, (t, v) in enumerate(order):
        tb = t if osp.exists(osp.join(mid, f'{t}.png')) else t.rsplit('-', 1)[0]  # tblr_split: handwear-l -> handwear
        im = np.array(Image.open(osp.join(mid, f'{tb}.png')).convert('RGBA'))
        dep = np.array(Image.open(osp.join(mid, f'{tb}_depth.png')).convert('L'))
        if tb != t:  # keep only this side's box
            bx = np.zeros(im.shape[:2], bool); bx[v['xyxy'][1]:v['xyxy'][3], v['xyxy'][0]:v['xyxy'][2]] = True
            im[~bx, 3] = 0
        col = cm(255 - dep)
        a = im[..., 3] > 15
        o = np.full((*a.shape, 3), 40, np.uint8)
        o[a] = col[a]
        x0, y0, x1, y1 = v['xyxy']
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        s = max(x1 - x0, y1 - y0) // 2 + 20
        x, y = (i % cols) * T, (i // cols) * (T + 20)
        Wd.paste(Image.fromarray(o).crop((cx - s, cy - s, cx + s, cy + s)).resize((T, T)), (x, y + 20))
        d.text((x + 3, y + 4), f'{i + 1}. {t}  d={v["depth_median"]:.2f}', fill=(0, 0, 0))
    y = (rows - 1) * (T + 20)
    for j, n in enumerate(['src_img.png', 'reconstruction.png']):
        im = on_checker(Image.open(osp.join(mid, n)).convert('RGBA').crop(box).resize((T, T)))
        Wd.paste(im.convert('RGB'), (j * T, y + 20))
        d.text((j * T + 3, y + 4), n, fill=(0, 0, 200))
    bar = cm(np.tile(np.linspace(255, 0, 256).astype(np.uint8), (20, 1)))
    Wd.paste(Image.fromarray(bar).resize((3 * T, 20)), (3 * T, y + 120))
    d.text((3 * T, y + 100), 'near(0) <-  depth  -> far(1)', fill=(0, 0, 0))
    Wd.save(osp.join(out, 'step24_depth.png'))
    rp = psnr(np.array(Image.open(osp.join(mid, 'src_img.png')).convert('RGBA')),
              np.array(Image.open(osp.join(mid, 'reconstruction.png')).convert('RGBA')))
    md += ['## step24_depth.png (2-4 Marigold 깊이)',
           '- PSD 레이어를 깊이 중앙값(psd.json) 순서로 배치, 레이어 안은 <태그>_depth.png를 색으로 표시',
           '| 순서 | 레이어 | 깊이 중앙값 |', '|---|---|---|'] + \
          [f'| {i + 1} | {t} | {v["depth_median"]:.3f} |' for i, (t, v) in enumerate(order)] + \
          ['', f'- reconstruction.png vs src_img.png PSNR(흰 배경): {rp:.1f} dB', '']

    # 2-5
    from psd_tools import PSDImage
    psd = PSDImage.open(osp.join(run, f'{name}.psd'))
    srcimg = np.array(Image.open(osp.join(mid, 'src_img.png')).convert('RGBA')).astype(int)
    layers = list(psd)
    T, cols = 230, 7
    rows = (len(layers) + cols - 1) // cols
    Wd = Image.new('RGB', (cols * T, rows * (T + 20)), (255, 255, 255))
    d = ImageDraw.Draw(Wd)
    canvas = Image.new('RGBA', psd.size, (0, 0, 0, 0))
    rows_md = []
    for i, l in enumerate(layers):
        im = l.topil().convert('RGBA')
        x0, y0, x1, y1 = l.bbox
        canvas.alpha_composite(im, (x0, y0))
        a = np.array(im).astype(int)
        m = a[..., 3] > 15
        gp = osp.join(mid, f'{l.name}.png')
        if not osp.exists(gp):  # tblr_split layer (handwear-l) -> source tag PNG
            gp = osp.join(mid, f'{l.name.rsplit("-", 1)[0]}.png')
        dg = np.abs(a[..., :3] - np.array(Image.open(gp).convert('RGBA')).astype(int)[y0:y1, x0:x1, :3])[m].mean() if osp.exists(gp) else float('nan')
        ds = np.abs(a[..., :3] - srcimg[y0:y1, x0:x1, :3])[m].mean()
        src_kind = '원본 픽셀' if ds < 1 else '생성 PNG' if dg < 1 else '?'
        rows_md.append(f'| {i} | {l.name} | {l.bbox} | {int(m.sum()):,} | {dg:.1f} | {ds:.1f} | {src_kind} |')
        x, y = (i % cols) * T, (i // cols) * (T + 20)
        th = on_checker(canvas.crop(box).resize((T, T)))
        dd = ImageDraw.Draw(th)
        sx, sy = T / (box[2] - box[0]), T / (box[3] - box[1])
        dd.rectangle([(x0 - box[0]) * sx, (y0 - box[1]) * sy, (x1 - box[0]) * sx, (y1 - box[1]) * sy], outline=(255, 0, 0, 255), width=2)
        Wd.paste(th.convert('RGB'), (x, y + 20))
        d.text((x + 3, y + 4), f'+{i}. {l.name}', fill=(0, 0, 0))
    Wd.save(osp.join(out, 'step25_psd_stack.png'))
    pp = psnr(srcimg.astype(np.uint8), np.array(canvas))
    md += ['## step25_psd_stack.png (2-5 PSD 조립)',
           f'- PSD 레이어 {len(layers)}개를 아래(먼 쪽)부터 하나씩 쌓아 가는 모습, 빨간 상자 = 방금 추가한 레이어 범위',
           '- 생성PNG차이/원본차이: 레이어 픽셀 RGB 평균 차이 (0이면 그 파일 그대로)',
           '| PSD 순서(아래→위) | 레이어 | bbox | 픽셀 | 생성PNG 차이 | 원본 차이 | 픽셀 출처 |',
           '|---|---|---|---|---|---|---|'] + rows_md + \
          ['', f'- PSD 전체 합성 vs src_img.png PSNR(흰 배경): {pp:.1f} dB', '']

    # 2-6 coverage: 원본엔 있는데 PSD 합성에 없는 곳(빨강) / 반대(파랑) / 둘 다 있는 곳의 색 차이(회색→노랑)
    comp = np.array(canvas).astype(int)
    sa, ca = srcimg[..., 3] > 128, comp[..., 3] > 128
    missing, extra, both = sa & ~ca, ca & ~sa, sa & ca
    cd = np.abs(flat_white(srcimg) - flat_white(comp)).mean(-1)
    vis = np.full((*sa.shape, 3), 255, np.uint8)
    g = (255 - np.clip(cd * 3, 0, 200)).astype(np.uint8)
    vis[both] = np.stack([g, g, g], -1)[both]
    vis[both & (cd > 40)] = [255, 200, 0]
    vis[missing] = [230, 0, 0]
    vis[extra] = [0, 90, 255]
    vi = Image.fromarray(vis)
    ImageDraw.Draw(vi).rectangle(crop, outline=(0, 160, 0), width=3)
    A = on_checker(Image.fromarray(srcimg.astype(np.uint8)).crop(box)).resize((512, 512))
    B = on_checker(canvas.crop(box)).resize((512, 512))
    C = vi.crop(box).resize((512, 512))
    Wd = Image.new('RGB', (1536 + 40, 560), (255, 255, 255))
    d = ImageDraw.Draw(Wd)
    for j, (im, t) in enumerate([(A, 'src_img'), (B, 'PSD composite'),
                                 (C, 'red=missing  blue=extra  yellow=color diff>40  green=head crop')]):
        Wd.paste(im.convert('RGB'), (j * 532, 30))
        d.text((j * 532 + 4, 8), t, fill=(0, 0, 0))
    Wd.save(osp.join(out, 'step26_coverage.png'))
    n_lab, lab, st, _ = cv2.connectedComponentsWithStats(missing.astype(np.uint8), connectivity=8)
    big = sorted([tuple(int(v) for v in s) for s in st[1:]], key=lambda s: -s[4])[:5]
    md += ['## step26_coverage.png (2-6 품질: 어디가 빠졌나)',
           f'- 원본에만 있음(빠짐, 빨강): {int(missing.sum()):,}px / PSD에만 있음(파랑): {int(extra.sum()):,}px / 둘 다: {int(both.sum()):,}px',
           f'- 둘 다 있는 곳 중 색 차이 > 40: {int((both & (cd > 40)).sum()):,}px',
           '- 빠진 덩어리 큰 순서 (x, y, w, h, 픽셀): ' + ', '.join(str(b) for b in big),
           '- 초록 상자 = 2-2 머리 자르기 상자 (상자 밖의 머리 장식은 생성되지 않음)', '']

    # 8⑤ hidden parts: 레이어를 혼자 띄우고, 앞 레이어에 가려지는 부분을 초록으로 표시
    full = []
    for l in layers:
        f = Image.new('RGBA', psd.size, (0, 0, 0, 0))
        f.alpha_composite(l.topil().convert('RGBA'), l.bbox[:2])
        full.append(np.array(f))
    T, cols = 260, 5
    order_top = list(range(len(layers)))[::-1]  # 위(앞) → 아래(뒤)
    rows = (len(order_top) + cols - 1) // cols
    Wd = Image.new('RGB', (cols * T, rows * (T + 20)), (255, 255, 255))
    d = ImageDraw.Draw(Wd)
    rows_md = []
    for k, i in enumerate(order_top):
        a = full[i]
        own = a[..., 3] > 15
        cover = np.zeros_like(own)
        for j in range(i + 1, len(layers)):
            cover |= full[j][..., 3] >= 16
        hidden = own & cover
        view = np.array(on_checker(Image.fromarray(a))).copy()
        view[hidden, :3] = (view[hidden, :3] * 0.5 + np.array([0, 200, 0]) * 0.5).astype(np.uint8)
        x0, y0, x1, y1 = layers[i].bbox
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        s = max(x1 - x0, y1 - y0) // 2 + 15
        th = Image.fromarray(view).crop((cx - s, cy - s, cx + s, cy + s)).resize((T, T))
        x, y = (k % cols) * T, (k // cols) * (T + 20)
        Wd.paste(th.convert('RGB'), (x, y + 20))
        pct = 100 * hidden.sum() / max(own.sum(), 1)
        d.text((x + 3, y + 4), f'{layers[i].name}  hidden {pct:.0f}%', fill=(0, 0, 0))
        rows_md.append(f'| {layers[i].name} | {int(own.sum()):,} | {int(hidden.sum()):,} | {pct:.0f}% |')
    Wd.save(osp.join(out, 'step27_hidden_parts.png'))
    md += ['## step27_hidden_parts.png (8⑤ 가려진 부분 확인)',
           '- 각 레이어를 혼자 띄움, 초록 = 그 위 레이어들에 가려지는 부분(앞 레이어를 움직이면 드러날 곳)',
           '| 레이어(앞→뒤) | 픽셀 | 가려지는 픽셀 | 비율 |', '|---|---|---|---|'] + rows_md + ['']

    # strip
    names =['src_img.png', 'head.png', 'src_head.png', 'face_depth.png', 'back hair_depth.png', 'reconstruction.png']
    Wd = Image.new('RGB', (384 * len(names), 404), (255, 255, 255))
    d = ImageDraw.Draw(Wd)
    for i, n in enumerate(names):
        p = osp.join(mid, n)
        if osp.exists(p):
            Wd.paste(on_checker(Image.open(p).convert('RGBA').resize((384, 384))).convert('RGB'), (384 * i, 20))
        d.text((384 * i + 4, 4), n, fill=(0, 0, 0))
    Wd.save(osp.join(out, 'stages_strip.png'))
    md += ['## stages_strip.png', f'- {" · ".join(names)}', '']

    with open(osp.join(out, 'review.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print('wrote', out)
    for f in sorted(os.listdir(out)):
        print('  ', f)


if __name__ == '__main__':
    main()
