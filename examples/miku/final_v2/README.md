# miku_v2 (리깅용으로 나눈 레이어, 1024 캔버스)

[v1(레이어 PSD, 21레이어)](../final_v1/README.md)을 관절·손목·트윈테일·눈 좌우에서 더 자르고, 바꿔 끼우는 파츠(손·표정)를 더한 버전이에요. v1과 v2의 차이와 각각 필요한 이유는 저장소 README의 "결과물 두 가지"에 정리했어요.

이 폴더의 결과물은 **리깅할 수 있게 나눈 레이어**예요. 실제 리깅(뼈 구조, 기준점, 움직임)은 이 프로젝트의 범위가 아니에요.
`rig.json`의 뼈와 `sheet.png`의 자세는 나눈 조각이 굽혀도 틈 없이 이어지는지 **확인하려고 임시로 만든 테스트용**이에요.
실제 리깅 도구(Spine, Live2D, Godot 등)에서는 뼈와 기준점을 새로 잡으세요.

옆모습(왼쪽 보기) 하나만 써요(사용자 결정). 오른쪽 보기는 전체를 좌우 반전해요. 이름의 l/r, left/right는 보는 사람 기준(그림 왼쪽/오른쪽)이에요.

## 결과물: 나눈 레이어
- `layers/NN_이름.png` : 기본 자세 레이어 45장. 번호가 작을수록 앞이에요. 쌓으면 v1과 같은 그림이 되고, 다른 곳은 다시 만든 맨팔·손뿐이에요(`v1_diff.png`).
  - 팔: 소매 아래·위, 맨팔 하박·상박, 손. 팔꿈치는 하박이 앞이에요.
  - 다리: 허벅지, 종아리. 무릎은 종아리가 앞이에요.
  - 트윈테일: 뿌리·중간·끝. 위 조각이 앞이에요(사용자 결정).
  - 눈 4종: 왼쪽/오른쪽으로 나눔
- `*_joint_line` 레이어 : 관절 외곽선이에요. 앞 조각과 같이 움직이지만, 그리는 순서는 뒤 조각 바로 뒤예요. 곧게 두면 가려지고, 굽히면 바깥으로 나온 부분만 보여요.
- 자른 위치: 무릎·팔꿈치·손목·트윈테일은 **사람이 그은 선**으로 잘랐어요. 선 파일은 `examples/miku/rig/`에 있어요.
- 나누지 않은 것: 치마, 앞머리·옆머리, 몸통·넥타이(사용자 결정: 팔다리면 충분). 목 보강도 하지 않았어요(사용자 결정).

## 바꿔 끼우는 파츠 (`variants/`)
- `expressions/<표정>/` : 표정 11종(calm, smile, ah, ee, oh, surprised, sleeping, pet, crying, question, angry)
  - 눈·눈썹·입을 통째로 바꿔요. 그 세트에 없는 부분(감은 눈의 눈동자 등)은 숨겨요.
  - 덧붙는 표시는 이렇게 그려요(`rig.json`의 `extras_place`).
    - blush(smile, pet, crying, question, angry), sweat(surprised), tears(crying): 얼굴 바로 앞
    - anger(angry 분노 마크): 맨 앞(앞머리 위). See-through가 빠뜨려서 입력 그림에서 직접 잘랐어요.
  - **안 쓰는 파츠(사용자 결정)**
    - 해당 파츠: 눈·눈썹(ah, ee, oh, sleeping, pet), 입(pet)
    - 이 파일들은 넣지 않았어요. 그 표정 세트는 다른 표정의 파츠를 빌려 써요(`rig.json`의 `borrowed`).
    - 빌려 쓰는 곳: ah·ee·oh → 기본 레이어, sleeping → calm, pet 눈·눈썹 → surprised(같은 `><`), pet 입 → ah
  - 얼굴만 빠르게 바꿔 보는 확인 페이지는 작업 폴더의 `seethrough_test/rig/face_viewer/index.html`에 있어요.
- `hands/{l,r}/` : 손 모양. 손목은 돌리지 않고 손만 갈아 끼워요(사용자 결정). 모두 같은 손목 선에서 잘랐어요.
  - l : default, fist, open, mic, peace, relax
  - r : default, fist, open, mic(마이크 없는 주먹), peace, relax, point
- `tails_whole/` : 안 자른 트윈테일이에요. 3조각 대신 써요.
- `effects/sweat_drop.png` : 공용 효과의 복사본이에요(원본은 저장소의 `effects/sweat_drop/`).

## 파일
- `miku_v2.stretch` : Stretchy Studio 프로젝트 파일. 관절 8개(rig.json 테스트 뼈 위치)를 넣고 팔다리를 Remesh해 둬서, 편집기에 끌어다 놓으면 관절 호를 마우스로 끌어 바로 굽힐 수 있어요.
- `miku_v2_stretchy.psd` : [Stretchy Studio](https://github.com/MangoLion/stretchystudio)용 PSD (`seethrough_test/rig/export_stretchy.py`)
  - 레이어를 그림 범위로 잘라 저장했어요. 원래 PSD는 레이어가 모두 1024 전체 크기라, Stretchy가 범위로 뼈를 추정하면 엉뚱해져요.
  - 이름을 See-through 태그로 바꿨어요(`front hair`, `back hair`, `handwear-l` …). Stretchy는 정확히 `handwear-l`인 레이어만 왼팔 뼈에 붙여서, 팔·다리 조각은 모두 같은 이름(`handwear-l/r`, `legwear-l/r`)이에요.
  - **좌우는 캐릭터 기준**이에요(우리 `_l` = 그림 왼쪽 → `-r`). Stretchy의 뼈대가 캐릭터 본인의 왼쪽에 `leftArm`을 두기 때문이에요.
  - 바꿔 끼우는 파츠는 넣지 않았어요(숨긴 레이어도 모두 가져와서 리깅해 버려요). 이름 대응표는 같은 이름의 `.json`이에요.
  - 가져오기 마법사에서는 DWPose(AI 자세 인식)를 고르세요. 범위 추정 방식은 손목·발목을 잘못 잡아요(작업 폴더 `seethrough_test/rig/stretchy_check.png`).
- `miku_v2.psd` : 기본 레이어 45장과 숨긴 `variants (hidden)` 그룹(표정 11종·손·안 자른 트윈테일, 빌려 쓰는 파츠는 원래 자리에만 있어요)
- `rig.json`
  - `layers_front_to_back` : 그리는 순서(**결과물**)
  - `slots` : 바꿔 끼우는 파츠 목록(**결과물**)
  - `bones` : **확인용 테스트 뼈** 16개(부모, 기준점, 기준점을 어떻게 정했는지 `from`)
    - 사람이 그은 선에서 나온 기준점: 팔꿈치, 무릎, 트윈테일 중간·끝
    - 계산으로 추정한 기준점: 어깨·엉덩이(그 조각 윗부분 가운데에서 약 10px 아래), 머리(얼굴 아래 끝 가운데), 트윈테일 뿌리
    - 몸(body)은 그림 가운데 엉덩이 높이로 손으로 정한 값이에요.
- `sheet.png` : 확인 시트. 테스트 뼈로 움직인 자세, 표정, 손, 트윈테일이 들어 있어요.

다시 만들기: `env\Scripts\python.exe seethrough_test\rig\build_v2.py` 다음 `seethrough_test\rig\v2_sheet.py` (작업 폴더 경로 기준)
