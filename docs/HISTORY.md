> 작업하면서 남긴 기록을 시간순 그대로 옮겼어요 (원본: 작업 폴더의 `log.md`). `<i2l>`은 작업 폴더예요.
> 정리된 내용은 [WORKFLOW.md](WORKFLOW.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md)를 보세요.

# See-through 실행 로그

완료된 점검표 항목을 완료 시간순으로 기록한다.

| 완료 시각 | id | 항목 | 통과 근거 |
|---|---|---|---|
| 2026-11-22 23:48:45 | p1 | 테스트 이미지 2장을 i2l에 넣기 | hair_input.png(583KB), miku_chibi_sprite.png(890KB) 확인 |
| 2026-11-22 23:48:45 | p2 | 설치 시작 승인 | 사용자 "작업 진행해주세여" |
| 2026-11-22 23:50:03 | i1 | git clone see-through | <i2l>\see-through 생성, requirements 파일 확인 |
| 2026-11-22 23:50:03 | i2 | conda 환경 생성 (Python 3.12) | Python 3.12.16. 첫 시도는 SSL 모듈 오류 → anaconda Library\bin을 이번 명령 PATH에만 추가해 해결 |
| 2026-11-22 23:55:08 | i3 | torch 2.8.0+cu128 설치 | torch 2.8.0+cu128, torchvision 0.23.0, torchaudio 2.8.0 |
| 2026-11-22 23:55:08 | i4 | GPU 인식 확인 | cuda.is_available()=True, NVIDIA GeForce RTX 3070, CUDA 12.8, GPU 행렬곱 성공 |
| 2026-11-22 23:55:14 | i3 | torch 2.8.0+cu128 설치 | torch 2.8.0+cu128, torchvision 0.23.0, torchaudio 2.8.0 |
| 2026-11-22 23:55:14 | i4 | GPU 인식 확인 | cuda.is_available()=True, NVIDIA GeForce RTX 3070, CUDA 12.8, GPU 행렬곱 성공 |
| 2026-11-22 23:55:38 | i6 | assets junction 만들기 | mklink /J assets common\assets 성공, assets\test_image.png 접근 확인 |
| 2026-11-23 00:00:43 | i5 | requirements.txt + requirements-inference-bnb.txt 설치 | pip EXIT 0. bitsandbytes 0.49.2 NF4 양자화/복원 GPU 테스트 성공, torch 2.8.0+cu128 유지. 선택 패키지(annotators extras, sam2, mmdet) 미설치 |
| 2026-11-23 00:02:21 | i7 | HF 모델 캐시를 D:로 지정 | HF_HOME=<i2l>\hf_cache (실행 스크립트 안에서만). models--24yearsold--seethroughv0.0.2_layerdiff3d_nf4가 D:에 2.6GB 쌓임. C: 캐시는 2023년 파일뿐, 새로 쓰지 않음 |
| 2026-11-23 01:39:44 | r2 | 메모리 부족 시 대안 | group offload(cuBLAS 오류), cpu_offload(코드의 장치 버그)는 실패. 다른 프로그램 종료로 기본 VRAM이 2.5→0.8GB가 되어 --no_group_offload로 GPU에 다 올라감 |
| 2026-11-23 01:39:44 | r1 | 예제 실행 (NF4, 1024) | --no_group_offload. EXIT 0, 493초(추론 444초: layerdiff 348 / marigold 21 / psd 3), 최대 GPU 7878MB(기본 809MB), 최소 남은 RAM 2.5GB. test_image.psd 생성 |
| 2026-11-23 01:50:46 | r3 | hair_input.png 실행 | EXIT 0, 515초, 최대 GPU 7918MB, 최소 남은 RAM 792MB(아슬아슬). 레이어 5개: neck, back hair, handwear, face, front hair. 트윈테일은 back hair에 합쳐짐. handwear는 트윈테일을 회색으로 다시 그린 잘못된 레이어 → 빼면 PSNR 20.1→27.1dB |
| 2026-11-23 01:59:10 | r4 | miku_chibi_sprite.png 실행 | EXIT 0, 551초(추론 500초), 최대 GPU 7859MB, 최소 남은 RAM 1.4GB. 레이어 13개 |
| 2026-11-23 01:59:10 | c1 | PSD 레이어를 PNG로 꺼내기 | example 17장, hair_input 5장, miku 13장 → 각 report\layers\ |
| 2026-11-23 01:59:10 | c2 | 체커보드 레이어 목록 이미지 | report\layer_sheet.png 3개, 직접 열어 확인 |
| 2026-11-23 01:59:10 | c3 | 조립 이미지 vs 입력 비교 이미지 | report\compare.png 3개, 흰 배경 기준 PSNR: example 28.4 / hair_input 20.1(handwear 빼면 27.1) / miku 23.3 dB, 직접 열어 확인 |
| 2026-11-23 01:59:10 | c4 | 트윈테일이 back hair와 분리됐나 | 분리 안 됨. hair_input·miku 모두 뒷머리+양쪽 트윈테일이 back hair 한 장 |
| 2026-11-23 01:59:10 | c5 | 기록: 모드·해상도·시간·GPU 메모리 | NF4 + --no_group_offload, 1024, 장당 약 8~9분, 최대 GPU 약 7.9GB / 8GB |
| 2026-11-23 01:59:10 | c6 | 다시 돌릴 한 줄 명령어 정리 | tools\run_seethrough.ps1 (아래 완료 보고 참고) |

## 실패 기록 (r1 예제 실행)

| 시각 | 시도 | 결과 |
|---|---|---|
| 2026-11-23 00:0x | NF4 1024 기본값(group_offload 켜짐) | 128초 만에 CUBLAS_STATUS_NOT_INITIALIZED. 텍스트 인코더 단독 테스트는 정상 → group offload와 bnb 4bit의 충돌로 추정 |
| 2026-11-23 00:05~00:35 | --no_group_offload | VRAM 7.9GB 가득 + 공유메모리 0.75GB로 넘침, GPU 100%인데 첫 단계에서 29분 진전 없음 → 수동 중단 |
| 2026-11-23 00:36 | --cpu_offload | 파이프라인을 만드는 중 시스템 RAM 부족으로 Claude Code가 강제 종료 (RAM 15.8GB) |
| 2026-11-23 00:5x | --cpu_offload (Chrome·VS Code 켜둔 채) | RAM은 버팀(최소 3.7GB 남음, GPU 최대 4.3GB). cache_tag_embeds 두 번째 호출에서 'Expected all tensors to be on the same device' → 코드 버그(입력 장치를 text_encoder 1 위치로 정함). tools/run_patched.py로 실행 중에만 ids를 cuda로 고정 |
| 2026-11-23 01:0x | --cpu_offload + run_patched | 파이프라인 만들기 통과. 추론 첫 단계 VAE encode에서 같은 종류의 장치 불일치(입력 cpu / 가중치 cuda). 코드가 self.unet.device 등으로 장치를 정해서 cpu_offload에서 여러 곳이 깨짐 → 이 경로는 포기 |

## 3번: 글로 지정하는 레이어 분리 (unmerge 방식, 로컬)

| 완료 시각 | id | 항목 | 통과 근거 |
|---|---|---|---|
| 2026-11-23 02:43:12 | t1 | SAM2 · Grounding DINO · LaMa 준비 | SAM2 git 커밋 c2ec8e1을 --no-deps --no-build-isolation, SAM2_BUILD_CUDA=0으로 설치. torch 2.8.0+cu128 유지. 모델은 HF만 사용(facebook/sam2.1-hiera-large, IDEA-Research/grounding-dino-base, dreMaz/AnimeMangaInpainting) |
| 2026-11-23 02:43:12 | t2 | 글로 부위 찾기 | 'head' 1개, 'twin tail' 3개 → 가장 왼쪽/오른쪽 선택. debug_boxes.png 확인 |
| 2026-11-23 02:43:12 | t3 | 부위 마스크 | SAM2 박스 마스크 + 겹침은 앞쪽 우선 + 떨어진 조각 3855px 정리. debug_labels.png 확인 |
| 2026-11-23 02:43:12 | t4 | 가려진 부분 채우기 | 1차: 얼굴 살색 섞임 → 2차: 흰색으로 바램 → 3차: 검은 윤곽선 색 번짐 → 4차: 안쪽 머리카락 색만 참고, 볼록 껍질 안으로 제한 → 머리카락 색으로 채움. tail_left 7889px, tail_right 16246px |
| 2026-11-23 02:43:12 | t5 | back_head / tail_left / tail_right 출력 | seethrough_test\text_layers\hair_input\ 00~02 PNG + layers.psd |
| 2026-11-23 02:43:12 | t6 | 조립 vs 입력 비교 | PSNR 44.5dB, 차이는 머리 윤곽 반투명 가장자리 2줄뿐. compare.png, layers_preview.png 확인 |
| 2026-11-23 02:43:12 | t7 | 사용법 한 줄 명령어 | tools\text_layers.py --part 이름=설명[@left/@right] |

## 혼합: See-through + 분리 + SDXL 인페인팅 → 5장 (hair_input)

| 완료 시각 | id | 항목 | 통과 근거 |
|---|---|---|---|
| 2026-11-23 03:23:01 | m1 | See-through 레이어 점검 | back hair는 가려진 공 모양까지 그려짐, face 윗부분은 회색 앞머리 그림자, front hair 양호, handwear는 버림 |
| 2026-11-23 03:23:01 | m2 | back hair 분리 | text_layers.py에 '*'(나머지) 부위와 마스크 5px 넓히기 추가 → 트윈테일 윤곽선도 트윈테일로. debug_labels.png 확인 |
| 2026-11-23 03:23:01 | m3 | SDXL 인페인팅 모델 | diffusers/stable-diffusion-xl-1.0-inpainting-0.1 fp16, 6.46GB, <i2l>\hf_cache |
| 2026-11-23 03:23:01 | m4 | 마스크 영역만 다시 그리기 도구 | tools\mask_inpaint.py: 텍스트 인코더 → UNet → VAE(fp32) 순서로 따로 올림, GPU 최대 6.7GB, 1회 약 2분 |
| 2026-11-23 03:23:01 | m5 | face 회색 부분 | 1차 strength 0.99: 검은 머리·눈썹·눈이 그려짐(실패) → 피부색으로 먼저 칠하고 strength 0.4 → 피부. face_fixed_check.png 확인 |
| 2026-11-23 03:23:01 | m6 | 트윈테일 뿌리 | 뿌리 마스크(back_hair 밑) strength 0.6 → 머리카락 결로 다시 그림. roots_check.png 확인 |
| 2026-11-23 03:23:01 | m7 | 5장 출력 + 비교 | tools\assemble_layers.py: 원래 크기 1312x1199로 복원 + 보이는 부분은 원본 픽셀. 1차 구멍 4735px / 2차 face에 앞머리 선 / 3차 앞머리 윤곽 깨짐 → 4차: 반투명 가장자리는 위 레이어가 가져감 → PSNR 51.4dB. compare.png, hidden_parts_check.png 확인 |

## 새 PC 설치 (SETUP.md 기준, RTX 5060 Ti 16GB)

| 완료 시각 | id | 항목 | 통과 근거 |
|---|---|---|---|
| 2026-11-23 08:07 | s1 | 루트 경로 결정 · 경로 치환 | D: 없음, G:는 Google Drive → 루트 = <i2l>. tools\*.py, run_seethrough.ps1의 <i2l> 치환, python은 env\Scripts\python.exe |
| 2026-11-23 08:08 | s2 | Python 환경 | conda 없음 → 시스템 Python 3.12.5로 venv(env\) 생성 |
| 2026-11-23 08:10 | s3 | PyTorch cu128 | torch 2.8.0+cu128, cuda True, RTX 5060 Ti, arch 목록에 sm_120 포함, GPU 연산 확인 |
| 2026-11-23 08:12 | s4 | See-through 저장소 | 커밋 e4cb250 고정, assets junction, requirements + bnb 설치 EXIT=0 |
| 2026-11-23 08:13 | s5 | SAM2 · 버전 확인 | SAM2 c2ec8e1 설치, import 통과. requirements-lock.txt와 차이는 setuptools(84.2.1→78.1.0)뿐 |
| 2026-11-23 08:16 | s6 | 모델 7개 다운로드 | hf_cache 약 16GB. 첫 시도 WinError 1314(심볼릭 링크 권한, HF 병렬 다운로드 경합) → are_symlinks_supported()를 먼저 호출해 해결 |
| 2026-11-23 08:18 | s7 | text_layers.py 동작 | back_hair.png → back_hair/tail_left/tail_right 38초. verify_setup\text_layers\debug_labels.png 확인 |
| 2026-11-23 08:27 | s8 | See-through 본 실행 | hair_input.png, --no_group_offload, EXIT=0, 366초(이전 PC 8~9분), GPU 최대 9.2GB(16GB 중), 최소 여유 RAM 5.9GB. 레이어: neck/back hair/headwear/face/nose/front hair. 조립 PSNR 27.2dB(이전 PC 20.1dB). verify_setup\seethrough_hair_input\report\layer_sheet.png, compare.png 확인 |

## See-through 단계별 검토 (miku_chibi_sprite, 실행 없이 기존 결과 대조)

| 완료 시각 | id | 항목 | 통과 근거 |
|---|---|---|---|
| 2026-11-23 | v1 | 검토 이미지 도구 | tools\review_seethrough.py 추가: 기존 결과만 읽어 seethrough_test\<이름>\review\에 step20~24 PNG + stages_strip.png + review.md(만든 방법·수치) 생성. 모델 실행 없음 |
| 2026-11-23 | v2 | 2-0 전처리 | 1312x1199 → 위아래 56px 패딩 → 1024 (0.78배). step20_preprocess.png |
| 2026-11-23 | v3 | 2-1 몸 단계 | 13태그 중 7개 생성, 빈 칸 6개(neck·neckwear·footwear·tail·wings·objects). 몸통 피부 칸 없음. step21_body_tags.png |
| 2026-11-23 | v4 | 2-2 머리 자르기 | head.png(헤드셋 없음) + 여백 1/5 → headwear 위·왼쪽 잘림. step22_head_crop.png. 여백 키우기는 미룬 일 |
| 2026-11-23 | v5 | 2-3 머리 단계 | 11태그 중 7개 생성, 빈 칸 4개(eyewear·ears·earwear·nose). step23_head_tags.png |
| 2026-11-23 | v6 | 2-4 깊이 | 순서 front hair 0.04 → … → back hair 0.90. handwear 좌우 깊이 차이 큼(중앙값 0.73). reconstruction PSNR 22.1dB. step24_depth.png |
| 2026-11-23 | v7 | 2-5 PSD 조립 | 13레이어, 아래 back hair(0.90) → 위 front hair(0.04). PSD 픽셀 = 생성 PNG 그대로, mouth만 원본 픽셀. 전체 합성 PSNR 23.3dB. review_seethrough.py에 step25_psd_stack.png 추가 |
| 2026-11-23 | v8 | 2-6 품질 | PSNR 23.3dB. 빠진 픽셀 5,692px = 헤드셋 윗부분 2덩어리 + 왼쪽 옆면(모두 2-2 자르기 상자 밖) + 목 158px(neck 빈 레이어). review_seethrough.py에 step26_coverage.png 추가 |
| 2026-11-23 | v9 | 3 레이어 점검 | miku 13레이어 모두 유지(오검출 없음). headwear 잘림 수정 방법(재실행 vs amodal)은 보류 |
| 2026-11-23 | v10 | 4 2차 분리 | 계획만 작성(back hair → back_hair / tail_left / tail_right), 실행은 보류 |
| 2026-11-23 | v11 | 5 다시 그리기 | face.png 이마의 분홍 앞머리 그림자 확인 → 사용자 판단으로 그대로 사용, 실행 안 함 |
| 2026-11-23 | v12 | 8 최종 확인(miku 기준 설명) | review_seethrough.py에 step27_hidden_parts.png 추가(레이어별 가려지는 부분). miku 현재 PSD: face 66% · back hair 33% · handwear 31% 가려짐. handwear 오른팔 안쪽 순서 확인 필요 |
| 2026-11-23 | v13 | 11 prompt.md 검토 | LayerDiff 구조 분석(RGBA 생성, depth 아님, 태그 13·11 고정), 옵션 목록, 조각 수(headwear 4) 정리 → open-items 11번 |
| 2026-11-23 | v14 | 11.3 tblr_split | ① 새 PC 재실행 `seethrough_test/miku_tblr` 356s, peak 7.98GB: 같은 seed인데 생성이 달라져 headwear 0px(헤드셋 통째로 사라짐, PSNR 22.4). ② 이전 생성물에 PSD 조립만 tblr로 `seethrough_test/miku_tblr_old` (2초): 18레이어, handwear-r 0.44(topwear 앞) · handwear-l 0.74(legwear 뒤), PSNR 23.4. review_seethrough.py: 이름을 PSD에서 읽고 -l/-r 레이어 지원 |
| 2026-11-23 | v15 | seed 탐색 | tools/seed_search.ps1: seed 0에서 headwear 15,541px(318s) → 멈춤. tools/compare_seeds.py로 seethrough_test/seed_compare.png(이전PC seed42 · 새PC seed42 · seed0). seed0: 헤드셋 4조각 온전, 대신 face 0px · back hair 뒤통수 빠지고 트윈테일만(168,800px). PSD PSNR 21.6 |
| 2026-11-23 | v16 | 11.2 머리 자르기 반복 | tools/head_grow.py + run_patched.py 소스 치환, -HeadGrow N. seed0 테스트(445s): pass0 [487,164,883,592] 위·왼쪽 닿음 → pass1 [416,88,883,592] 닿음 없음 → 종료. 헤드셋 4조각 상자 안, step26 헤드셋 빠짐 사라짐. seed1~7(원래 여백) 결과는 seethrough_test/miku_seed1~7에 보존 |
| 2026-11-23 | v17 | seed 0~9 + HeadGrow 3 | seethrough_test/miku_grow_seed0~9, seed당 312~573s. 비교표 seethrough_test/seed_compare_grow.png (tools/compare_seeds.py). headwear 있음: s0 s2 s4 s6 s8 s9 / 없음: s1(footwear로 감) s3(pass0엔 있었는데 확장 후 사라짐) s5 s7. face 온전: s2 s4 s9 등, 빈 것 s0 s7 s8. 뒤통수 온전: s4 s6 s9. PSD PSNR 최고 s9 26.9 · s4 26.7 |
| 2026-11-23 | v18 | 원격 공유 | github.com/borry345/tmpday2 master에 miku_seeds/ 푸시(370c255, 110MB): seed_compare_grow.png · s0~s9·oldPC42별 layers/ · review/ · README.md |
| 2026-11-24 | v19 | seed 조합 pick1 | 사용자 선택대로 tools/mix_layers.py(스펙 seethrough_test/mix/miku_pick1.json) → seethrough_test/mix/miku_pick1: 17레이어 PSD(neck 꺼짐), PSNR 27.2dB, 빠짐 2,014px · 넘침 26px. s0 back hair 좌우 분리 → tail_left/right, oldPC42 back hair − s0 트윈테일 → back_center(시도). mouth 깊이 0.43 고정. 깊이 순서 tail_left 0.890 < back_center 0.898 < tail_right 0.906. GitHub miku_mix/ 푸시(37ad766) |
| 2026-11-24 | v20 | pick1 입 수정 | s1 mouth 가장자리 반투명 회색 테두리가 수염처럼 보임 → mix_layers.py에 rgb_from:"src"(알파는 레이어, 색은 원본 — See-through 입·코 처리와 같음), mouth에 적용. 확대 비교로 원본과 같음 확인. GitHub 갱신 |
| 2026-11-24 | v21 | pick1 전 레이어 원본 색 | 눈 흰자 가장자리 선 지적 → mix_layers.py visible_rgb:"src": 앞→뒤로 보이는 픽셀(alpha≥16)에 원본 색, 반투명이면 불투명(≥250) 레이어까지 밑 레이어도 원본 색, 가려진 부분은 생성 색 유지. PSNR 27.2→32.3dB, 색 차이(노랑) 사라짐, 남은 빨강 2,014px = 바깥 윤곽선·헤드셋 옆 |
| 2026-11-24 | v22 | back_center 재생성 (pick2) | text_layers.py: oldPC42 back hair → tail_left 87,564 · tail_right 76,912 · back_center 71,662px(+LaMa 1,398px), 찌꺼기 없음. amodal_complete.py front=트윈테일(oldPC42+s0): hull 49s(오른쪽 직선 잘림 남음) · key 66s 후보3 → seed1 채택(색 오차 2.8). mix_layers.py에 png·keep_rgb 옵션. 머리카락 3장 keep_rgb → 레이어에 다른 부위 선 안 찍힘, PSNR 30.0dB. 남은 점: back_center 오른쪽 보라 테두리. GitHub 푸시 |
| 2026-11-24 | v23 | 7·8단계 (pick2) | mix_layers.py: fill_missing(빠진 1,846px → 가까운 레이어, 원본 픽셀) · despill magenta(back_center 488px) · hidden.png(레이어별 가려지는 부분). 결과 빠짐 0px · 넘침 26px · PSNR 30.9dB. hidden.png에서 윤곽 안 구멍 없음 확인. 가려짐: back_center 91% · eyewhite 80% · face 63% · handwear-r 43% · bottomwear 42%. GitHub 푸시 |
| 2026-11-24 | v24 | 레이어 검은 선 원인 | visible_rgb가 다른 부위 선을 레이어에 찍음(seed 간 모양 1~3px 어긋남 + 반투명 가장자리 밑 체인). 시도: 차이 60 이하만 복사·큰 차이 반투명 지움 → 레이어는 깨끗해졌으나 합성 계단 현상, 눈만 적용도 어색 → 폐기. 두 버전으로 정리: A miku_pick2_srccolor(PSNR 30.9, 레이어에 남의 선) / B miku_pick2_clean(생성 색, mouth만 원본, PSNR 27.8). mix_layers.py에 rgb_thr 가드·halo 지우기 추가(기본 동작에 포함). variants_compare.png |
| 2026-11-24 | v25 | pick2 C: 색 기준 픽셀 주인 (visible_rgb "owner") | A(합성)+B(깨끗) 둘 다 목표. mix_layers.py owner_assign: 원본 픽셀마다 2px 안 생성 색이 맞는 맨 앞 레이어가 주인(윤곽선은 덮는 레이어에서 4px), 주인만 원본 RGBA·앞 레이어는 비움·뒤는 생성 색, 깊은 안쪽은 구멍 안 냄, 안쪽 어두운 선이 생성 색과 다르면 생성 색 유지(눈4·mouth 제외 owner_guard:false). 경과: 54.4dB지만 face 구멍 201px → 깊은 안쪽 규칙 → 안쪽 차이 전부 생성 색은 눈 윤곽·"01" 깨짐(32.9dB, 폐기) → 어두운 선만 **41.0dB**. 검증 owner_zoom·owner_cmp1/2·hidden.png(구멍 없음), 빠짐/넘침 0. 남은 점: face 옅은 흔적, legwear 허벅지 위 얇은 선, eyewhite 살색 테두리, 바깥 윤곽 일부 들쭉날쭉. 새 도구 compare_variants.py. GitHub 491ff86 |
| 2026-11-24 | v26 | 레이어 선 90% 지우기 (pick2_v26) | 측정 tools/layer_marks.py: "선" = 다른 부위 경계 3px 안에서 생성본보다 40 이상 어두워진 픽셀, "이음매" = 그 밖의 새 경계(Canny). A 선 2,706px 기준. 조합(mix_layers.py align flow/sam2, blend poisson/poisson_seam, line_front, bd_guard, guard_hand): C 33% · 블렌딩(S/P)은 회색 번짐으로 오히려 악화(74~77%) · flow(E) 평균 0.5px 이동이라 효과 없음 · SAM2(D)는 eyewhite IoU 0.10 등 눈 레이어를 비움(탈락) · line_front 8(CF) 32% · +bd_guard 3(CFG) **2%**지만 합성 눈썹·턱선 끊김(PSNR 37.8) · +guard_hand 6(CFGH6) **선 2%(98% 제거) · PSNR 40.3dB** → 최종 miku_pick2_v26. 검증 v26_marks_CFGH.png · v26_zoom.png · v26_cmp1/2.png · hidden.png 구멍 없음. 남은 점: "01" 0자 왼쪽 일부 생성 모양, 왼눈 속눈썹 끝·오른쪽 턱선 약간 들쭉날쭉, 앞 레이어(front hair) 바깥 윤곽에 넘겨받은 선 조각, eyewhite 살색 테두리, 이음매는 66% 남음 |
| 2026-11-24 | v27 | pick3: 레이어별 방식 선택 + headwear 고리 분리 | 사용자 선택: 전부 B(생성 색), handwear-l만 A(원본 색, "01" 보존). headwear는 s6 objects(닫힌 고리 + 온전한 오른쪽 스피커)로 교체, 사용자가 objects_boxed.png에 빨간 선으로 표시한 고리 뒤쪽을 floodFill로 마스크 → headwear/parts/ 6조각: ring_l/r_back(2,773·3,899px, 깊이 0.95 모든 머리 뒤), ring_l/r_front(6,700·6,514px, 0.60 front hair 뒤·트윈테일 앞), speaker_l(4,046px, 0.58), speaker_r(3,035px, 원본에서 머리에 가려 0.95). mix_layers.py: split에 top/bottom 조합 추가, 검사 이미지 글자 한국어(맑은 고딕). 결과 seethrough_test/mix/miku_pick3: 22레이어, 빠짐/넘침 0, PSNR 28.7dB, 새 경계 28px. 검증 zoom.png(원본|B|pick3), sheet.png, hidden.png 구멍 없음, 고리 뒤 84~86% 가려짐 |
| 2026-11-24 | v28 | pick3 headwear 채우기 제외 | 질문: mix의 ring_l_front가 parts 파일과 다름 → 원인: fill_missing이 원본에서 아무 레이어도 덮지 않은 고리 위 오른편 모서리 173px를 가장 가까운 레이어(ring_l_front)에 원본 픽셀로 붙임. 사용자 선택: 군더더기 없이(2번). mix_layers.py 레이어 옵션 no_fill 추가(그 레이어가 가장 가까운 빈 픽셀은 비워 둠, 다른 레이어로 넘기지 않음), headwear 6조각에 적용. 결과: 6조각 = parts 파일과 동일(알파 1~15 희미한 픽셀만 원래대로 제외), 합성 빈 곳 314px(고리·스피커 바깥 윤곽선, zoom_nofill.png), PSNR 28.4dB |
| 2026-11-24 | v29 | pick4: 사용자 지정 레이어 순서 | 순서(앞→뒤) handwear-l > front hair > eyelash > irides > eyewhite > eyebrow > mouth > face > speaker_l > ring_l_front > topwear > bottomwear > legwear-l > legwear-r > tail_left > back_center > handwear-r > ring_r_front > tail_right > ring_l_back > ring_r_back (깊이 0.02~0.92 고정). neck·speaker_r 제거(목록에 없음). legwear는 두 다리가 허벅지에서 8px 붙어 있어 연결 조각 분리 실패 → mix_layers.py split_cut(가운데 40%에서 픽셀이 가장 적은 세로줄 x=540에서 자름) → 16,717/16,558px. 결과 seethrough_test/mix/miku_pick4: 21레이어, 빠짐 312px(headwear no_fill), PSNR 28.3dB. pick3 대비 합성 653px 변화: 오른쪽 고리 앞 왼쪽 윤곽을 back_center가 덮음(~760px 영역), 속눈썹이 눈동자 위로(~640px 영역). 검증 order_check.png · order_zoom.png · hidden.png 구멍 없음 |
| 2026-11-24 | v30 | pick4 handwear-l 수동 수정본 반영 | 사용자가 tmp/05_handwear-l.png를 직접 다듬음(기존 대비 609px 지움, 22px 색 변경) → manual/handwear-l.png로 복사, spec에 png + keep_rgb + no_fill. 첫 실행에서 기존 옵션 split:left가 한 조각짜리 수정본에 적용돼 레이어가 비는 문제 → split 제거 후 재실행. 결과: 레이어 = 수정본과 픽셀 동일, 합성 빈 곳 312→534px(어깨 바깥 윤곽선·손가락 아래 가는 선), PSNR 28.0dB. 검증 manual_handwear_check.png(원본|수정 전|수정본|빈 곳) |
| 2026-11-24 | v31 | pick4 빨간 선 안쪽 제거 | 사용자가 tmp/composite.png에 빨간 선 4곳 표시(고리 위 3곳, 목 왼쪽 1곳) → 원본 보관 manual/composite_red_marks.png, pick4 합성과 다른 빨간 픽셀을 선으로 보고 floodFill(4연결)로 안쪽 마스크. mix_layers.py 레이어 옵션 erase(마스크 흰색 제거, fill_missing 뒤 맨 마지막 적용) 추가. 안쪽만 지우면 선 자리 점이 남아(erase_check.png 3행) 선까지 포함 마스크 manual/remove_with_line.png로 확정: front hair 38 · topwear 32 · back_center 150px 제거. 합성 빈 곳 749px, PSNR 27.7dB, 주변 윤곽선 유지 확인 |
| 2026-11-24 | v32 | miku 레이어 1차 확정 | 사용자 "이대로 만족하고 출발" → pick4를 final/miku_v1/로 복사: miku_v1.psd(1024, 21레이어, 순서 handwear-l … ring_r_back), layers/ 00~20 PNG, composite·sheet·hidden.png, mix.json, spec.json(재현용, i2l 기준 상대경로: headwear/parts, manual/). 남은 점(미룸): 레이어 잔선 정리 |
| 2026-11-24 | v33 | 작업 흐름 문서 | 사용자: 파이프라인으로 묶기엔 수작업이 많아 흐름·문제·해결만 기록 → i2l/WORKFLOW.md 작성 (1 작업 흐름 8단계, 2 mix_layers spec 옵션 표, 3 문제와 해결법: 생성·합치기·검은 선 실험, 4 사람이 판단한 곳, 5 남은 일) |
| 2026-11-24 | v34 | 17.3 코드 정리: 하드코딩 경로 제거 | 사용자 선택: i2l 원본 tools도 같이 수정. text_layers.py · mask_inpaint.py · diag_te.py: `ROOT = I2L_ROOT 환경변수 또는 tools/..` 기준으로 HF_HOME · TORCH_HOME · see-through 경로. run_seethrough.ps1 · seed_search.ps1: `$root = $env:I2L_ROOT 또는 $PSScriptRoot/..` 기준으로 HF_HOME · see-through · env python · run_patched. 확인: 남은 절대경로 0개(make_archive.py는 개인 경로라 저장소 제외 예정), 세 py의 ROOT = i2l, ps1 문법 오류 0개, root 아래 env·see-through·hf_cache 존재 |
| 2026-11-24 | v35 | 17.3 코드 정리 완료 | 저장소 작업 폴더: <저장소 폴더> (빈 원격 clone, master). i2l/repo_export.py(저장소 미포함): 목록에 있는 파일만 복사 — tools 15개, tools/experimental/diag_te.py, LICENSE(See-through의 Apache-2.0 원문), requirements-lock.txt(freeze_new.txt = 현재 env, cu128 인덱스 머리말), NOTICE(See-through 출처·각색 파일 2개), .gitignore. 제외: make_archive.py(이 PC 경로), _selftest/(출력). selftest_psd_report.py는 psd_report를 같은 폴더에서 불러서 tools/에 둠. head_grow.py · run_patched.py 머리말에 See-through 출처(커밋 e4cb250, Apache-2.0) 추가. diag_te.py는 위로 올라가며 tools 폴더를 찾게 바꿔 experimental/에서도 ROOT 정상. lock과 현재 env 차이는 setuptools 하나(78.1.0), see-through 클론은 수정 없음(e4cb250) |
| 2026-11-24 | v36 | 17.4.1 README + 예시·발췌 이미지 | i2l/repo_docs/README.md 작성(개요, 원본·합성·시트 이미지, 할 수 있는 것, 문서 표, 빠른 시작, examples 표, 모델·라이선스 표, 라이선스). 처음 쓴 "seed당 2~3분"은 근거 없는 값이라 summary.txt로 확인해 "312~573초(약 5~10분), GPU 약 8GB"로 수정. repo_export.py에 README, examples/miku(input·final·headwear·manual·back_center), docs/images(seed 비교, head_grow seed0, seed9 review, pick_sheet, 색 A/B·owner, 잔선 v26, no_fill, 순서·수동·지우기 확인) 추가 → 103파일, 33MB(최대 PSD 7.4MB). README 링크 확인: 파일·이미지 모두 있음, docs/*.md 6개는 다음 단계에서 작성 |
| 2026-11-24 | v37 | 17.4.2 INSTALL + 자체 테스트 수리 | repo_docs/docs/INSTALL.md (0 준비물 ~ 8 설치 확인, 저장소 폴더 기준, I2L_ROOT, 절대 경로 주의). README 모델 표에 juggernautXL(설정 파일만 참조) 추가. 설치 확인 명령으로 넣은 selftest_psd_report.py를 실제로 돌리니 실패 → ① psd-tools 1.14는 Group.new(parent, name) 순서 ② PSDImage.new("RGB")로 만든 PSD는 topil()에서 투명도가 사라짐(알파 255) → "RGBA"로. 수정 후 SELFTEST OK(PSNR inf). 같은 의심으로 final/miku_v1.psd 검사: mix_layers는 RGBA로 만들어서 레이어 알파·색이 PNG와 완전히 같음(이상 없음) |
| 2026-11-24 | v38 | 17.4.3 ENVIRONMENT + venv/conda 호환 | 이 PC의 env는 conda가 아니라 venv(Python 3.12.5, env\Scripts\python.exe)임을 발견. INSTALL은 conda(env\python.exe) 기준이라 run_seethrough.ps1이 깨질 뻔함 → run_seethrough.ps1 · seed_search.ps1이 env\Scripts\python.exe → env\python.exe 순서로 찾게 수정(없으면 오류 메시지), 문법 오류 0. INSTALL 2단계를 venv(테스트한 방법) + conda(대안)로 다시 씀. repo_docs/docs/ENVIRONMENT.md: PC B(i7-14700, 32GB, RTX 5060 Ti 16GB, 616.92) / PC A(RTX 3070 8GB, 616.86), 패키지 버전(실측), 디스크, See-through seed 0~9 시간 312~573초·GPU +8.0GB, 다른 도구 시간(mix_layers 11초 실측, text_layers 38초는 기록) |
| 2026-11-24 | v39 | 17.4.4 WORKFLOW | repo_docs/docs/WORKFLOW.md: 7단계 흐름(✋ 사람이 고르는 곳 표시), head_grow 설명(두 단계 생성, 닿음 판정 2px·8px, 0.25배씩 최대 1배, 같은 난수 상태, 주의점), seed 비교·review 이미지 표, spec 예시, 가려진 부분 생성(text_layers·amodal hull/key), 색 방식 A/B, 레이어 손질 표(objects·경계 그리기·no_fill·split_cut·depth·수동 png·erase·hidden), 단순한 경우(hair_input), 사람이 판단한 곳. review_seethrough.py 사용법을 실제 인자(--run, --src)로 고침. 링크 검사: 아직 안 쓴 TOOLS·TROUBLESHOOTING·HISTORY만 없음 |
| 2026-11-24 | v40 | 17.4.5 TOOLS · 17.4.6 TROUBLESHOOTING · HISTORY | TOOLS.md: 도구 표 + 도구별 사용법·인자(코드의 argparse에서 뽑음)·함수·출력, mix_layers spec 레이어/전체 옵션 표. TROUBLESHOOTING.md: 설치 · 8GB 실행 시도 6단계 · 생성 결과 · SDXL 다시 그리기 · 합치기 · 레이어 남의 검은 선(원인 3가지, 시도 6개, 결론, 측정 주의) · 도구·환경. HISTORY.md는 repo_export.py가 log.md에서 만들고 절대 경로를 <i2l>·<저장소 폴더>로 바꿈. 확인: 108파일, 문서 링크 모두 실제 파일, 제목 앵커 오류 0, HISTORY에 절대 경로 없음 |
| 2026-11-24 | v41 | 17.5 민감 정보 점검 | 저장소 폴더 전체 검색(사용자명·절대 경로·이메일·HF/GitHub/API 토큰·세션 링크): 글 파일 1건(review_seed9/review.md의 절대 경로) → repo_export.py가 복사한 .md/.json/.txt 전부에 경로 치환 적용 → 0건. png/psd 바이너리 안 문자열 0건. 사용자 편집 PNG 3장의 XMP는 Orientation=1과 Windows 이미지 앱 고정 UUID뿐(개인 정보 없음). .gitignore 시험: env·hf_cache·see-through·outputs·tmp 모두 무시됨. 다른 저장소 언급: HISTORY에 github.com/borry345/tmpday2 1건(사용자 본인 저장소, 그대로 둠) |
| 2026-11-24 | v42 | 17.6 검증 중 발견: -File 배열 문제 | 문서의 `powershell -ExecutionPolicy Bypass -File tools\run_seethrough.ps1 -Extra @(...)`를 시험 → -File로 부르면 배열의 첫 값만 전달(Extra count=1)되어 --tblr_split·--seed가 조용히 빠짐. README·INSTALL·WORKFLOW·TOOLS를 `Set-ExecutionPolicy -Scope Process Bypass` + `& tools\run_seethrough.ps1`로 고치고, TROUBLESHOOTING에 이 문제와 "BOM 없는 .ps1의 한글 문자열 파싱 오류"(검증 스크립트에서 실제로 겪음) 추가. 저장소 .ps1은 run_seethrough=BOM, seed_search=ASCII라 해당 없음. 검증 스크립트 i2l/verify_install.ps1(저장소 미포함): C:\ 루트는 쓰기 권한 없어 <사용자 폴더>\i2l_verify에서 새 venv로 INSTALL 2~8단계 실행 중 |
| 2026-11-24 | v43 | 17.6 검증 통과 | verify_install.ps1로 <사용자 폴더>\i2l_verify에 INSTALL을 그대로 따라 함(모델만 기존 hf_cache junction): venv → pip → torch cu128(1분54초) → see-through clone·e4cb250·assets junction·requirements(1분57초) → SAM2 → freeze → selftest OK → run_seethrough seed0(497초, EXIT=0, ARGS에 --tblr_split --seed 0 전부 전달) → 모두 OK, 약 13분. 레이어 27장이 원래 환경 seed0과 픽셀까지 동일(같은 PC·seed는 재현됨) → ENVIRONMENT에 추가. freeze는 lock과 4개 패키지만 패치 버전 차이(charset-normalizer, ipython, packaging, regex; 고정 안 된 의존성). 검증 중 고친 것: 스크립트가 stderr 경고를 오류로 보던 문제(종료 코드로만 판단), C:\ 루트 권한, junction 안전 삭제(rmdir 먼저) |
| 2026-11-24 | v44 | 17.7 커밋·푸시 | 사용자 승인: main 브랜치, 작성자 이메일은 GitHub 비공개 주소(90628321+borry345@users.noreply.github.com, 이 저장소에만 설정). 커밋 f02beb7 (111파일) → github.com/borry345/sd-character-i2l main 푸시. 확인: 원격 main = f02beb7, 공개(public), 기본 브랜치 main, README raw 200. 검증 폴더 <사용자 폴더>\i2l_verify 삭제: junction 2개(hf_cache, see-through\assets)를 rmdir로 먼저 끊고 모델 캐시 크기 15.37GB 전후 동일 확인 후 삭제 |
| 2026-11-24 | v45 | 18 레이어 잔선 조사 (handwear-r) | 사용자 표시 tmp/16_handwear-r.png: 빨간 박스 1곳(x625~643, y672~680, 소매 끝 아래). 단계별 확대(zansun_zoom.png: 원본·s8 생성·gen·최종·표시·합성): 생성 레이어와 gen에는 없고 최종에만 있음 → 박스 안 29px 모두 원본 픽셀과 동일, handwear-r에 덧붙은 132px = mix.json filled_px 132 → 원인은 fill_missing(어느 레이어도 덮지 않은 원본 윤곽선을 가장 가까운 레이어에 원본 픽셀로 붙임). 생성 소매 윤곽이 원본보다 1~2px 위에 있어 그 사이 원본 윤곽선 조각이 끊긴 점선으로 붙음. 명칭·해법 조사: GIS의 sliver polygon(겹침 연산 뒤 생기는 가는 조각, Eliminate = 경계를 가장 길게 공유하는 이웃에 병합), 인쇄의 misregistration → trapping(경계를 살짝 넓혀 틈을 덮음). 이 잔선만 지우는 전용 모델은 찾지 못함 |
| 2026-11-24 | v46 | 19 fill_missing 이해·끈 버전 비교 | 하는 일: 원본에는 불투명한데 어떤 (보이는) 레이어도 덮지 않은 픽셀 → 가장 가까운 레이어에 원본 RGBA 복사. 생긴 이유: v23(pick2) 때 합성 검사에서 빠짐 1,846px(빨강, 대부분 바깥 윤곽선, 레이어에서 3.7px 이내)을 0으로 만들려고 추가. 끈 버전 seethrough_test/mix/miku_pick4_nofill(임시, 확정본 그대로): 빈 곳 2,183px(켰을 때 749px, headwear no_fill·erase 몫) — 바깥 테두리 2px 안 1,907px, 안쪽 276px, 어두운 선 픽셀 1,999px, 조각 757개(크기 중앙값 1px, 1~3px 조각 682개, 최대 193px). PSNR 27.7 → 27.6dB. 비교 이미지 fill_compare.png |
| 2026-11-24 | v47 | 20 fill_missing 삭제 | 사용자: 얻은 것보다 잃은 게 많으니 아예 지우기. mix_layers.py에서 fill_missing·no_fill 코드 삭제(spec에 남아 있으면 안내만 출력하고 무시). assemble_layers.py의 같은 방식은 원본에서 잘라 낸 레이어용이라 유지(hybrid/hair_input final_v2: 763px 메움). pick4 spec에서 두 키 제거 후 재실행 → 끈 버전(miku_pick4_nofill)과 레이어 21장 모두 동일, 모든 레이어에서 생성본에 없던 픽셀 0, handwear-r 잔선 박스 = 생성본(71px). 확인 이미지 fill_removed_handwear_r.png. final/miku_v1 갱신(PSD 21레이어 = PNG). 바뀐 레이어 10장 = 예전에 채우기를 받은 레이어와 일치. 문서: WORKFLOW(spec 예시·빈 곳은 비워 둔다는 설명·no_fill 행 삭제), TOOLS(옵션 표에서 삭제 + 삭제 안내), TROUBLESHOOTING("레이어에 점선 같은 잔선" 절: 원인·명칭(슬리버·정합 오차)·해결·전후 표·이미지). docs/images: no_fill.png 빼고 fill_removed_handwear_r.png·fill_compare.png 추가. 링크·앵커 오류 0 |
| 2026-11-24 | v48 | 21 목 붙인 topwear 반영 | 사용자 수정본 tmp/10_topwear_new.png → manual/topwear.png, pick4 spec topwear = png + keep_rgb (erase는 수정본에 이미 반영돼 뺌). 수정본: 목 512px 추가(x506~538, y430~448, 알파 중앙값 253), 옷깃 위 107px 색 변화, 그 밖 1,420px은 값 1~2 차이(저장 시 반올림으로 추정). 결과: topwear 레이어 = 수정본 픽셀 동일, 합성 변화 1,676px 중 1,662px은 값 1~2, 14px은 3~20, 20 초과 0(눈으로 차이 없음, topwear_neck_result.png). 목은 정지 합성에서 100% 얼굴·앞머리 뒤. 머리 움직임 미리 보기(neck_tilt_zoom.png): ±12° 회전은 목 있고 없고 차이 0~4px(턱이 옷깃 근처에 머묾), 머리를 위로 10px·20px 올리면 목 없을 때 빈 틈(216·522px)이 목으로 채워짐. 20px 근처가 한계(목이 턱 밑으로 들어간 깊이 19~26px). 목 양옆에 윤곽선이 없음. final/miku_v1 갱신 |
| 2026-11-24 | v49 | fill_missing 삭제 + 목 topwear 커밋·푸시 | 사용자 승인. WORKFLOW 레이어 손질 표에 "움직일 때 드러날 부분 그려 넣기(목)" 행 추가, docs/images에 topwear_neck_result.png·neck_tilt_zoom.png 추가 |
| 2026-11-24 | v50 | 민감 정보 누락 발견·수정 | 커밋 전 재검사에서 docs/HISTORY.md v42·v43 줄에 <사용자 폴더>\i2l_verify 경로 발견. 이미 올라간 커밋 f02beb7에도 있음(17.5 검사 뒤에 추가된 기록을 커밋 전에 다시 검사하지 않음). repo_export.py 치환 규칙에 사용자 폴더(~) → <사용자 폴더> 추가 → 재검사 글·바이너리 0건 |
| 2026-11-24 | v51 | 커밋·푸시 | 커밋 3996480 (27파일: mix_layers fill_missing 삭제, 확정본 재생성·목 topwear, 문서·이미지 4장, HISTORY 경로 가림) → main 푸시, 원격 main = 3996480. 남은 일: 첫 커밋 f02beb7의 HISTORY에는 사용자 폴더 경로가 기록에 남아 있음(지우려면 기록을 다시 쓰고 강제 푸시 필요, 사용자 결정 대기) |
| 2026-11-24 | v52 | 첫 커밋 기록 처리 결정 | 사용자: f02beb7의 사용자 폴더 경로는 그대로 둠(기록 다시 쓰기·강제 푸시 안 함) |
| 2026-11-24 | v53 | 19 amodal_complete.py --debug | `--debug` 추가: <out>_dbg_01_visible · 02_region · 03_mask2(key는 seed마다) · 04_prefill(hull) png + <out>_dbg.json(픽셀 수, 자른 범위, 후보 색 오차, 고른 seed). back_center(v22 명령 그대로)로 hull·key 실행 → 기존 결과와 다른 픽셀 0. debug_sheet.png 확인: hull 마스크2는 그려도 되는 영역 51,933px 중 2,814px뿐 → 오른쪽 직선 잘림의 원인. TOOLS·TROUBLESHOOTING 문서, repo_export에 시트 이미지 추가 (저장소 푸시는 안 함) |
| 2026-11-24 | v54 | 앞으로 할 일 등록 | open-items에 20 저장소 반영 · 21 리깅용 레이어 분리 · 22 목 보강(선택) · 23 남은 개선(9, 11.12, 11.6) 등록. 사용자가 미룬 일 3건(--debug 2건, 잔선 정리)을 직접 지움 |
| 2026-11-24 | v55 | 20 저장소 반영 준비 | 사용자 결정: amodal_debug_test 폴더를 예시에 포함, 커밋·푸시 승인. 추가로 넣은 것: 잔선이 생기는 단계 6칸(lines_stage_zoom.png → TROUBLESHOOTING 잔선 섹션), 머리 ±12° 기울임(neck_tilt_preview.png → WORKFLOW 손질 표), WORKFLOW 가려진 곳 그리기에 --debug 안내와 디버그 시트 |
| 2026-11-24 | v56 | 20 커밋·푸시 | 민감 정보 재검사(글·이미지): 사용자 폴더·이메일 0건(HISTORY에는 가려진 <사용자 폴더>\i2l_verify만). 커밋 ed92ece (26파일: amodal --debug, 문서 3개, 이미지 3장, amodal_debug_test 예시) → main 푸시, 원격 main = ed92ece |
| 2026-11-24 | v57 | 21.1 움직임 정함 | 사용자: 앞모습만. 가만히·눈깜빡·입모양·걷기·의자 앉기·무릎 꿇기·노래·드래그로 들림·쓰다듬·누워 자기·앉아서 일하기·좋아하기·환호 등. 리깅 도구는 미정. 21.2 분리 목록 초안(나누기 A1~A8, 새로 그리기 B1~B6, 3단계) 제시, 확인 대기 |
| 2026-11-24 | v58 | 21.1 시점 정정 | 사용자: 앞모습은 안 보여줌, 항상 사이드뷰("억지 측면"). 지금 그림(화면 왼쪽으로 돈 3/4)을 측면으로 쓰고 반대 방향은 반전하는 것으로 해석, 분리 목록을 앞팔·뒷팔 / 앞다리·뒷다리 기준으로 수정해 확인 요청 |
| 2026-11-24 | v59 | 21.2 분리 목록 확정 | 사용자 확인: 측면 = 지금 그림, 반대 방향은 좌우 반전, 1단계(다리·팔·트윈테일) 순서, 눈 좌우 분리 필요. 새 일러(miku_chibi_smile.png)는 v1과 머리·팔·다리 위치가 달라 부품으로 못 씀(smile_vs_v1.png) → 표정은 v1 원본을 "표정만 바꾸는" 편집으로 받기로. open-items 21.3을 항목별로 펼침 |
| 2026-11-24 | v60 | 범위 확인 | 사용자: 항상 측면만 보여줌(뒤돌기·정면 없음), 에셋 늘리기는 최소로. 분리·채우기는 측면 동작에서 드러나는 곳만 |
| 2026-11-24 | v61 | 21.3 A4 다리 무릎 나누기 | 새 도구 tools/split_joint.py(자르는 선 + 관절 캡 + 굽힘 확인 시트). legwear-l/r을 긴 축 0.56(하늘색 점 아래)에서 thigh/shin으로 나눔. 캡: 원본 픽셀 복사는 점이 겹쳐 보여 → 스타킹 색 원 + 윤곽선, 허벅지 아래 불투명한 곳에만. 곧은 자세 원본 대비: 밖으로 나온 px 0, 달라진 px 6·11. legs_joint_check.png로 ±30·60° 굽힘 확인. 결과: seethrough_test/rig/legs |
| 2026-11-24 | v62 | 표정 편집본 확인 | 사용자 정정: 에셋 수가 아니라 "AI 모델이 만들 수 없는 에셋"이 곤란함. 사용자가 miku_chibi_{calm,smile,ah,ee,oh,surprised,sleeping}.png 7장 생성(원본과 같은 1312×1199). 원본과 비교: 몸·머리·옷 위치 그대로, 바뀐 곳은 얼굴(눈·입·홍조·땀)과 다시 그려진 윤곽선 1~2px. 얼굴 주변 이동량 x -0.1~-0.9, y -0.4~-1.5px → 위치 보정으로 맞출 수 있음. 확인: seethrough_test/expr/diff_sheet.png, faces.png |
| 2026-11-24 | v63 | A4 수정 | 사용자: tmp/12·13 legwear 빨간 선으로 자르기, 아래 조각(종아리·하박)이 앞, 앞 조각에 관절 캡 + 검정 외곽선. split_joint.py: --front second(기본), 캡 = 뒤 조각 쪽 원본 픽셀(반지름 = 폭/2) + 원호 외곽선 4px(다리 윤곽선 색 [9,10,11]). 굽혀도 무릎이 둥글고 계단 없음. 곧은 자세에서는 원호 선이 무릎 선처럼 보임. 표정 7장 See-through seed1 HeadGrow3 백그라운드 실행 시작 |
| 2026-11-24 | v64 | A4 관절 외곽선 방법 1 | 사용자 선택: 관절 외곽선을 따로 떼어 맨 뒤로. split_joint.py: 앞 조각 캡은 외곽선 없이(반지름 폭/2-4px), 외곽선 링은 <앞조각>_joint_line.png(앞 조각 뼈에 붙이고 뒤 조각보다 뒤에 그림), 뒤 조각도 앞쪽 원본 픽셀을 반지름만큼 가짐(안쪽 홈 메움), 링은 캡과 1px 겹침. 곧은 자세: 원 선 안 보임, 원본과 다른 곳은 윤곽선 가장자리 몇십 px. 굽힘 ±30·60°: 바깥쪽만 외곽선, 계단·흰 홈 거의 없음(knee_zoom.png). 그리는 순서 joint.json order_front_to_back |
| 2026-11-24 | v65 | 표정 7장 i2l 실행 | See-through seed1 HeadGrow3 tblr_split, 장당 332~462초, 모두 성공. 눈 감은 표정(calm·smile·sleeping·surprised)은 eyelash만 나오고 irides·eyewhite 0px(맞음). v1에 eyelash·irides·eyewhite·eyebrow·mouth만 바꿔 끼움 → 위치 맞음(expr_swap_v1.png). 남은 점: smile 홍조와 surprised 땀방울은 face 레이어에 들어 있음, surprised face는 아래쪽이 비어 못 씀(17,675px), surprised 입에 살색 테두리. 확인: seethrough_test/expr/expr_layers.png |
| 2026-11-24 | v66 | 2단계 표정 다듬기 | 새 도구 tools/face_parts.py: 원본+표정 7장 → 눈 4종 좌·우(x=540, 모든 표정에서 눈 픽셀 0인 열), 입, 홍조, 땀. 홍조: 표정 face가 원본보다 분홍(Lab a*)인 곳 중 눈 가운데보다 아래·얼굴 가장자리 10px 안쪽·분홍 덩어리만 → smile만 나옴(오검출 oh·sleeping 없앰). 땀: surprised face의 파란 덩어리 + 윤곽 → effects/sweat_drop/(잘라낸 공용 에셋 + source.json에 miku 위치). 입 테두리: 어두운 선·붉은 픽셀과 그 안(이빨)만 남기고 가장 큰 조각만, 200px 미만 작은 입은 그대로 → surprised 796px·oh 132px 살색 고리 제거. 확인: seethrough_test/rig/face/check_swap.png, mouth_clean.png |
| 2026-11-24 | v67 | tmpday2 새로 올림 | 사용자 요청: 기존 내용 싹 지우고 새로. 커밋 5d47e6d(master): 1_legs · 2_expr_input · 3_expr_layers · 4_face_parts · 5_effects + 한국어 README. 예전 miku_seeds·miku_mix·haha.text·pairpair.txt는 지움(기록에는 남음). 경로 검사 0건 |
| 2026-11-24 | v68 | 표정 입 수염 | 사용자 지적: 입 근처 수염. 원인은 v20과 같음(생성 입의 반투명 가장자리가 회색). face_parts.py에 v20 해결법(rgb_from src: 모양은 레이어, 색은 각 실행의 src_img.png) 적용 후 테두리 정리 → base·calm 회색 테두리, smile 입 밖 검붉은 번짐, sleeping 입 아래 갈색 선 사라지고 원본 그림과 같음(mouth_whisker_fix.png). tmpday2 4_face_parts 갱신 |
| 2026-11-24 | v69 | 입·코 색 공용 함수 + 저장소 반영 | 사용자: 안 헷갈리게 공용 함수로. tools/layer_common.py rgb_from_src → mix_layers(rgb_from src)·face_parts(입)가 같이 씀. 검증: miku_pick4 재생성 21레이어 = final/miku_v1 (다른 레이어 0), face_parts 74파일 동일. 문서: TROUBLESHOOTING "0. 공통 규칙"(수염, 어느 도구든)·"리깅용 나누기" 표, TOOLS에 split_joint·face_parts·layer_common, WORKFLOW "8. 리깅용 나누기". repo_export: 도구 3개, rig 이미지 3장, examples/miku/rig, effects/ |
