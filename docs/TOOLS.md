# 도구 설명

모든 도구는 `tools/`에 있고, `tools`의 상위 폴더(또는 환경 변수 `I2L_ROOT`)를 기준으로 `env`, `hf_cache`, `see-through`를 찾아요.
`$PY`는 `env\Scripts\python.exe`(venv) 또는 `env\python.exe`(conda)예요.

| 단계 | 도구 | 하는 일 | GPU |
|---|---|---|---|
| 생성 | [run_seethrough.ps1](#run_seethroughps1) | See-through 한 장 실행 + 시간·메모리 기록 | ✔ |
| | [run_patched.py](#run_patchedpy) | See-through 스크립트를 실행 중에만 고쳐서 실행 (`run_seethrough.ps1`이 부름) | ✔ |
| | [head_grow.py](#head_growpy) | 머리 자르기 상자를 넓혀 가며 머리 단계 다시 돌리기 (`-HeadGrow`) | ✔ |
| | [seed_search.ps1](#seed_searchps1) | 특정 부위가 나올 때까지 seed 돌리기 | ✔ |
| 검토 | [review_seethrough.py](#review_seethroughpy) | 결과 하나의 단계별 검토 이미지 | |
| | [compare_seeds.py](#compare_seedspy) | 여러 seed의 같은 태그를 나란히 | |
| 합치기 | [mix_layers.py](#mix_layerspy) | 레이어마다 seed를 골라 PSD 하나로 | (옵션에 따라) |
| | [compare_variants.py](#compare_variantspy) | 여러 합치기 결과의 같은 레이어를 나란히 | |
| | [layer_marks.py](#layer_markspy) | 레이어에 생긴 남의 선·색 이음매 세기 | |
| 나누기·그리기 | [text_layers.py](#text_layerspy) | 글로 부위를 지정해 레이어 나누기 (DINO + SAM2 + LaMa) | ✔ |
| | [amodal_complete.py](#amodal_completepy) | 앞 레이어에 가려진 부분 그리기 (SDXL) | ✔ |
| | [mask_inpaint.py](#mask_inpaintpy) | 마스크 영역만 다시 그리기 (SDXL) | ✔ |
| 조립·확인 | [assemble_layers.py](#assemble_layerspy) | 원래 크기로 되돌리고 원본 픽셀로 PSD | |
| | [psd_report.py](#psd_reportpy) | PSD 레이어 추출·목록·원본 비교 | |
| | `selftest_psd_report.py` | psd_report 자체 테스트 (`$PY tools\selftest_psd_report.py <출력 폴더>`) | |
| | `experimental/diag_te.py` | NF4 텍스트 인코더만 올려 보는 진단 | ✔ |

---

## run_seethrough.ps1
See-through(`inference/scripts/inference_psd_quantized.py`)를 한 장 실행해요. 1초마다 GPU 메모리와 남은 RAM을 기록해요.
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # 지금 창에서만
& tools\run_seethrough.ps1 -Src <그림.png> -OutDir <출력 폴더> `
  -Extra @('--no_group_offload','--tblr_split','--seed','0') -HeadGrow 3
```
`powershell -File ...`로 부르면 `-Extra` 배열의 첫 값만 전달돼요. 반드시 `&`로 부르세요.
| 인자 | 기본값 | 뜻 |
|---|---|---|
| `-Src` | (필수) | 입력 그림. **절대 경로** (실행 중 see-through 폴더로 이동함) |
| `-OutDir` | (필수) | 출력 폴더. 절대 경로 |
| `-Resolution` | 1024 | 생성 해상도 |
| `-Script` | `inference/scripts/inference_psd_quantized.py` | 실행할 See-through 스크립트 |
| `-Extra` | 없음 | See-through에 그대로 넘기는 인자 (`--no_group_offload`, `--tblr_split`, `--seed N` 등) |
| `-HeadGrow` | 0 | 머리 단계를 다시 돌릴 수 있는 횟수 ([head_grow.py](#head_growpy)) |

출력: `<OutDir>\<이름>.psd`, `<이름>_depth.psd`, `<OutDir>\<이름>\` 아래 태그별 `<태그>.png`·`<태그>_depth.png`·`src_img.png`, `run.log`, `gpu_mem.csv`, `summary.txt`(`EXIT`, `SECONDS`, `PEAK_GPU_MB`, `MIN_FREE_RAM_MB` …)

## run_patched.py
See-through 저장소 파일을 고치지 않고, 실행할 때만 두 가지를 바꿔요.
- `encode_cropped_prompt_77tokens`: `--cpu_offload`일 때 토큰 id가 CPU로 가서 생기는 장치 불일치를 막으려고 CUDA로 보내요. (그래도 cpu_offload는 다른 곳에서 깨져서 권하지 않아요.)
- `HEAD_GROW_ITERS`가 0보다 크면 스크립트의 `run_layerdiff`를 [head_grow.py](#head_growpy)의 것으로 바꿔 실행해요.

## head_grow.py
See-through `run_layerdiff`를 대신하는 함수예요 (See-through 코드를 고쳐 만듦, [NOTICE](../NOTICE)).
| 함수 | 하는 일 |
|---|---|
| `run_layerdiff(pipeline, imgp, save_dir, seed, num_inference_steps, resolution)` | 몸 단계 → head 레이어로 머리 상자 → 머리 단계 → 테두리에 닿은 쪽 넓혀서 다시 (같은 난수 상태) |
| `_pass(...)` | 파이프라인 한 번 실행 (몸 = group 0, 머리 = group 1) |

| 환경 변수 | 기본값 | 뜻 |
|---|---|---|
| `HEAD_GROW_ITERS` | 0 | 다시 돌릴 수 있는 횟수 (`-HeadGrow`가 설정) |
| `HEAD_GROW_STEP` | 0.25 | 한 번에 넓히는 양 (머리 너비·높이 대비) |
| `HEAD_GROW_MAX` | 1.0 | 한쪽 여백 최대값 (머리 크기 대비) |
| `HEAD_GROW_MINPX` | 8 | 테두리 2px 안에 이만큼 있으면 "닿음" |

추가 출력: `head_grow\src_head_<회차>.png`, `head_grow\<회차>_<태그>.png`, `head_grow.json`(회차별 상자, 닿은 쪽, 넓힌 쪽)

## seed_search.ps1
```powershell
tools\seed_search.ps1 -Src <그림.png> -OutRoot C:\work\out\seed -Tag headwear -MinPx 8000 -Seeds 0,1,2,3 -HeadGrow 3
```
seed마다 `<OutRoot><seed>`에 생성하고, `-Tag` 레이어 픽셀 수가 `-MinPx` 이상이면 멈춰요. 이미 결과가 있는 seed는 다시 돌리지 않아요. 기록은 `<OutRoot>_search.txt`.
`-Extra` 기본값은 `--no_group_offload --tblr_split`이에요.

## review_seethrough.py
```powershell
& $PY tools\review_seethrough.py --run <run_seethrough 출력 폴더> --src <원본 그림> [--res 1024]
```
모델을 돌리지 않고 결과 파일만 읽어 `<run>\review\`에 검토 이미지를 만들어요: `step20_preprocess` ~ `step27_hidden_parts`, `stages_strip.png`, `review.md`(수치). 각 이미지 설명은 [WORKFLOW.md](WORKFLOW.md#2-seed-비교-).

## compare_seeds.py
```powershell
& $PY tools\compare_seeds.py --run s0=<폴더> --run s1=<폴더> ... --out compare.png [--cell 220]
```
행 = 비어 있지 않은 태그, 열 = 실행. 칸마다 그 태그의 모든 실행을 합친 범위로 잘라 보여 주고, 픽셀 수를 적어요 (0px는 빨강).

## mix_layers.py
```powershell
& $PY tools\mix_layers.py --spec <spec.json> --out <출력 폴더>
```
여러 실행(seed)의 태그 레이어를 골라 PSD 하나로 합쳐요. 모든 실행은 같은 1024 페이지 좌표라 그대로 섞여요.
깊이 = 그 레이어 픽셀에서 실행의 `<태그>_depth.png` 중앙값 (0 = 가까움). PSD 맨 아래가 가장 먼 레이어예요.

### spec: 레이어 옵션
| 옵션 | 뜻 |
|---|---|
| `name` | 레이어 이름 |
| `run`, `tag` | 가져올 실행 폴더와 태그 |
| `png` | 이 파일로 바꿔 쓰기 (깊이는 `run`/`tag`에서). 바꿀 때 `split`은 지우기 |
| `split` | `left`/`right`/`top`/`bottom`/`top-left`… 연결 조각을 레이어 상자 중심 기준으로 고르기 (50px 미만 조각 무시) |
| `split_cut` | 조각이 붙어 있을 때, 가운데 40% 안에서 픽셀이 가장 적은 세로줄로 자르기 (`left`/`right`만) |
| `minus` + `minus_grow` | 다른 실행·태그의 레이어(넓힌 만큼)를 빼기 |
| `keep: "largest"` | 가장 큰 조각만 |
| `depth` | 깊이 고정 (작을수록 앞) |
| `keep_rgb` | 원본 색을 복사하지 않음 (생성 색 그대로) |
| `rgb_from: "src"` | 알파는 레이어, 색은 원본 (입 테두리 같은 반투명 가장자리 색 문제) |
| `despill: "magenta"` | 마젠타 기운이 있는 픽셀을 가장 가까운 깨끗한 색으로 (amodal key 모드 잔여) |
| `no_fill` | `fill_missing`이 이 레이어에 원본 픽셀을 붙이지 않음 (그 자리는 빈 채로) |
| `erase` | 마스크 PNG(흰색 = 지움)를 맨 마지막에 적용 |
| `owner_guard` | `visible_rgb: owner`에서 `false`면 항상 원본 색 (눈처럼 세부가 선뿐인 레이어) |
| `hidden` | PSD에 넣되 꺼 두고, 합성 검사에서 뺌 |

### spec: 전체 옵션
| 옵션 | 뜻 |
|---|---|
| `src` | 원본 (실행 폴더의 `src_img.png`, 1024 페이지) |
| `fill_missing` | 원본에는 있는데 어떤 레이어도 덮지 않은 픽셀 → 가장 가까운 레이어에 원본 픽셀로 |
| `visible_rgb: "src"` (+`rgb_thr`) | 앞에서 뒤로, 보이는 픽셀에 원본 색 복사 (A 방식). `rgb_thr`(기본 60)보다 색 차이가 크면 복사 안 함 |
| `visible_rgb: "owner"` | 원본 픽셀마다 색이 맞는 레이어 하나를 주인으로 정해 그 레이어만 원본 색 (실험, `owner_r`, `line_front`, `bd_guard`, `guard_hand`) |
| `align: "flow"/"sam2"/"flow+sam2"` | owner 전에 레이어를 원본에 맞춰 옮기기·다시 자르기 (실험) |
| `blend: "poisson"/"poisson_seam"` | owner 후 보이는 부분과 숨은 부분의 색 이음매 메우기 (실험) |

### 출력
| 파일 | 내용 |
|---|---|
| `layers/NN_이름.png` | 레이어 (00 = 맨 앞) |
| `gen/NN_이름.png` | 원본 색을 넣기 전 생성 레이어 (`layer_marks.py`의 기준) |
| `mix.psd` | PSD (`hidden` 레이어는 꺼짐) |
| `composite.png`, `check.png` | 합성, 원본 비교 (빨강 = 빠짐, 파랑 = 넘침, 노랑 = 색 차이 > 40, PSNR) |
| `sheet.png`, `hidden.png` | 레이어 목록, 레이어별 가려지는 부분(초록) |
| `mix.json` | spec, 수치, 레이어별 깊이·픽셀 수·처리 기록 |

### 주요 함수
| 함수 | 하는 일 |
|---|---|
| `build(L, src_rgba)` | 레이어 하나 만들기: 불러오기 → `minus` → `split`/`keep` → `rgb_from` → `despill` → 깊이 |
| `owner_assign(...)` | `visible_rgb: owner`의 픽셀 주인 정하기 |
| `line_mask(src_rgba)` | 원본의 윤곽선 픽셀 (어두움 또는 black-hat) |
| `flow_align`, `sam_refine` | `align` 옵션 |
| `poisson_blend`, `poisson_seam_blend` | `blend` 옵션 |
| `extra_edges(it)` | 생성본에 없는 새 경계선 (`layer_marks.py`가 씀) |

## compare_variants.py
```powershell
& $PY tools\compare_variants.py --v "A=<mix 폴더>" --v "B=<mix 폴더>" --layers face,legwear --out cmp.png [--cell 330]
```
행 = 레이어, 열 = 버전. 레이어를 하나씩 체커보드 위에 놓고 보여 줘요. 레이어마다 버전을 고를 때 써요.

## layer_marks.py
```powershell
& $PY tools\layer_marks.py --v "A=<mix 폴더>:<기준 레이어 폴더>" --v "C=<mix 폴더>" --base A --out marks.png
```
레이어에 생긴 흔적을 세요. 기준은 `<mix>/gen/`(생성본), 없으면 `:` 뒤 폴더.
- **선**: 다른 부위와의 경계 3px 안에서, 생성본보다 40 이상 어두워진 픽셀 (남의 윤곽선이 찍힌 것)
- **이음매**: 그 밖에 생성본에 없던 새 경계선
- 측정 규칙과 고치는 규칙이 같은 것을 보면 숫자가 좋게만 나와요. 반드시 이미지로도 확인하세요.

## text_layers.py
```powershell
& $PY tools\text_layers.py --image back_hair.png --out <폴더> --part "back_hair=*" --part "tail_left=twin tail@left" --part "tail_right=twin tail@right"
```
| 인자 | 기본값 | 뜻 |
|---|---|---|
| `--part 이름=설명[@left/@right]` | (필수, 여러 번) | **앞에 있는 부위부터.** `@left/@right` = 같은 설명의 상자가 여럿일 때 가장 왼/오른쪽, `*` = 나머지 전부 |
| `--box_thr`, `--text_thr` | 0.25 | Grounding DINO 임계값 |
| `--fill_px` | 48 | 뒤 레이어가 앞 레이어 밑으로 이어지는 거리 (LaMa로 채움) |
| `--grow_px` | 5 | 찾은 마스크를 넓혀 윤곽선까지 포함 (`*` 모드) |

| 함수 | 하는 일 |
|---|---|
| `detect` / `pick_box` | Grounding DINO로 글 → 상자, `@left/@right` 고르기 |
| `segment` | SAM2로 상자 → 마스크 |
| `assign` | 모든 불투명 픽셀을 정확히 한 부위에 (겹치면 앞 부위, 남으면 가장 가까운 부위) |
| `clean_islands` | 작은 조각 정리 |

출력: `NN_이름.png`, `layers.psd`, `parts.json`, `debug_boxes.png`(찾은 상자), `debug_labels.png`(부위 분배)

## amodal_complete.py
```powershell
& $PY tools\amodal_complete.py --mode key --candidates 3 --target back_center.png --front tail_left.png --front tail_right.png `
  --out back_center_key.png --prompt "anime illustration, light blue hair, back of head" --negative "face, skin"
```
1. 보이는 부분 = 대상 레이어에서 `--front` 레이어에 가려지지 않은 픽셀
2. 그려도 되는 곳(마스크2) = 가려진 곳 중 보이는 부분에서 `--search_px` 안 (∩ `--shape` 마스크)
3. SDXL 인페인팅으로 그 영역만 그림

| 인자 | 기본값 | 뜻 |
|---|---|---|
| `--mode` | `key` | `key`: 마젠타 배경 위에 SDXL이 모양까지 그림 (자연스럽지만 색이 흔들림) / `hull`: 볼록 껍질만큼 먼저 칠하고 다듬기 (색 안전, 모양 딱딱) |
| `--candidates` | 3 | seed 여러 개를 그려서 보이는 부분과 색(Lab 색상)이 가장 가까운 것 채택 |
| `--search_px` | 90 | 앞 레이어 밑으로 이어질 수 있는 거리 |
| `--shape` | 없음 | 직접 그린 마스크2 (흰색 = 그려도 됨) |
| `--strength`, `--line_px` | 0.5, 2 | hull 모드: 다시 그리는 정도, 윤곽선 굵기 |
| `--margin`, `--steps`, `--seed`, `--key` | 80, 30, 0, `255,0,255` | 자르기 여백, 단계 수, 첫 seed, 배경색 |

출력: `<out>`, 후보별 `<out>_seed<N>_check.png`, 후보 모음 `candidates.png`

## mask_inpaint.py
```powershell
& $PY tools\mask_inpaint.py --image face.png --mask mask.png --out fixed.png --prefill median --strength 0.4 --prompt "anime style, smooth forehead skin, flat cel shading" --negative "hair, eyes"
```
SDXL 인페인팅으로 마스크(흰색)만 다시 그려요. 8GB에 맞추려고 텍스트 인코더 → UNet → VAE를 따로 올려요.
| 인자 | 기본값 | 뜻 |
|---|---|---|
| `--prefill` | `none` | `median`/`nearest`: 먼저 칠하고 낮은 `--strength`로 다듬기. 얼굴처럼 엉뚱한 걸 그리기 쉬운 곳은 `median` + 0.4 |
| `--strength` | 0.99 | 다시 그리는 정도. 머리카락 결은 0.6 정도 |
| `--margin` | 96 | 마스크 둘레 문맥 |
| `--feather` | 6 | 경계 부드럽게 |
| `--bg` | `255,255,255` | 투명 픽셀 뒤 색 |
| `--steps`, `--guidance`, `--seed` | 30, 7.0, 0 | |

## assemble_layers.py
```powershell
& $PY tools\assemble_layers.py --src 원본.png --out final --layer "front_hair=..." --layer "face=..." --layer "back_hair=..."
```
`--layer`는 앞에 있는 것부터. 1024 페이지 → 원래 크기로 되돌리고, 보이는 픽셀은 원본 픽셀로 바꿔 PSD를 만들어요 (`--alpha_thr` 16).
**레이어를 원본에서 잘라낸 경우에만** 맞아요. 여러 seed의 생성 레이어를 섞을 때 쓰면 남의 선이 찍혀요 → 그때는 `mix_layers.py`.

## psd_report.py
```powershell
& $PY tools\psd_report.py --psd <psd> --input <원본 png> --out <폴더>
```
`layers\NN_이름.png`(레이어 추출), `layer_sheet.png`(목록), `composite.png`, `compare.png`(입력 / 합성 / 차이), `layers.json`, `compare_stats.json`(PSNR)
