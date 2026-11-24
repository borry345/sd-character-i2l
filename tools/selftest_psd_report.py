"""Self-test for psd_report.py.

If psd-tools is importable: builds a real 3-layer PSD (+ one empty layer, one hidden
layer inside a group) with PixelLayer.frompil and runs the report on it.
Otherwise: injects a mock psd_tools module so the rest of the pipeline is exercised.

    python selftest_psd_report.py [out_dir]
"""
import os
import sys
import types

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "_selftest")
os.makedirs(OUT, exist_ok=True)
W, H = 200, 150


def make_layers():
    bg = Image.new("RGBA", (W, H), (240, 220, 200, 255))
    circ = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(circ).ellipse([0, 0, 59, 59], fill=(200, 30, 30, 255))
    sq = Image.new("RGBA", (50, 40), (30, 30, 200, 180))
    return bg, circ, sq


bg, circ, sq = make_layers()
# expected "input": composite of the 3 visible layers
inp = bg.copy()
tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0)); tmp.paste(circ, (30, 40)); inp = Image.alpha_composite(inp, tmp)
tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0)); tmp.paste(sq, (120, 80)); inp = Image.alpha_composite(inp, tmp)
inp_path = os.path.join(OUT, "input.png")
inp.save(inp_path)

try:
    import psd_tools  # noqa: F401
    REAL = True
except ImportError:
    REAL = False

if REAL:
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer, Group

    psd = PSDImage.new("RGBA", (W, H), depth=8)  # "RGB" drops layer transparency in psd-tools 1.14 topil()
    psd.append(PixelLayer.frompil(bg, psd, "background", 0, 0))
    psd.append(PixelLayer.frompil(circ, psd, "face", 40, 30))  # (top, left)
    grp = Group.new(psd, "hair group", open_folder=True)  # psd-tools 1.14: parent comes first
    grp.append(PixelLayer.frompil(sq, psd, "back hair", 80, 120))
    hid = PixelLayer.frompil(Image.new("RGBA", (20, 20), (0, 255, 0, 255)), psd, "hidden ear", 5, 5)
    hid.visible = False
    grp.append(hid)
    psd.append(PixelLayer.frompil(Image.new("RGBA", (W, H), (0, 0, 0, 0)), psd, "empty tail", 0, 0))
    psd_path = os.path.join(OUT, "synthetic.psd")
    psd.save(psd_path)
    print("Built real PSD:", psd_path)
else:
    print("psd_tools not importable -> using mock PSD objects")

    class L:
        def __init__(self, name, img, left, top, visible=True, children=None):
            self.name, self._img, self.left, self.top = name, img, left, top
            self.visible, self._children = visible, children
            self.opacity, self.blend_mode, self.kind = 255, "BlendMode.NORMAL", "group" if children else "pixel"
            self.parent_visible = True

        def is_group(self):
            return self._children is not None

        def __iter__(self):
            return iter(self._children or [])

        def is_visible(self):
            return self.visible and self.parent_visible

        def has_pixels(self):
            return self._img is not None and self._img.size[0] > 0

        @property
        def offset(self):
            return (self.left, self.top)

        @property
        def width(self):
            return self._img.size[0] if self._img else 0

        @property
        def height(self):
            return self._img.size[1] if self._img else 0

        @property
        def bbox(self):
            return (self.left, self.top, self.left + self.width, self.top + self.height)

        def topil(self):
            return self._img

    hidden = L("hidden ear", Image.new("RGBA", (20, 20), (0, 255, 0, 255)), 5, 5, visible=False)
    layers = [
        L("background", bg.convert("RGB"), 0, 0),
        L("face", circ, 30, 40),
        L("hair group", None, 0, 0, children=[L("back hair", sq, 120, 80), hidden]),
        L("empty tail", None, 0, 0),
        L("zero size", Image.new("RGBA", (0, 0)), 0, 0),
        L("髪 unicode", Image.new("RGBA", (W, H), (0, 0, 0, 0)), 0, 0),
    ]

    class FakePSD(list):
        width, height, color_mode, depth = W, H, "RGB", 8

    fake = types.ModuleType("psd_tools")

    class PSDImage:
        @staticmethod
        def open(path):
            return FakePSD(layers)

    fake.PSDImage = PSDImage
    sys.modules["psd_tools"] = fake
    psd_path = "mock.psd"

sys.path.insert(0, HERE)
import psd_report  # noqa: E402

rc = psd_report.main(["--psd", psd_path, "--input", inp_path, "--out", os.path.join(OUT, "report")])
assert rc == 0
import json  # noqa: E402
meta = json.load(open(os.path.join(OUT, "report", "layers.json"), encoding="utf-8"))
names = [e["name"] for e in meta["layers"]]
print("layer order:", names)
assert names[:4] == ["background", "face", "back hair", "hidden ear"], names
assert meta["layers"][3]["visible"] is False
assert any(e["empty"] for e in meta["layers"])
stats = json.load(open(os.path.join(OUT, "report", "compare_stats.json")))
assert stats["mean_abs_diff_rgb"] < 1.0, stats
for f in ("layer_sheet.png", "compare.png", "composite.png"):
    assert os.path.exists(os.path.join(OUT, "report", f)), f
print("SELFTEST OK (%s)" % ("real psd-tools" if REAL else "mock"))
