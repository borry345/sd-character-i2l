"""Anger mark of the "angry" expression: See-through dropped it (no layer has it), so cut it from the run's input page.
  red pixels in the box around the mark -> biggest blob + 1px edge -> face_v2/angry/anger.png (1024 page, like the parts)
"""
import os

import cv2
import numpy as np
from PIL import Image

I2L = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(I2L)
SRC = 'seethrough_test/expr/angry_seed1/miku_chibi_angry/src_img.png'
OUT = 'seethrough_test/rig/face_v2/angry/anger.png'
BOX = (520, 220, 680, 380)  # page coords around the mark (right side of the head)

a = np.asarray(Image.open(SRC).convert('RGBA')).astype(int)
r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
red = (al > 128) & (r > 150) & (r - g > 80) & (r - b > 80)
roi = np.zeros_like(red); roi[BOX[1]:BOX[3], BOX[0]:BOX[2]] = True
red &= roi
n, cc, st, _ = cv2.connectedComponentsWithStats(red.astype(np.uint8))
# the mark is 4 strokes: keep blobs near the biggest one
big = 1 + int(np.argmax(st[1:, 4]))
cx, cy = st[big][0] + st[big][2] / 2, st[big][1] + st[big][3] / 2
keep = np.zeros_like(red)
for i in range(1, n):
    x, y, w, h, area = st[i]
    if area >= 8 and abs(x + w / 2 - cx) < 40 and abs(y + h / 2 - cy) < 40:
        keep |= cc == i
ring = cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~keep
out = np.zeros((1024, 1024, 4), np.uint8)
out[keep, :3] = a[keep, :3]; out[keep, 3] = 255
# anti-aliased edge: keep the edge pixel with alpha = how red it is
redness = np.clip((np.minimum(r - g, r - b) - 20) / 80, 0, 1)
out[ring, :3] = a[ring, :3]; out[ring, 3] = (redness[ring] * 255).astype(np.uint8)
Image.fromarray(out).save(OUT)
ys, xs = np.nonzero(out[..., 3] > 16)
print(OUT, int((out[..., 3] > 16).sum()), 'px, box', xs.min(), ys.min(), xs.max(), ys.max())
