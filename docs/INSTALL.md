# 설치

Windows + NVIDIA GPU 기준이에요. 이 문서대로 하면 저장소 폴더 안에 환경(`env/`), 모델(`hf_cache/`), See-through(`see-through/`)가 만들어지고, `tools/`의 스크립트가 그 위치를 자동으로 찾아요.

## 0. 준비물
- Windows 10/11, **NVIDIA GPU 8GB 이상**, CUDA 12.8을 지원하는 드라이버 (테스트한 PC는 [ENVIRONMENT.md](ENVIRONMENT.md))
- RAM 16GB 이상
- 디스크 약 25GB (환경 약 8.4GB + 모델 약 15GB)
- **Python 3.12** ([python.org](https://www.python.org/downloads/) 설치 프로그램, 테스트: 3.12.5), Git
  - conda를 써도 돼요 (2단계 참고)
- **영문 경로.** 한글이 들어간 경로에서는 CUDA·빌드 도구가 깨지기 쉬워요. 아래에서는 `D:\sd-character-i2l`을 예로 써요.

## 1. 저장소 받기
```powershell
git clone https://github.com/borry345/sd-character-i2l D:\sd-character-i2l
$ROOT = 'D:\sd-character-i2l'
```
> 도구는 기본적으로 **`tools` 폴더의 상위 폴더**를 기준으로 `env`, `hf_cache`, `see-through`를 찾아요.
> 다른 곳에 두고 싶으면 환경 변수 `I2L_ROOT`에 그 폴더를 넣으세요.

## 2. 파이썬 환경 (Python 3.12)
저장소 폴더 안의 `env`에 만들어요. 도구는 `env\Scripts\python.exe`(venv)와 `env\python.exe`(conda)를 모두 찾아요.

**venv (테스트한 방법)**
```powershell
py -3.12 -m venv "$ROOT\env"
$PY = "$ROOT\env\Scripts\python.exe"
& $PY -m pip install --upgrade pip
```

**conda를 쓴다면**
```powershell
$A = "$env:USERPROFILE\anaconda3"   # Miniconda면 miniconda3
# conda를 PATH 없이 실행하면 "SSL module is not available" 오류가 나요. 이 줄은 지금 창에만 적용돼요.
$env:PATH = "$A;$A\Library\mingw-w64\bin;$A\Library\usr\bin;$A\Library\bin;$A\Scripts;$env:PATH"
& "$A\Scripts\conda.exe" create -p "$ROOT\env" python=3.12 -y
$PY = "$ROOT\env\python.exe"
```

## 3. PyTorch (CUDA 12.8)
```powershell
& $PY -m pip install torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
& $PY -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
`True`와 GPU 이름이 나오면 돼요.

## 4. See-through (테스트한 커밋으로 고정)
```powershell
git clone https://github.com/mitmul/see-through "$ROOT\see-through"
cd "$ROOT\see-through"
git checkout e4cb250dc69defe6f982168dab684aa461552b5b
cmd /c mklink /J assets common\assets      # 리눅스의 ln -s 대신 junction
& $PY -m pip install -r requirements.txt -r requirements-inference-bnb.txt   # 반드시 see-through 폴더에서
cd $ROOT
```

## 5. SAM2 (`text_layers.py`용)
CUDA 확장을 빌드하지 않고, 설치한 torch를 건드리지 않게 넣어요.
```powershell
& $PY -m pip install "hydra-core>=1.3.2" "iopath>=0.1.10"
$env:SAM2_BUILD_CUDA = '0'
& $PY -m pip install --no-deps --no-build-isolation "git+https://github.com/facebookresearch/segment-anything-2@c2ec8e14a185632b0a5d8b161928ceb50197eddc"
```

## 6. 버전 확인
`requirements-lock.txt`가 테스트한 환경의 `pip freeze` 결과예요. 문제가 생기면 이 파일과 비교하세요.
```powershell
& $PY -m pip freeze > my_freeze.txt
```
핵심 버전: torch 2.8.0+cu128, bitsandbytes 0.49.2, diffusers 0.37.0, transformers 5.0.0, psd-tools 1.14.2.
lock 파일의 `-e git+...see-through...` 두 줄은 4단계에서 설치한 See-through의 `common`, `annotators` 폴더예요.
lock 파일로 바로 `pip install -r` 하기보다 2~5단계 순서를 따르는 걸 권해요 (torch 인덱스, SAM2 빌드 옵션 때문).

## 7. 모델
처음 실행할 때 Hugging Face에서 `$ROOT\hf_cache`로 자동으로 받아요 (`HF_HOME`, `TORCH_HOME`을 도구가 설정해요).

| 모델 | 크기 | 쓰는 곳 |
|---|---|---|
| `24yearsold/seethroughv0.0.2_layerdiff3d_nf4` | 3.6GB | See-through 레이어 생성 |
| `24yearsold/seethroughv0.0.1_marigold_nf4` | 1.8GB | See-through 깊이 |
| `frankjoshua/juggernautXL_version6Rundiffusion` | 설정 파일만 | See-through가 참조 |
| `diffusers/stable-diffusion-xl-1.0-inpainting-0.1` (fp16) | 6.5GB | `amodal_complete.py`, `mask_inpaint.py` |
| `IDEA-Research/grounding-dino-base` | 1.8GB | `text_layers.py` (글 → 상자) |
| `facebook/sam2.1-hiera-large` | 1.7GB | `text_layers.py` (상자 → 마스크) |
| `dreMaz/AnimeMangaInpainting` (`lama_large_512px.ckpt`) | 0.2GB | `text_layers.py` (틈 메우기), `hf_cache\torch`에 저장 |

크기는 테스트한 PC의 `hf_cache` 폴더 기준이에요. 라이선스는 [README](../README.md#모델과-라이선스)에 있어요.

**빠른 방법:** 다른 PC에 이미 받은 `hf_cache` 폴더가 있으면 통째로 복사해도 돼요. Windows에서는 HF 캐시가 심볼릭 링크 없이 실제 파일로 저장돼서 그대로 쓸 수 있어요.

SDXL 인페인팅만 미리 받으려면:
```powershell
$env:HF_HOME = "$ROOT\hf_cache"
& $PY -c "from huggingface_hub import snapshot_download as s; s('diffusers/stable-diffusion-xl-1.0-inpainting-0.1', allow_patterns=['model_index.json','*/config.json','scheduler/*','tokenizer*/*','*.fp16.safetensors'])"
```

## 8. 설치 확인
```powershell
# (1) 도구 자체 테스트 (GPU·모델 없이 PSD 읽기/쓰기 확인)
& $PY tools\selftest_psd_report.py $env:TEMP\i2l_selftest

# (2) See-through 한 장 (처음에는 모델을 받느라 오래 걸려요)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # 지금 창에서만 .ps1 실행 허용
& $ROOT\tools\run_seethrough.ps1 `
  -Src $ROOT\examples\miku\input\miku_chibi_sprite.png -OutDir $ROOT\outputs\test `
  -Extra @('--no_group_offload','--tblr_split','--seed','0') -HeadGrow 3
Get-Content $ROOT\outputs\test\summary.txt
```
- `summary.txt`에 `EXIT=0`이 있고 `outputs\test\miku_chibi_sprite.psd`가 생기면 성공이에요. `ARGS=` 뒤에 `--tblr_split --seed 0`까지 다 들어갔는지도 보세요.
- 경로는 상대 경로로 줘도 돼요. 스크립트가 `see-through` 폴더로 이동하기 전에 절대 경로로 바꿔요. 그림을 `sources/`에 넣었다면 `-Src`에 파일 이름만 쓰고, `-OutDir`를 빼면 `result\<그림 이름>`에 저장돼요.
- **`powershell -File tools\run_seethrough.ps1 -Extra @(...)` 형태로 부르지 마세요.** `-File`로 부르면 `-Extra` 배열의 첫 값만 전달돼서 `--tblr_split`, `--seed`가 조용히 빠져요. PowerShell 창에서 `&`로 부르세요.
- 실행 전에 GPU를 쓰는 다른 프로그램(게임 런처, 메신저, 데스크톱 캐릭터 앱 등)을 닫으세요. 이유는 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)에 있어요.

다음: [WORKFLOW.md](WORKFLOW.md)
