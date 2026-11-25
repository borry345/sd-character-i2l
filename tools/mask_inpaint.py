"""Redraw only the masked area of a layer with SDXL inpainting (local, fits 8 GB VRAM).

  python mask_inpaint.py --image layer.png --mask mask.png --prompt "..." --out out.png

  - mask: white = redraw. The crop around the mask is scaled to 1024, generated, scaled back
    and blended in with a soft edge; pixels outside the mask are kept exactly.
  - Output alpha = layer alpha OR mask (the redrawn area becomes opaque).
  - Memory: text encoders run first and are freed, then UNet, then the VAE (in fp32).
"""
import argparse
import os

ROOT = os.environ.get('I2L_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # i2l folder (tools/..)
os.environ.setdefault('HF_HOME', os.path.join(ROOT, 'hf_cache'))
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

import cv2
import numpy as np
import torch
from PIL import Image

REPO = 'diffusers/stable-diffusion-xl-1.0-inpainting-0.1'
# --model: any SDXL in diffusers format (Hugging Face id or folder), e.g. an anime SDXL. A normal (not inpainting)
# SDXL also works: the inpaint pipeline keeps the unmasked latents and redraws only the mask.


def _variant(model):
    return 'fp16' if model == REPO else None  # the default repo has *.fp16.safetensors; most others are fp16 files without the variant name


@torch.no_grad()
def encode(prompts, model=REPO):
    from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPTokenizer
    t1 = CLIPTokenizer.from_pretrained(model, subfolder='tokenizer')
    t2 = CLIPTokenizer.from_pretrained(model, subfolder='tokenizer_2')
    e1 = CLIPTextModel.from_pretrained(model, subfolder='text_encoder', variant=_variant(model), torch_dtype=torch.float16).to('cuda')
    e2 = CLIPTextModelWithProjection.from_pretrained(model, subfolder='text_encoder_2', variant=_variant(model), torch_dtype=torch.float16).to('cuda')
    out = []
    for p in prompts:
        i1 = t1(p, padding='max_length', max_length=77, truncation=True, return_tensors='pt').input_ids.to('cuda')
        i2 = t2(p, padding='max_length', max_length=77, truncation=True, return_tensors='pt').input_ids.to('cuda')
        o1 = e1(i1, output_hidden_states=True)
        o2 = e2(i2, output_hidden_states=True)
        out.append((torch.cat([o1.hidden_states[-2], o2.hidden_states[-2]], dim=-1), o2.text_embeds))
    del e1, e2
    torch.cuda.empty_cache()
    return out


def generate(crop, mcrop, prompt, negative, strength=0.99, steps=30, guidance=7.0, seed=0, model=REPO):
    """SDXL inpaint of a 1024x1024 PIL crop + PIL mask (white = redraw). Returns uint8 HxWx3.
    Runs text encoders, UNet and VAE one after another so it fits in 8 GB."""
    (pe, pp), (ne, np_) = encode([prompt, negative], model)
    from diffusers import StableDiffusionXLInpaintPipeline
    pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        model, text_encoder=None, text_encoder_2=None, tokenizer=None, tokenizer_2=None,
        variant=_variant(model), torch_dtype=torch.float16).to('cuda')
    pipe.set_progress_bar_config(disable=True)
    g = torch.Generator('cuda').manual_seed(seed)
    lat = pipe(prompt_embeds=pe, pooled_prompt_embeds=pp, negative_prompt_embeds=ne, negative_pooled_prompt_embeds=np_,
               image=crop, mask_image=mcrop, height=1024, width=1024, strength=strength,
               num_inference_steps=steps, guidance_scale=guidance, generator=g, output_type='latent').images
    vae = pipe.vae
    del pipe
    torch.cuda.empty_cache()
    vae.to(torch.float32)
    with torch.no_grad():
        img = vae.decode(lat.float() / vae.config.scaling_factor).sample
    img = ((img[0].clamp(-1, 1) + 1) * 127.5).permute(1, 2, 0).cpu().numpy().astype(np.uint8)
    del vae
    torch.cuda.empty_cache()
    print(f'[gpu] peak allocated {torch.cuda.max_memory_allocated() // 2**20} MB')
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--mask', required=True)
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--negative', default='lowres, blurry, jpeg artifacts, text, watermark, extra limbs')
    ap.add_argument('--out', required=True)
    ap.add_argument('--steps', type=int, default=30)
    ap.add_argument('--strength', type=float, default=0.99)
    ap.add_argument('--guidance', type=float, default=7.0)
    ap.add_argument('--model', default=REPO, help='SDXL in diffusers format (default: SDXL inpainting 0.1)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--margin', type=int, default=96, help='context around the mask (px)')
    ap.add_argument('--bg', default='255,255,255', help='colour behind transparent pixels')
    ap.add_argument('--feather', type=int, default=6)
    ap.add_argument('--prefill', choices=['none', 'median', 'nearest'], default='none',
                    help='paint the mask first (median colour of the rest of the layer, or nearest colours) '
                         'and use a lower --strength so SDXL only refines it')
    a = ap.parse_args()

    rgba = np.asarray(Image.open(a.image).convert('RGBA')).copy()
    mask = np.asarray(Image.open(a.mask).convert('L')) > 127
    if a.prefill != 'none':
        lum = rgba[..., :3].astype(np.float32).mean(axis=2)
        src = (rgba[..., 3] > 200) & ~mask & (lum > 110)  # skip line art
        if a.prefill == 'median':
            rgba[mask, :3] = np.median(rgba[src, :3], axis=0).astype(np.uint8)
        else:
            from scipy.ndimage import distance_transform_edt
            _, (iy, ix) = distance_transform_edt(~src, return_indices=True)
            rgba[mask, :3] = rgba[iy[mask], ix[mask], :3]
        rgba[mask, 3] = 255
        print(f'[prefill] {a.prefill}: {int(mask.sum())}px')
    H, W = mask.shape
    bg = np.array([int(v) for v in a.bg.split(',')], np.float32)
    al = rgba[..., 3:].astype(np.float32) / 255
    rgb = (rgba[..., :3] * al + bg * (1 - al)).astype(np.uint8)

    ys, xs = np.nonzero(mask)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    side = int(max(xs.max() - xs.min(), ys.max() - ys.min()) + 2 * a.margin)
    side = max(side, 256)
    x0 = int(np.clip(cx - side / 2, 0, max(0, W - side))); y0 = int(np.clip(cy - side / 2, 0, max(0, H - side)))
    x1, y1 = min(W, x0 + side), min(H, y0 + side)
    crop = Image.fromarray(rgb[y0:y1, x0:x1]).resize((1024, 1024), Image.LANCZOS)
    mcrop = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8)).resize((1024, 1024), Image.NEAREST)
    print(f'[crop] ({x0},{y0})-({x1},{y1}) side {x1 - x0}px -> 1024, mask {int(mask.sum())}px')

    img = generate(crop, mcrop, a.prompt, a.negative, a.strength, a.steps, a.guidance, a.seed, a.model)
    gen =np.asarray(Image.fromarray(img).resize((x1 - x0, y1 - y0), Image.LANCZOS))
    soft = mask.astype(np.float32)
    if a.feather > 0:
        soft = cv2.GaussianBlur(soft, (0, 0), a.feather) * mask  # soft only inside the mask edge
        soft = np.maximum(soft, cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32))
    out = rgba.copy()
    region = out[y0:y1, x0:x1]
    s = soft[y0:y1, x0:x1, None]
    region[..., :3] = (gen * s + region[..., :3] * (1 - s)).astype(np.uint8)
    region[..., 3] = np.maximum(region[..., 3], (mask[y0:y1, x0:x1] * 255).astype(np.uint8))
    Image.fromarray(out).save(a.out)

    # before | mask | after, on white, for checking
    def show(x):
        x = x[y0:y1, x0:x1].astype(np.float32); al = x[..., 3:] / 255
        return Image.fromarray((x[..., :3] * al + 255 * (1 - al)).astype(np.uint8))
    m = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8)).convert('RGB')
    w, h = x1 - x0, y1 - y0
    sheet = Image.new('RGB', (w * 3, h), 'white')
    for i, im in enumerate([show(rgba), m, show(out)]):
        sheet.paste(im, (i * w, 0))
    sheet.save(os.path.splitext(a.out)[0] + '_check.png')
    print('[done]', a.out)


if __name__ == '__main__':
    main()
