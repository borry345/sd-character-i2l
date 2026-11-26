# miku_v1 (레이어 PSD, 21레이어)

그림 한 장을 **부위별 레이어 PSD**로 나눈 결과예요. 작업 흐름 1~7단계(seed 생성 → 고르기 → 합치기 → 가려진 부분 생성 → 색 → 손질 → 확정)의 최종본이에요.
리깅용으로 더 잘게 나눈 버전은 [final_v2](../final_v2/README.md)에 있어요.

## 무엇이 들어 있나
- `miku_v1_stretchy.psd` : [Stretchy Studio](https://github.com/MangoLion/stretchystudio)용 PSD (`seethrough_test/rig/export_stretchy.py`)
  - 레이어를 그림 범위로 잘라 저장했어요. 원래 PSD는 레이어가 모두 1024 전체 크기라, Stretchy가 범위로 뼈를 추정하면 엉뚱해져요.
  - 이름을 See-through 태그로 바꿨어요(`front hair`, `back hair`, `handwear-l` …). 
  - **좌우는 캐릭터 기준**이에요(우리 `_l` = 그림 왼쪽 → `-r`). Stretchy의 뼈대가 캐릭터 본인의 왼쪽에 `leftArm`을 두기 때문이에요.
  - 바꿔 끼우는 파츠는 넣지 않았어요(숨긴 레이어도 모두 가져와서 리깅해 버려요). 이름 대응표는 같은 이름의 `.json`이에요.
  - 가져오기 마법사에서는 DWPose(AI 자세 인식)를 고르세요. 범위 추정 방식은 손목·발목을 잘못 잡아요(작업 폴더 `seethrough_test/rig/stretchy_check.png`).
- `miku_v1.psd` : 21레이어 PSD (위 레이어가 앞)
- `layers/NN_이름.png` : 같은 21장을 PNG로 (번호가 작을수록 앞, 1024 캔버스)
- `composite.png` : 21장을 쌓은 그림. 원본과 같아요(보이는 픽셀은 모두 원본 색).
- `hidden.png` : 레이어마다 다른 레이어에 가려진 부분까지 보여 주는 확인 그림
- `sheet.png` : 레이어를 한 장씩 늘어놓은 시트
- `spec.json`, `mix.json` : 레이어마다 어느 seed·어느 처리를 골랐는지 (`mix_layers.py` 입력과 기록)

## 레이어 (앞 → 뒤)
| 묶음 | 레이어 |
|---|---|
| 팔 | `handwear-l`(앞 팔), `handwear-r`(뒤 팔). 팔 하나가 소매·맨팔·손을 모두 포함한 한 장 |
| 머리카락 | `front_hair`, `tail_left`, `tail_right`, `back_center`(트윈테일에 가려진 뒤통수를 새로 그림) |
| 얼굴 | `eyelash`, `irides`, `eyewhite`, `eyebrow`, `mouth`, `face`. 눈은 좌우가 한 장 |
| 헤드셋 | `headwear_speaker_l`, `headwear_ring_{l,r}_front`, `headwear_ring_{l,r}_back` (고리를 앞/뒤로 나눠 머리를 감싸게) |
| 옷·다리 | `topwear`, `bottomwear`, `legwear-l`, `legwear-r`. 다리 하나가 허벅지~발까지 한 장 |

## 언제 쓰나
- **리깅 없이 레이어만 필요할 때:** 배경 지우기, 부분 색 바꾸기, 가벼운 움직임(머리 흔들기, 헤드셋 고리 앞뒤), 일러스트 편집처럼 "부위별로 나뉘어 있고 가려진 곳이 채워져 있으면 되는" 일.
- **v2를 만드는 재료:** v2는 이 레이어들을 관절·손목·트윈테일·눈 좌우에서 더 자른 것이에요. v2를 다시 만들거나 다른 방식으로 나눌 때 여기서 시작해요.
- **비교 기준:** v2의 기본 레이어를 쌓으면 이 그림과 같아야 해요(`final_v2/v1_diff.png`).

## 이것만으로는 부족한 것 (그래서 v2)
- 팔·다리가 한 장이라 팔꿈치·무릎에서 굽힐 수 없어요.
- 손 모양·표정을 바꿔 끼울 파츠가 없어요.
- 트윈테일이 한 장이라 흔들 때 휘어지지 않아요.
- 눈이 좌우 한 장이라 한쪽만 감기·윙크를 못 해요.
