"""Cut one layer into two rig pieces at a joint (knee, elbow, ...) so that bending does not open a gap.

  python split_joint.py --layer legwear-l.png --at 0.5 --out_dir legs --names thigh,shin
  python split_joint.py --layer arm.png --cut 400,520,470,540 --out_dir arm --names upper,lower

  - The cut is a straight line across the part. --at t puts it at fraction t along the part's long axis
    (0 = top end, 1 = bottom end), perpendicular to that axis; --cut x0,y0,x1,y1 gives it directly.
  - "first" piece = side of the line containing the top end (--at) or the side the --first_side point
    is on; "second" piece = the other side.
  - --front second (default): the second (lower) piece is drawn in front, e.g. shin over thigh,
    forearm over upper arm. The front piece gets a joint cap: the other piece's original pixels within
    (--cap - --line_px) px of the pivot (middle of the cut inside the part), with no outline.
  - The cap's outline ring goes to <front>_joint_line.png: attach it to the front piece's bone but draw it
    BEHIND the back piece. Straight, the back piece hides it (looks exactly like the original); bent, only
    the part of the ring that sticks out over the background shows. (--cap 0 disables cap and ring.)
  - Writes <out_dir>/<name1>.png, <name2>.png (full canvas, same size as the layer), joint.json
    (pivot, cut, axis, draw order) and joint_check.png (pieces + bends of -60..60 degrees around the pivot).
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layer_common import bleed  # noqa: E402

FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 14)


def axis_of(alpha):
    ys, xs = np.nonzero(alpha)
    pts = np.stack([xs, ys], 1).astype(np.float64)
    c = pts.mean(0)
    w, v = np.linalg.eigh(np.cov((pts - c).T))
    d = v[:, np.argmax(w)]
    if d[1] < 0:  # point "down" the image
        d = -d
    t = (pts - c) @ d
    return c, d, t.min(), t.max()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--at', type=float, default=None, help='cut at this fraction along the long axis (0 top, 1 bottom)')
    ap.add_argument('--cut', default=None, help='x0,y0,x1,y1 of the cut line (overrides --at)')
    ap.add_argument('--first_side', default=None, help='x,y of a point on the first piece (with --cut)')
    ap.add_argument('--cap', type=int, default=-1, help='joint cap radius in px (default: half the part width at the cut)')
    ap.add_argument('--line_px', type=int, default=4, help='outline width of the joint cap arc')
    ap.add_argument('--front', choices=['first', 'second'], default='second',
                    help='which piece is drawn in front and gets the joint cap (default: second = lower piece)')
    ap.add_argument('--out_dir', required=True)
    ap.add_argument('--names', default='upper,lower')
    ap.add_argument('--pivot', default=None,
                    help='x,y joint centre to use instead of the middle of the cut (e.g. share one elbow between sleeve and arm)')
    a = ap.parse_args()

    img = np.asarray(Image.open(a.layer).convert('RGBA'))
    H, W = img.shape[:2]
    alpha = img[..., 3] > 16
    c, d, tmin, tmax = axis_of(alpha)
    if a.cut:
        x0, y0, x1, y1 = [float(v) for v in a.cut.split(',')]
        p0, p1 = np.array([x0, y0]), np.array([x1, y1])
        n = np.array([-(y1 - y0), x1 - x0]); n /= np.linalg.norm(n)
        if a.first_side:
            fs = np.array([float(v) for v in a.first_side.split(',')])
        else:
            fs = c + d * tmin  # top end
        if (fs - p0) @ n > 0:
            n = -n  # n points from the first piece to the second
        mid = (p0 + p1) / 2
    else:
        t = tmin + (tmax - tmin) * (0.5 if a.at is None else a.at)
        mid = c + d * t
        n = d.copy()
        p0 = p1 = None
    yy, xx = np.mgrid[0:H, 0:W]
    side = (xx - mid[0]) * n[0] + (yy - mid[1]) * n[1]  # <0 first piece, >=0 second piece
    # pivot = middle of the part along the cut line
    on_line = alpha & (np.abs(side) < 1.0)
    if on_line.sum() == 0:
        raise SystemExit('cut line does not cross the part')
    ly, lx = np.nonzero(on_line)
    tang = np.array([-n[1], n[0]])
    s = (lx - mid[0]) * tang[0] + (ly - mid[1]) * tang[1]
    pivot = mid + tang * (s.min() + s.max()) / 2
    if a.pivot:
        pivot = np.array([float(v) for v in a.pivot.split(',')])
    width = float(s.max() - s.min())
    cap = int(round(width / 2)) if a.cap < 0 else a.cap
    if p0 is None:
        p0, p1 = pivot - tang * width / 2, pivot + tang * width / 2

    first = alpha & (side < 0)
    second = alpha & (side >= 0)
    names = a.names.split(',')
    os.makedirs(a.out_dir, exist_ok=True)
    pieces = {}
    for nm, m in zip(names, (first, second)):
        out = np.zeros_like(img)
        out[m] = img[m]
        pieces[nm] = out
    front = names[1] if a.front == 'second' else names[0]
    back = names[0] if front == names[1] else names[1]
    line_layer = None
    if cap > 0:
        # joint cap on the FRONT piece: the other piece's original pixels within (cap - line_px) of the pivot,
        # WITHOUT an outline. The outline ring (cap - line_px .. cap) goes to a separate layer that is drawn
        # BEHIND the back piece and moves with the front piece: straight, the back piece hides it; bent, only
        # the part that sticks out over the background shows.
        import cv2
        rr = np.sqrt((xx - pivot[0]) ** 2 + (yy - pivot[1]) ** 2)
        other_side = (side < 0) if front == names[1] else (side >= 0)
        r_in = cap - a.line_px
        capm = (rr <= r_in) & alpha & other_side
        inner = cv2.erode(alpha.astype(np.uint8), np.ones((2 * a.line_px + 3,) * 2, np.uint8)).astype(bool)
        lum = img[..., :3].astype(np.float32).mean(2)
        near = alpha & (rr <= cap * 1.5) & ~inner  # outline pixels of the part near the joint
        line = np.median(img[near & (lum < 40), :3], axis=0) if (near & (lum < 40)).sum() > 10 else np.array([15, 15, 15])
        pieces[front][capm] = img[capm]
        # back piece: also keeps the front side's original pixels within cap px (hidden behind the front piece
        # when straight); when bent it fills the notch on the inner side of the joint
        backm = (rr <= cap) & alpha & ~other_side
        pieces[back][backm] = img[backm]
        # ring: starts 1px inside the cap (no see-through seam), soft outer edge, only inside the part so it
        # never sticks out when straight
        cov = np.clip(np.minimum(rr - (r_in - 1.5), (cap + 0.5) - rr), 0, 1) * other_side * alpha
        line_layer = np.zeros_like(img)
        line_layer[..., :3] = line.astype(np.uint8)
        line_layer[..., 3] = (cov * 255).astype(np.uint8)
        print(f'[cap] on {front}: fill r={r_in}px {int(capm.sum())}px, ring {r_in}..{cap}px {int((cov > 0).sum())}px colour={line.astype(int).tolist()}')
    for nm in names:
        pieces[nm] = bleed(pieces[nm])  # transparent pixels get the edge colour (no dark/white fringe when rotated)
        Image.fromarray(pieces[nm]).save(os.path.join(a.out_dir, nm + '.png'))
    if line_layer is not None:
        Image.fromarray(line_layer).save(os.path.join(a.out_dir, front + '_joint_line.png'))
    order = [front, back] + ([front + '_joint_line'] if line_layer is not None else [])
    info = {'layer': os.path.basename(a.layer), 'pivot': [round(float(v), 1) for v in pivot],
            'cut': [round(float(v), 1) for v in (*p0, *p1)], 'width_px': round(width, 1), 'cap_px': cap,
            'line_px': a.line_px, 'axis': [round(float(v), 3) for v in d],
            'pieces': {nm: int((pieces[nm][..., 3] > 16).sum()) for nm in names},
            'order_front_to_back': order,
            'note': f'{front}_joint_line moves with {front} (same bone) but is drawn behind {back}'}
    json.dump(info, open(os.path.join(a.out_dir, 'joint.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))
    check(a.out_dir, img, pieces[names[0]], pieces[names[1]], line_layer, pivot, p0, p1, names, front == names[1])


def check(out_dir, img, first, second, line_layer, pivot, p0, p1, names, second_front=True):
    ys, xs = np.nonzero(img[..., 3] > 16)
    pad = 60
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(img.shape[1], xs.max() + pad), min(img.shape[0], ys.max() + pad)

    def chk(a):
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        bg = np.where(((yy // 8 + xx // 8) % 2)[..., None] == 0, 255, 215).astype(np.uint8).repeat(3, 2)
        im = Image.fromarray(bg).convert('RGBA')
        im.alpha_composite(Image.fromarray(a))
        return im.convert('RGB')

    cells = []
    orig = chk(img); dr = ImageDraw.Draw(orig)
    dr.line([tuple(p0), tuple(p1)], fill=(255, 0, 0), width=2)
    dr.ellipse([pivot[0] - 4, pivot[1] - 4, pivot[0] + 4, pivot[1] + 4], outline=(255, 0, 0), width=2)
    cells.append(('원본 + 자르는 선', orig))
    cells.append((names[0] + ('' if second_front else ' (앞, 캡)'), chk(first)))
    cells.append((names[1] + (' (앞, 캡)' if second_front else ''), chk(second)))
    if line_layer is not None:
        cells.append(('관절 외곽선 (맨 뒤)', chk(line_layer)))
    front, back = (second, first) if second_front else (first, second)
    for ang in (0, -60, -30, 30, 60):
        rot2 = Image.fromarray(second).rotate(ang, resample=Image.BILINEAR, center=tuple(pivot))
        f_im = rot2 if second_front else Image.fromarray(first)
        b_im = Image.fromarray(first) if second_front else rot2
        comp = Image.new('RGBA', rot2.size, (0, 0, 0, 0))
        if line_layer is not None:
            ll = Image.fromarray(line_layer)
            if second_front:
                ll = ll.rotate(ang, resample=Image.BILINEAR, center=tuple(pivot))
            comp.alpha_composite(ll)
        comp.alpha_composite(b_im); comp.alpha_composite(f_im)
        cells.append(('곧게 (0°)' if ang == 0 else f'{names[1]} {ang:+d}°', chk(np.asarray(comp))))
    cw, chh = x1 - x0, y1 - y0
    sheet = Image.new('RGB', (cw * len(cells), chh + 24), 'white')
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(cells):
        sheet.paste(im.crop((x0, y0, x1, y1)), (i * cw, 24))
        d.text((i * cw + 4, 3), t, font=FONT, fill='black')
    sheet.save(os.path.join(out_dir, 'joint_check.png'))


if __name__ == '__main__':
    main()
