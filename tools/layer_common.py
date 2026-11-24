"""Small helpers shared by the layer tools (mix_layers.py, face_parts.py, ...).

rgb_from_src: See-through's mouth and nose layers have a soft, greyish edge. Put on another picture, that
edge shows as grey "whiskers" around the mouth. See-through itself paints nose/mouth with the input
picture's colours, so do the same: keep the layer's shape (alpha), take the colour from the picture the
layer was made from (the run's src_img.png, same 1024 page). Use this for EVERY tool that takes mouth/nose
layers out of a run (docs/TROUBLESHOOTING.md, "입에 수염 같은 회색 테두리").
"""
import numpy as np


def rgb_from_src(layer, src, mask=None):
    """Return a copy of the RGBA layer whose colour comes from src (RGBA/RGB, same size) where mask is true
    (default: every pixel with any alpha). Alpha is unchanged."""
    out = layer.copy()
    if mask is None:
        mask = layer[..., 3] > 0
    out[mask, :3] = src[mask, :3]
    return out
