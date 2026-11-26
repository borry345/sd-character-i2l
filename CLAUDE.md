# sd-character-i2l: Claude 작업 안내

캐릭터 그림 한 장을 **리깅할 수 있게 나눈 레이어**(PSD + PNG)로 만드는 도구 모음이에요.
리깅 자체(뼈, 메시, 애니메이션)는 범위 밖이에요. 뼈나 자세를 만들면 나눔 확인용 테스트로만 쓰고 그렇게 적으세요.

## 폴더
- `sources/` : 작업할 그림을 사용자가 넣는 곳. 이 안의 파일은 커밋하지 않아요.
- `result/` : 결과물을 저장하는 곳. 그림마다 `result/<그림 이름>/` 아래에 두세요. 커밋하지 않아요.
- `tools/` : 도구 (설명은 `docs/TOOLS.md`)
- `docs/WORKFLOW.md` : 단계별 작업 흐름. **작업 전에 꼭 읽으세요.** `docs/TROUBLESHOOTING.md`: 막혔을 때.
- `examples/miku/` : 끝까지 해 본 예시 (입력, 중간 결과, 최종 레이어)

## 실행 환경
- 도구는 `env/`(파이썬), `hf_cache/`(모델), `see-through/`(코드)가 필요해요.
  저장소 폴더에 없으면 환경 변수 `I2L_ROOT`가 그 셋이 있는 폴더를 가리켜야 해요.
  이 PC의 위치는 `CLAUDE.local.md`에 있어요(있을 때만). 없으면 사용자에게 묻거나 `docs/INSTALL.md`대로 설치하세요.
- 파이썬: `$I2L_ROOT\env\Scripts\python.exe` (venv) 또는 `env\python.exe` (conda)
- PowerShell에서 .ps1이 막히면: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
- GPU 한 장으로 돌려요. See-through 한 번에 몇 분 걸리니 백그라운드로 돌리세요.

## 시작 명령
```powershell
$env:I2L_ROOT = '<env·hf_cache·see-through가 있는 폴더>'
& tools\run_seethrough.ps1 -Src char.png -Extra @('--no_group_offload','--tblr_split','--seed','0')
```
- `-Src`에 파일 이름만 쓰면 `sources/`에서 찾고, `-OutDir`를 빼면 `result/<그림 이름>/`에 저장해요.
- 여러 seed를 돌릴 땐 seed마다 `-OutDir result\<이름>\seed<N>`처럼 나누세요.

## 일하는 방식
- **자동 파이프라인이 아니에요.** `docs/WORKFLOW.md`에서 ✋ 표시가 있는 단계는 사람이 골라요.
  - 예: seed 고르기, 자를 선 긋기(관절·손목·트윈테일), 앞뒤 순서, 표정·손 모양 고르기
  - 그 단계에서는 확인 이미지를 만들어 보여 주고, 사용자가 정할 때까지 멈추세요. 대신 정하지 마세요.
- 단계마다 **확인 이미지**를 만들어 결과를 보고 판단하세요. 이미지 안의 글자는 한국어로 쓰세요(PIL은 `C:/Windows/Fonts/malgun.ttf`).
- 사용자에게는 한국어로 답하세요.
- 중간 파일은 `result/<그림 이름>/` 아래에 단계별 폴더로 두세요. `sources/`의 원본은 고치지 마세요.

## 저장소 관리
- `sources/`, `result/`, `env/`, `hf_cache/`, `see-through/`는 커밋하지 않아요(.gitignore).
- 커밋·푸시는 사용자가 요청할 때만 하세요. 개인 경로나 이메일을 문서·코드에 넣지 마세요.
