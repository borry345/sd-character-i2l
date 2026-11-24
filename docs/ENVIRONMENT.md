# 실행 환경

## 테스트한 PC

| | PC B (주 작업, 2026-11-24) | PC A (처음 설치, 2026-11-23) |
|---|---|---|
| OS | Windows 11 Enterprise 10.0.26300 | Windows 11 |
| CPU / RAM | Intel i7-14700 / 32GB | — / 16GB 이상 |
| GPU | **RTX 5060 Ti 16GB**, 드라이버 616.92 | **RTX 3070 8GB**, 드라이버 616.86 |
| 파이썬 환경 | venv, Python 3.12.5 | conda, Python 3.12 |

`miku_v1`(examples)은 PC B에서 만들었어요.
- **같은 PC + 같은 seed → 결과가 픽셀까지 같아요.** PC B에서 문서대로 새로 설치한 환경으로 seed 0을 돌렸더니, 원래 환경의 seed 0 결과와 레이어 27장이 모두 똑같았어요.
- **다른 GPU면 같은 seed라도 결과가 달라요** (PC A의 seed 42에 있던 헤드셋이 PC B에서는 사라짐). 다른 PC에서 같은 그림이 나온다고 기대하지 말고, 여러 seed를 만들어 고르는 흐름([WORKFLOW.md](WORKFLOW.md))을 쓰세요.

## 패키지 버전 (PC B)
| 패키지 | 버전 |
|---|---|
| torch | 2.8.0+cu128 (CUDA 12.8, cuDNN 9.10.2) |
| diffusers | 0.37.0 |
| transformers | 5.0.0 |
| bitsandbytes | 0.49.2 (NF4 4bit) |
| psd-tools | 1.14.2 |
| opencv-python | 4.13.0.92 |
| numpy | 2.2.6 |
| See-through | 커밋 e4cb250 |
| SAM2 | 커밋 c2ec8e1 |

전체 목록: [requirements-lock.txt](../requirements-lock.txt)

## 디스크
| 폴더 | 크기 |
|---|---|
| `env/` | 약 8.4GB |
| `hf_cache/` (모델) | 약 15.6GB |
| See-through 결과 1개 (seed 하나) | 약 22~24MB |

모델별 크기는 [INSTALL.md](INSTALL.md#7-모델)에 있어요.

## 걸리는 시간과 메모리

### See-through (1024, NF4, 30 steps, `--no_group_offload --tblr_split`, `-HeadGrow 3`)
PC B에서 seed 0~9를 돌린 기록이에요 (`summary.txt`).

| 머리 단계 횟수 | 시간 | seed |
|---|---|---|
| 1회 (닿은 곳 없음) | 312~314초 | s1, s5, s7 |
| 2회 | 438~445초 | s0, s2, s3, s6, s8, s9 |
| 3회 | 573초 | s4 |

- GPU 메모리: 실행 전보다 **약 8.0GB 더** 씀 (7,974~8,043MB)
- 남은 RAM 최소값: 약 9.5GB (s9)
- PC A(8GB GPU): `-HeadGrow` 없이 장당 약 8~9분. 다른 프로그램이 GPU를 2.5GB 쓰고 있으면 공유 메모리로 밀려나 멈춤 → GPU를 쓰는 프로그램을 닫아 0.8GB 이하로 만든 뒤 실행

### 다른 도구
| 도구 | 시간 | 기록 |
|---|---|---|
| `text_layers.py` (DINO + SAM2 + LaMa) | 38초 | 설치 확인 때 back_hair.png 한 장 |
| `amodal_complete.py --mode hull` | 49초 | PC B, back_center |
| `amodal_complete.py --mode key --candidates 3` | 66초 | PC B, back_center |
| `mask_inpaint.py` | 회당 약 2분 | PC A |
| `mix_layers.py` (21레이어, `miku_v1`) | 11초 | PC B. `visible_rgb: owner`·`align`·`blend`를 쓰면 더 걸려요 (SAM2 로딩 등) |

## 8GB GPU에서
- See-through는 NF4 양자화 덕분에 8GB에서 돌아가요. 대신 **`--no_group_offload`가 필요하고**, 다른 프로그램의 GPU 사용을 줄여야 해요.
- `--cpu_offload`는 쓰지 마세요 (여러 곳에서 장치 불일치로 깨짐, [TROUBLESHOOTING.md](TROUBLESHOOTING.md)).
- `mask_inpaint.py`, `amodal_complete.py`는 SDXL을 텍스트 인코더 → UNet → VAE 순서로 따로 올려서 8GB에 맞춰요.
