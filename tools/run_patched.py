"""Run a See-through inference script with a runtime-only fix (repo files untouched).

Fix: with --cpu_offload, encode_cropped_prompt_77tokens picks the input device from
text_encoder (1). After text_encoder_2 ran, text_encoder (1) sits on CPU, so the
token ids go to CPU while the other encoder's weights are on CUDA ->
"Expected all tensors to be on the same device". Offload hooks execute on CUDA,
so the ids are sent to CUDA.

Usage: python run_patched.py <script.py> [script args...]   (cwd = repo root)

`encode_cropped_prompt_77tokens` below is adapted from See-through
common/modules/layerdiffuse/diffusers_kdiffusion_sdxl.py (https://github.com/mitmul/see-through,
commit e4cb250, Apache License 2.0). Change: token ids are sent to CUDA.
"""
import os, sys, runpy

script = os.path.abspath(sys.argv[1])
sys.argv = [script] + sys.argv[2:]

import torch
from modules.layerdiffuse import diffusers_kdiffusion_sdxl as m  # 'modules' is installed via -e ./common


@torch.inference_mode()
def encode_cropped_prompt_77tokens(self, prompt):
    device = torch.device('cuda')
    pooled_prompt_embeds = None
    prompt_embeds_list = []
    for tokenizer, text_encoder in zip([self.tokenizer, self.tokenizer_2], [self.text_encoder, self.text_encoder_2]):
        ids = tokenizer(prompt, padding="max_length", max_length=tokenizer.model_max_length,
                        truncation=True, return_tensors="pt").input_ids
        out = text_encoder(ids.to(device), output_hidden_states=True, return_dict=False)
        pooled_prompt_embeds = out[0]
        pe = out[-1][-2]
        bs_embed, seq_len, _ = pe.shape
        prompt_embeds_list.append(pe.view(bs_embed, seq_len, -1).to(device))
    prompt_embeds = torch.concat(prompt_embeds_list, dim=-1).to(dtype=self.unet.dtype, device=device)
    pooled_prompt_embeds = pooled_prompt_embeds.to(device).view(bs_embed, -1)
    return prompt_embeds, pooled_prompt_embeds


m.KDiffusionStableDiffusionXLPipeline.encode_cropped_prompt_77tokens = encode_cropped_prompt_77tokens
print('[run_patched] encode_cropped_prompt_77tokens -> ids on cuda', flush=True)
if (int(os.environ.get('HEAD_GROW_ITERS', '0')) > 0 or os.environ.get('HEAD_BOX')) and 'def run_layerdiff(' in open(script, encoding='utf-8').read():
    # growing head crop: swap run_layerdiff for tools/head_grow.py's version (repo file untouched)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    src = open(script, encoding='utf-8').read()
    src = src.replace('def run_layerdiff(', 'def _orig_run_layerdiff(', 1)
    src = src.replace("if __name__ == '__main__':", "from head_grow import run_layerdiff\n\nif __name__ == '__main__':", 1)
    print(f"[run_patched] head_grow on: HEAD_GROW_ITERS={os.environ.get('HEAD_GROW_ITERS')} HEAD_BOX={os.environ.get('HEAD_BOX', '')} HEAD_NEED={os.environ.get('HEAD_NEED', '')}", flush=True)
    g = {'__name__': '__main__', '__file__': script}
    exec(compile(src, script, 'exec'), g)
else:
    runpy.run_path(script, run_name='__main__')
