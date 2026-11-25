# sd-character-i2l

애니메이션 캐릭터 그림 **한 장**을 리깅·애니메이션용 **레이어 PSD**로 나누는 로컬 작업 기록과 도구 모음이에요.
레이어 분리에는 [See-through](https://github.com/mitmul/see-through)를 쓰고, 그 위에 seed 고르기, 레이어 섞기, 가려진 부분 생성, 검토 이미지 같은 도구를 더했어요.

자동 파이프라인이 아니라 **사람이 단계마다 확인 이미지를 보고 고르는 반자동 흐름**이에요. 그 흐름과 막혔던 곳, 해결한 방법을 같이 정리했어요.

| 원본 | 결과 합성 (21레이어) |
|---|---|
| ![원본](examples/miku/input/miku_chibi_sprite.png) | ![합성](examples/miku/final/composite.png) |

![레이어 시트](examples/miku/final/sheet.png)

---

## 무엇을 할 수 있나
- 그림 한 장 → 최대 24개 고정 태그(앞머리, 뒷머리, 얼굴, 눈, 옷 …) 레이어 + 깊이 (See-through, NF4 양자화로 **8GB GPU**에서 실행)
- 같은 그림을 여러 seed로 생성해 **레이어마다 가장 좋은 seed를 골라 섞기** (`tools/mix_layers.py`)
- 머리 부위가 잘리지 않게 머리 자르기 상자를 자동으로 넓히기 (`tools/head_grow.py`)
- 글로 부위를 지정해 레이어를 더 나누기: Grounding DINO + SAM2 + LaMa (`tools/text_layers.py`)
- 앞 레이어에 가려진 부분을 SDXL 인페인팅으로 그리기 (`tools/amodal_complete.py`)
- 리깅용 나누기: 관절(무릎·팔꿈치) 자르기 + 관절 외곽선, 트윈테일 체인, 소매 천만 남기기, 표정·손 모양 바꿔 끼우기 파츠, 뼈·슬롯 정보(`rig.json`) (`tools/split_joint.py`, `split_chain.py`, `sleeve_cloth.py`, `face_parts.py`)
- 단계별 검토 이미지, seed·버전 비교 시트, 레이어 잔선 측정

## 문서
| 문서 | 내용 |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | 설치 (conda 환경, torch, See-through, 모델 다운로드) |
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | 테스트한 GPU·드라이버·버전, 모델 목록과 용량, 메모리 |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | 그림 한 장 → PSD → 리깅용 조각까지의 작업 흐름 (예시 이미지 포함) |
| [docs/TOOLS.md](docs/TOOLS.md) | 도구 스크립트·함수·옵션 설명 |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 문제 → 원인 → 해결 과정 |
| [docs/HISTORY.md](docs/HISTORY.md) | 작업 기록 (시간순) |

## 빠른 시작
설치는 [docs/INSTALL.md](docs/INSTALL.md)를 따라 하세요. 설치가 끝나면 폴더가 이렇게 돼요.
```
sd-character-i2l/
├─ env/          conda 환경 (설치 때 만듦)
├─ hf_cache/     모델 (설치 때 받음, 약 15GB)
├─ see-through/  See-through 코드 (설치 때 clone, 커밋 e4cb250)
└─ tools/
```
```powershell
# 1) 같은 그림을 seed 0~9로 생성
#    RTX 5060 Ti 16GB 기준 seed 하나에 약 5~10분 (머리 단계를 다시 돌린 횟수에 따라 312~573초), GPU 메모리 약 8GB
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # 지금 창에서만 .ps1 실행 허용
foreach ($s in 0..9) {
  & .\tools\run_seethrough.ps1 -Src C:\work\my_char.png -OutDir C:\work\out\seed$s `
    -Extra @('--no_group_offload','--tblr_split','--seed',"$s") -HeadGrow 3
}
# 2) seed 비교 시트
.\env\Scripts\python.exe tools\compare_seeds.py --run s0=C:\work\out\seed0 --run s1=C:\work\out\seed1 --out C:\work\out\compare.png
# 3) 레이어마다 seed를 골라 spec.json을 쓰고 합치기
.\env\Scripts\python.exe tools\mix_layers.py --spec C:\work\spec.json --out C:\work\out\mix
```
spec 예시는 [examples/miku/final/spec.json](examples/miku/final/spec.json), 옵션은 [docs/TOOLS.md](docs/TOOLS.md)에 있어요.

## 예시 (`examples/miku/`)
| 폴더 | 내용 |
|---|---|
| `input/` | 원본 그림 (1312×1199) |
| `final/` | 확정본 PSD(`miku_v1.psd`, 21레이어), 레이어 PNG, 합성·시트·가려짐 확인 이미지, `spec.json` |
| `final_v2/` | 리깅용 확정본: 레이어 45장, `rig.json`(순서·뼈·슬롯), 표정·손·트윈테일 바꿔 끼우기, `miku_v2.psd`, `sheet.png` |
| `rig/` | 리깅 나누기 과정: 다리(legs), 팔·소매·손(arms), 트윈테일(tails), 표정 파츠(face), 사람이 그은 선 |
| `headwear/` | 헤드셋 고리를 앞/뒤로 나눈 과정 (생성 결과, 사람이 빨간 선으로 표시한 그림, 6조각) |
| `manual/` | 사람이 직접 다듬은 레이어, 지울 곳 표시와 마스크 |
| `back_center/` | 가려진 뒤통수를 분리·생성한 과정 (text_layers, amodal 후보) |

seed 10개와 중간 합치기 결과는 용량이 커서 넣지 않았어요. 대표 이미지는 [docs/WORKFLOW.md](docs/WORKFLOW.md)에 있어요.
`spec.json` 안의 `seethrough_test/...` 경로는 그 중간 결과를 가리켜서, 예시 spec은 그대로 다시 돌릴 수 없고 형식 참고용이에요.

## 모델과 라이선스
모델 가중치는 저장소에 없어요. 처음 실행할 때 Hugging Face에서 받아요. 쓰기 전에 각 모델 카드의 라이선스를 확인하세요.

| 모델 | 쓰는 곳 | 라이선스 |
|---|---|---|
| [24yearsold/seethroughv0.0.2_layerdiff3d_nf4](https://huggingface.co/24yearsold/seethroughv0.0.2_layerdiff3d_nf4) | 레이어 생성 | openrail++ |
| [24yearsold/seethroughv0.0.1_marigold_nf4](https://huggingface.co/24yearsold/seethroughv0.0.1_marigold_nf4) | 깊이 | openrail++ |
| [frankjoshua/juggernautXL_version6Rundiffusion](https://huggingface.co/frankjoshua/juggernautXL_version6Rundiffusion) | See-through가 설정 파일만 참조 (가중치는 안 받음) | 모델 카드 참고 |
| [diffusers/stable-diffusion-xl-1.0-inpainting-0.1](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1) | amodal_complete, mask_inpaint (`--model`로 바꿀 수 있음) | openrail++ |
| [IDEA-Research/grounding-dino-base](https://huggingface.co/IDEA-Research/grounding-dino-base) | text_layers (글 → 상자) | Apache-2.0 |
| [facebook/sam2.1-hiera-large](https://huggingface.co/facebook/sam2.1-hiera-large) | text_layers (상자 → 마스크) | Apache-2.0 |
| [dreMaz/AnimeMangaInpainting](https://huggingface.co/dreMaz/AnimeMangaInpainting) (LaMa) | text_layers (틈 메우기) | 모델 카드 참고 |

**SDXL 인페인팅 모델을 고른 근거:** 가려진 부분 그리기(key 모드)를 애니메이션 SDXL 3종(Animagine XL 4.0, NoobAI-XL 1.1, Illustrious XL v0.1)과 같은 설정·seed 5개로 비교했어요. 색 오차 중앙값이 가장 낮았고(기본 8.1 / 10.1 / 8.9 / 33.2), 가려진 모양도 가장 많이 이어 그렸어요. 애니메이션 모델은 인페인팅 전용이 아니라서 평균 0.4~0.6배만 그렸어요. 자세한 결과: [TROUBLESHOOTING](docs/TROUBLESHOOTING.md#4-다시-그리기-sdxl)

## 라이선스
- 이 저장소의 코드와 문서: [Apache License 2.0](LICENSE)
- See-through 코드를 고쳐 쓴 파일이 있어요 (`tools/head_grow.py`, `tools/run_patched.py`). 출처는 [NOTICE](NOTICE)에 적었어요.
- 예시 그림의 캐릭터 하츠네 미쿠는 Crypton Future Media의 캐릭터예요. 예시 이미지는 비영리 작업 기록용이에요.
