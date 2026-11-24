#!/usr/bin/env python
"""Visual verification report for layered PSDs (e.g. See-through output).

Usage:
    python psd_report.py --psd out.psd --input original.png --out report_dir

Outputs (in --out):
    layers/NN_<name>.png   full-canvas RGBA per pixel layer, PSD stacking order (00 = bottom)
    layers.json            per-layer metadata
    layer_sheet.png        contact sheet of all layers on checkerboard
    compare.png            input | composite of visible layers | amplified abs-diff heat map

Dependencies: psd-tools (1.14.x), Pillow, numpy.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from psd_tools import PSDImage

THUMB = 256
COLS = 6
LABEL_H = 30
PAD = 8
DIFF_GAIN = 4.0


# ----------------------------------------------------------------------------- helpers
def sanitize(name: str, maxlen: int = 60) -> str:
    """Filesystem-safe, ASCII-ish file name fragment (keeps unicode word chars)."""
    name = unicodedata.normalize("NFKC", name or "unnamed")
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = name.strip("._") or "unnamed"
    return name[:maxlen]


def ascii_label(text: str) -> str:
    """Default PIL bitmap font is Latin-1 only; replace anything else."""
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("ascii", "replace").decode("ascii")


def get_font():
    try:
        return ImageFont.load_default(size=14)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def checkerboard(w: int, h: int, cell: int = 16) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w]
    mask = ((yy // cell) + (xx // cell)) % 2 == 0
    arr = np.where(mask[..., None], 255, 200).astype(np.uint8)
    arr = np.repeat(arr, 3, axis=2)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def on_checker(img: Image.Image) -> Image.Image:
    bg = checkerboard(*img.size)
    return Image.alpha_composite(bg, img.convert("RGBA"))


def fit(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    if w == 0 or h == 0:
        return Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
    s = max_side / max(w, h)
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def to_rgba(pil: Image.Image) -> Image.Image:
    if pil.mode == "RGBA":
        return pil
    if pil.mode in ("LA", "PA", "P", "L", "RGB", "I;16", "I", "F"):
        try:
            return pil.convert("RGBA")
        except Exception:
            pass
    if pil.mode == "CMYK":
        return pil.convert("RGB").convert("RGBA")
    return pil.convert("RGBA")


def safe_attr(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


# ----------------------------------------------------------------------------- PSD walk
def walk(container, path=()):
    """Yield (layer, group_path) bottom-to-top, recursing into groups.

    psd-tools iterates a container bottom-first, matching PSD stacking order.
    """
    for layer in container:
        if layer.is_group():
            yield from walk(layer, path + (layer.name,))
        else:
            yield layer, path


def render_layer(layer, canvas_size):
    """Return full-canvas RGBA image (or None if no pixel data)."""
    W, H = canvas_size
    try:
        if not layer.has_pixels():
            return None
    except Exception:
        pass
    left, top = safe_attr(layer, "offset", None) or (safe_attr(layer, "left", 0), safe_attr(layer, "top", 0))
    w, h = safe_attr(layer, "width", 0) or 0, safe_attr(layer, "height", 0) or 0
    if w <= 0 or h <= 0:
        return None
    try:
        pil = layer.topil()
    except Exception as e:  # corrupt / unsupported channel data
        print(f"  ! topil() failed for {layer.name!r}: {e}", file=sys.stderr)
        return None
    if pil is None or pil.size[0] == 0 or pil.size[1] == 0:
        return None
    pil = to_rgba(pil)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # paste handles negative/out-of-bounds offsets by clipping; use alpha_composite-free paste
    canvas.paste(pil, (int(left), int(top)))
    return canvas


# ----------------------------------------------------------------------------- outputs
def make_sheet(entries, images, out_path):
    font = get_font()
    n = len(entries)
    if n == 0:
        Image.new("RGB", (400, 60), "white").save(out_path)
        return
    cols = min(COLS, n)
    rows = math.ceil(n / cols)
    cell_w, cell_h = THUMB + PAD * 2, THUMB + LABEL_H + PAD * 2
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (e, img) in enumerate(zip(entries, images)):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w + PAD, r * cell_h + PAD
        if img is None:
            img = Image.new("RGBA", (e["canvas_w"], e["canvas_h"]), (0, 0, 0, 0))
        th = on_checker(fit(img, THUMB)).convert("RGB")
        sheet.paste(th, (x0 + (THUMB - th.width) // 2, y0 + (THUMB - th.height) // 2))
        draw.rectangle([x0 - 1, y0 - 1, x0 + THUMB, y0 + THUMB], outline=(120, 120, 120))
        flags = []
        if e["empty"]:
            flags.append("EMPTY")
        if not e["visible"]:
            flags.append("hidden")
        label = f"{e['index']:02d} {e['name']}"
        draw.text((x0, y0 + THUMB + 3), ascii_label(label)[:34], fill=(0, 0, 0), font=font)
        if flags:
            draw.text((x0, y0 + THUMB + 16), " ".join(flags), fill=(200, 0, 0), font=font)
    sheet.save(out_path)


def psnr(mse: float, peak: float = 255.0) -> float:
    return float("inf") if mse <= 0 else 10.0 * math.log10(peak * peak / mse)


def make_compare(input_path, composite, entries, out_path):
    W, H = composite.size
    inp = to_rgba(Image.open(input_path))
    if inp.size != (W, H):
        print(f"NOTE: input size {inp.size[0]}x{inp.size[1]} != PSD canvas {W}x{H}; resizing input to canvas.")
        inp = inp.resize((W, H), Image.LANCZOS)

    a = np.asarray(inp).astype(np.float32)
    b = np.asarray(composite).astype(np.float32)
    # Inputs often have an opaque white background while the layers are transparent,
    # so both are flattened onto white before comparing.
    def on_white(x):
        al = x[..., 3:] / 255.0
        return x[..., :3] * al + 255.0 * (1.0 - al)
    rgb_diff = np.abs(on_white(a) - on_white(b))
    mse = float((rgb_diff ** 2).mean())
    stats = {
        "compare": "both flattened on white, all pixels",
        "mean_abs_diff_rgb": float(rgb_diff.mean()),
        "mse_rgb": mse,
        "psnr_rgb_db": psnr(mse),
    }
    char = b[..., 3] > 127
    if char.any():
        cd = rgb_diff[char]
        stats["char_pixels"] = int(char.sum())
        stats["char_mean_abs_diff_rgb"] = float(cd.mean())
        stats["char_psnr_rgb_db"] = psnr(float((cd ** 2).mean()))

    heat_val = rgb_diff.max(axis=2)  # 0..255
    heat_val = np.clip(heat_val * DIFF_GAIN, 0, 255) / 255.0
    # simple black->red->yellow->white ramp
    r = np.clip(heat_val * 3, 0, 1)
    g = np.clip(heat_val * 3 - 1, 0, 1)
    bl = np.clip(heat_val * 3 - 2, 0, 1)
    heat = (np.stack([r, g, bl], axis=2) * 255).astype(np.uint8)
    heat_img = Image.fromarray(heat, "RGB").convert("RGBA")

    hidden = [e for e in entries if not e["visible"]]
    titles = [
        "(a) input",
        f"(b) composite of {sum(1 for e in entries if e['visible'] and not e['empty'])} visible layers"
        + (f" ({len(hidden)} hidden skipped)" if hidden else ""),
        f"(c) |diff| x{DIFF_GAIN:g}  meanAbs={stats.get('mean_abs_diff_rgb', float('nan')):.2f} "
        f"PSNR={stats.get('psnr_rgb_db', float('nan')):.1f}dB",
    ]
    panels = [on_checker(inp), on_checker(composite), heat_img]

    max_side = 768
    scale = min(1.0, max_side / max(W, H))
    pw, ph = max(1, round(W * scale)), max(1, round(H * scale))
    font = get_font()
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def wrap(text):
        lines, cur = [], ""
        for word in ascii_label(text).split(" "):
            cand = (cur + " " + word).strip()
            if cur and probe.textlength(cand, font=font) > pw:
                lines.append(cur)
                cur = word
            else:
                cur = cand
        return lines + ([cur] if cur else [])

    wrapped = [wrap(t) for t in titles]
    line_h = 17
    title_h = line_h * max(len(w) for w in wrapped) + 6
    out = Image.new("RGB", (3 * pw + 4 * PAD, ph + title_h + 2 * PAD), (255, 255, 255))
    d = ImageDraw.Draw(out)
    for i, (p, lines) in enumerate(zip(panels, wrapped)):
        x = PAD + i * (pw + PAD)
        for j, ln in enumerate(lines):
            d.text((x, PAD + j * line_h), ln, fill=(0, 0, 0), font=font)
        out.paste(p.resize((pw, ph), Image.LANCZOS).convert("RGB"), (x, PAD + title_h))
    out.save(out_path)
    return stats


# ----------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--psd", required=True)
    ap.add_argument("--input", required=False, help="original image (PNG) for comparison")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    out_dir = os.path.abspath(args.out)
    layers_dir = os.path.join(out_dir, "layers")
    os.makedirs(layers_dir, exist_ok=True)

    psd = PSDImage.open(args.psd)
    W, H = psd.width, psd.height
    print(f"PSD: {args.psd}  canvas {W}x{H}  mode={safe_attr(psd, 'color_mode')}  depth={safe_attr(psd, 'depth')}")

    entries, images = [], []
    composite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for idx, (layer, gpath) in enumerate(walk(psd)):
        img = render_layer(layer, (W, H))
        if img is not None:
            alpha = np.asarray(img.getchannel("A"))
            count = int((alpha > 0).sum())
        else:
            count = 0
        try:
            visible = bool(layer.is_visible())  # includes parent-group visibility
        except Exception:
            visible = bool(safe_attr(layer, "visible", True))
        empty = count == 0
        bbox = safe_attr(layer, "bbox", (0, 0, 0, 0))
        opacity = safe_attr(layer, "opacity", 255)
        blend = safe_attr(layer, "blend_mode", None)
        name = layer.name or f"layer{idx}"
        fname = f"{idx:02d}_{sanitize(name)}.png"
        if img is not None:
            img.save(os.path.join(layers_dir, fname))
            if visible:
                if opacity is not None and opacity < 255:
                    a = np.asarray(img).copy()
                    a[..., 3] = (a[..., 3].astype(np.uint16) * int(opacity) // 255).astype(np.uint8)
                    img_c = Image.fromarray(a, "RGBA")
                else:
                    img_c = img
                composite = Image.alpha_composite(composite, img_c)
        else:
            fname = None
        e = {
            "index": idx,
            "name": name,
            "group_path": list(gpath),
            "kind": safe_attr(layer, "kind", None),
            "bbox": [int(v) for v in bbox] if bbox else [0, 0, 0, 0],
            "visible": visible,
            "opacity": int(opacity) if opacity is not None else None,
            "blend_mode": str(blend) if blend is not None else None,
            "pixel_count": count,
            "empty": empty,
            "file": f"layers/{fname}" if fname else None,
            "canvas_w": W,
            "canvas_h": H,
        }
        entries.append(e)
        images.append(img)

    with open(os.path.join(out_dir, "layers.json"), "w", encoding="utf-8") as f:
        json.dump({"psd": os.path.abspath(args.psd), "canvas": [W, H], "layers": entries},
                  f, ensure_ascii=False, indent=2)

    # summary table
    nw = max([4] + [len(e["name"]) for e in entries])
    print(f"\n{'idx':>3}  {'name':<{nw}}  {'bbox (l,t,r,b)':<24} {'pixels':>10}  flags")
    print("-" * (nw + 50))
    for e in entries:
        flags = []
        if e["empty"]:
            flags.append("EMPTY")
        if not e["visible"]:
            flags.append("hidden")
        if e["blend_mode"] and "NORMAL" not in e["blend_mode"].upper() and "PASS" not in e["blend_mode"].upper():
            flags.append(e["blend_mode"])
        if e["opacity"] is not None and e["opacity"] < 255:
            flags.append(f"opacity={e['opacity']}")
        print(f"{e['index']:>3}  {e['name']:<{nw}}  {str(tuple(e['bbox'])):<24} {e['pixel_count']:>10}  {' '.join(flags)}")
    n_empty = sum(e["empty"] for e in entries)
    n_hidden = sum(not e["visible"] for e in entries)
    print(f"\n{len(entries)} pixel layers, {n_empty} EMPTY, {n_hidden} hidden")
    if n_hidden:
        print("NOTE: hidden layers exist and are excluded from the composite.")
    print("NOTE: composite uses normal alpha-over with layer opacity; blend modes/masks/effects are ignored.")

    make_sheet(entries, images, os.path.join(out_dir, "layer_sheet.png"))
    composite.save(os.path.join(out_dir, "composite.png"))

    if args.input:
        stats = make_compare(args.input, composite, entries, os.path.join(out_dir, "compare.png"))
        print("\nComparison (input and composite both flattened on white):")
        for k, v in stats.items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
        with open(os.path.join(out_dir, "compare_stats.json"), "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    else:
        print("\n(no --input given; compare.png skipped)")

    print(f"\nWrote report to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
