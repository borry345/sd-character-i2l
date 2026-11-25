# 트윈테일 (v1 레이어 기준, 1024 캔버스)

- whole/   : 안 자른 버전. tail_left.png = v1 14_tail_left, tail_right.png = v1 18_tail_right (원본 그대로)
- split3/  : 3조각 버전 (뿌리 root / 중간 mid / 끝 tip, 위 조각이 앞). tools/split_chain.py, --overlap 14 --feather 8
  - split3/{left,right}/tail_*_{root,mid,tip}.png, chain.json(관절 기준점·순서), chain_check.png
  - split3/tails_check.png (곧게·±10°·±20°씩), split3/seam_hard_vs_feather.png
- lines/   : 사용자가 그은 자르는 선 (lined_tail_left/right.png)
