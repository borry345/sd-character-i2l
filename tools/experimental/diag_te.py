"""Minimal repro: load the NF4 text encoder and run one forward pass."""
import os
_d = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_d) != 'tools' and os.path.dirname(_d) != _d:  # works in tools/ and tools/experimental/
    _d = os.path.dirname(_d)
ROOT = os.environ.get('I2L_ROOT') or os.path.dirname(_d)  # i2l folder (the parent of tools/)
os.environ.setdefault('HF_HOME', os.path.join(ROOT, 'hf_cache'))
import torch
from transformers import CLIPTextModel

print('free/total MB before:', [x // 2**20 for x in torch.cuda.mem_get_info()])
a = torch.randn(64, 64, device='cuda', dtype=torch.bfloat16)
print('bf16 matmul ok:', (a @ a).float().abs().sum().item() > 0)

repo = '24yearsold/seethroughv0.0.2_layerdiff3d_nf4'
te = CLIPTextModel.from_pretrained(repo, subfolder='text_encoder')
p = next(te.parameters())
print('te param device/dtype:', p.device, p.dtype, type(te.text_model.encoder.layers[0].self_attn.q_proj).__name__)
print('free MB after load:', torch.cuda.mem_get_info()[0] // 2**20)
ids = torch.ones(1, 77, dtype=torch.long, device=p.device if p.device.type == 'cuda' else 'cuda')
te.to('cuda') if p.device.type != 'cuda' else None
with torch.no_grad():
    out = te(ids, output_hidden_states=True, return_dict=False)
print('forward ok', out[0].shape, 'peak MB', torch.cuda.max_memory_allocated() // 2**20)
