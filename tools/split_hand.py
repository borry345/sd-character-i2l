"""Take the hand (skin below a sleeve) out of a sleeve layer as its own rig piece.

  python split_hand.py --layer forearm.png --out_dir arm --names sleeve,hand

  1. hand = skin-coloured pixels in the lower part of the layer (--lower: fraction of the height),
     plus the outline pixels next to them that are not sleeve colour.
  2. sleeve = the rest.
  3. The hand is drawn just BEHIND the sleeve. It gets a hidden "wrist" extension: skin colour going up
     into the sleeve (disc around the wrist point), only where the sleeve covers it, so turning the hand a
     little around the wrist does not open a gap at the sleeve hem.
  Writes <sleeve>.png, <hand>.png, hand.json (wrist pivot, order) and hand_check.png (hand rotated -30..30).
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 14)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layer', required=True)
    ap.add_argument('--out_dir', required=True)
    ap.add_argument('--names', default='sleeve,hand')
    ap.add_argument('--lower', type=float, default=0.35, help='look for the hand in this bottom fraction of the layer')
    ap.add_argument('--line_px', type=int, default=4, help='outline width taken with the hand')
    ap.add_argument('--hem_px', type=int, default=-1,
                    help='px below the sleeve trim that still belong to the sleeve (a cuff band); default line_px + 1')
    a = ap.parse_args()
    img = np.asarray(Image.open(a.layer).convert('RGBA')).copy()
    al = img[..., 3] > 16
    ys, xs = np.nonzero(al)
    y_lo = int(ys.max() - (ys.max() - ys.min()) * a.lower)
    r, g, b = [img[..., i].astype(int) for i in range(3)]
    lum = (r + g + b) / 3
    teal = (g > r + 40) & (b > r + 40)  # sleeve hem trim
    # hand = light pixels (skin and its white highlights), not sleeve black or trim, in pieces that reach
    # the bottom end of the layer (the sleeve's light panel is higher up)
    skin = al & (lum > 110) & ~teal & (r >= b)
    skin[:y_lo] = False
    if a.hem_px >= 0:  # light pixels inside the cuff band are the sleeve's, not the hand's
        pass
    n, cc, st, _ = cv2.connectedComponentsWithStats(skin.astype(np.uint8))
    keep = np.zeros_like(skin)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area >= 30 and y + h >= ys.max() - 25:
            keep |= cc == i
    if keep.sum() == 0:
        raise SystemExit('no hand (skin) found in the lower part')
    # outline around the hand: a dark pixel goes with the hand if it is closer to the hand's light pixels
    # than to the sleeve trim, within --line_px * 2 (the finger outline is thicker than the trim's)
    sy, sx = np.nonzero(keep)
    d_hand = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    trim = al & teal
    d_trim = cv2.distanceTransform((~trim).astype(np.uint8), cv2.DIST_L2, 3) if trim.any() else np.full(keep.shape, 1e6, np.float32)
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    # the sleeve's own outline runs just under the trim: in columns with trim, the band down to
    # trim bottom + line_px + 1 stays with the sleeve
    tb = np.full(img.shape[1], -1)
    ty_, tx_ = np.nonzero(trim)
    for x in np.unique(tx_):
        tb[x] = ty_[tx_ == x].max()
    tbx = tb[xx]
    hem = a.line_px + 1 if a.hem_px < 0 else a.hem_px
    below_hem = (tbx < 0) | (yy > tbx + hem)
    ring = al & ~keep & ~teal & (d_hand <= a.line_px * 2) & (d_hand < d_trim) & (yy >= sy.min() - 2) & below_hem
    hand_m = keep | ring
    # bits left over from the hand's thick outline that are not attached to the sleeve go with the hand
    rest = al & ~hand_m
    n, cc, st, _ = cv2.connectedComponentsWithStats(rest.astype(np.uint8), connectivity=8)
    if n > 2:
        main = 1 + int(np.argmax(st[1:, 4]))
        hand_m |= rest & (cc != main) & (cc > 0)
    names = a.names.split(',')
    os.makedirs(a.out_dir, exist_ok=True)
    sleeve = img.copy(); sleeve[hand_m] = 0
    hand = np.zeros_like(img); hand[hand_m] = img[hand_m]
    # wrist pivot: middle of the hand's top edge; hidden extension up into the sleeve
    top = keep & (yy <= sy.min() + 3)
    ty, tx = np.nonzero(top)
    wx, wy = float(tx.mean()), float(sy.min())
    width = float(sx.max() - sx.min())
    rad = width * 0.45
    disc = ((xx - wx) ** 2 + (yy - wy) ** 2 <= rad ** 2) & (yy < wy + 2)
    # well inside the sleeve (8px from its edge), so it stays hidden when the hand turns
    inside = cv2.erode((sleeve[..., 3] > 250).astype(np.uint8), np.ones((17, 17), np.uint8)).astype(bool)
    hid = disc & inside & ~hand_m
    sk = keep & (r - b > 15)  # skin tone (not the white highlight) for the hidden wrist
    skin_col = np.median(img[sk if sk.sum() > 20 else keep, :3], axis=0).astype(np.uint8)
    hand[hid, :3] = skin_col; hand[hid, 3] = 255
    Image.fromarray(sleeve).save(os.path.join(a.out_dir, names[0] + '.png'))
    Image.fromarray(hand).save(os.path.join(a.out_dir, names[1] + '.png'))
    info = {'layer': os.path.basename(a.layer), 'wrist_pivot': [round(wx, 1), round(wy, 1)],
            'hand_px': int(hand_m.sum()), 'hidden_wrist_px': int(hid.sum()), 'skin': skin_col.tolist(),
            'order_front_to_back': [names[0], names[1]], 'note': f'{names[1]} rotates around wrist_pivot, drawn just behind {names[0]}'}
    json.dump(info, open(os.path.join(a.out_dir, 'hand.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))
    # check
    bb = Image.fromarray(img).getchannel('A').getbbox()
    box = (bb[0] - 30, int(wy) - 90, bb[2] + 30, bb[3] + 30)

    def chk(arr):
        h, w = arr.shape[:2]
        y2, x2 = np.mgrid[0:h, 0:w]
        bg = np.where(((y2 // 8 + x2 // 8) % 2)[..., None] == 0, 255, 215).astype(np.uint8).repeat(3, 2)
        c = Image.fromarray(bg).convert('RGBA'); c.alpha_composite(Image.fromarray(arr)); return c.convert('RGB')
    cells = [('원본', chk(img)), (names[0], chk(sleeve)), (names[1] + ' (숨은 손목 포함)', chk(hand))]
    for ang in (0, -30, -15, 15, 30):
        c = Image.new('RGBA', (img.shape[1], img.shape[0]), (0, 0, 0, 0))
        c.alpha_composite(Image.fromarray(hand).rotate(ang, Image.BICUBIC, center=(wx, wy)))
        c.alpha_composite(Image.fromarray(sleeve))
        cells.append(('곧게 (0°)' if ang == 0 else f'손 {ang:+d}°', chk(np.asarray(c))))
    w, h = box[2] - box[0], box[3] - box[1]
    s = Image.new('RGB', (w * 3 * len(cells), h * 3 + 22), 'white'); d = ImageDraw.Draw(s)
    for i, (t, im) in enumerate(cells):
        s.paste(im.crop(box).resize((w * 3, h * 3), Image.NEAREST), (i * w * 3, 22)); d.text((i * w * 3 + 4, 3), t, font=FONT, fill='black')
    s.save(os.path.join(a.out_dir, 'hand_check.png'))


if __name__ == '__main__':
    main()
