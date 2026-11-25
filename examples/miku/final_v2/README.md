# miku_v2 (리깅용 확정본, 1024 캔버스)

옆모습(왼쪽 보기) 하나만 씁니다. 오른쪽 보기는 리그 전체를 좌우 반전합니다. 이름의 l/r, left/right는 보는 사람 기준(그림 왼쪽/오른쪽)입니다.

- `layers/NN_이름.png` : 기본 자세 레이어 45장. 번호가 작을수록 앞입니다. 쌓으면 v1과 같은 그림이 되고, 다른 곳은 다시 만든 맨팔·손뿐입니다(`v1_diff.png`).
- `rig.json`
  - `layers_front_to_back` : 그리는 순서와 레이어마다 붙는 뼈
  - `bones` : 뼈 16개(부모, 기준점, 기준점을 어떻게 정했는지 `from`)
    - **사람이 그은 선에서 나온 기준점:** 팔꿈치, 무릎, 트윈테일 중간·끝(선이 부위 안을 지나는 구간의 가운데)
    - **계산으로 추정한 기준점 (선을 긋지 않음):** 어깨·엉덩이(그 조각 윗부분 가운데에서 약 10px 아래), 머리(얼굴 아래 끝 가운데), 트윈테일 뿌리(윗부분 가운데). 몸(body)은 그림 가운데 엉덩이 높이로 손으로 정한 값이에요. 움직여 보고 어색하면 이 값부터 고치세요.
  - `slots` : 갈아 끼우는 부분(손, 표정, 트윈테일)
- `*_joint_line` 레이어 : 앞 조각과 같은 뼈에 붙지만, 그리는 순서는 뒤 조각 바로 뒤입니다. 곧게 두면 가려지고, 굽히면 바깥으로 나온 부분만 보입니다.
- `variants/expressions/<표정>/` : 표정 7종
  - 눈·눈썹·입을 통째로 바꿉니다. 그 세트에 없는 부분(감은 눈의 눈동자 등)은 숨깁니다.
  - blush(smile)와 sweat(surprised)는 얼굴 바로 앞에 그립니다.
- `variants/hands/{l,r}/` : 손 모양. 손목은 돌리지 않고 손만 갈아 끼웁니다.
  - l : default, fist, open, mic, peace, relax
  - r : default, fist, open, mic(주먹), peace, relax, point
- `variants/tails_whole/` : 안 자른 트윈테일입니다. 기본은 3조각(root/mid/tip, 위 조각이 앞)입니다.
- `effects/sweat_drop.png` : 공용 효과의 복사본입니다(원본은 저장소의 `effects/sweat_drop/`).
- `miku_v2.psd` : 기본 레이어 45장과 숨긴 `variants (hidden)` 그룹(표정·손·안 자른 트윈테일)
- `sheet.png` : 미리보기 시트(자세, 표정, 손, 트윈테일)
- 머리(head) 뼈는 작게만 기울이세요. 목 보강은 하지 않았습니다(사용자 결정).
- 치마·앞머리·몸통은 조각으로 나누지 않았습니다. 메시 변형 방식은 검토 중입니다.

다시 만들기: `env\Scripts\python.exe seethrough_test\rig\build_v2.py` 다음 `seethrough_test\rig\v2_sheet.py`
