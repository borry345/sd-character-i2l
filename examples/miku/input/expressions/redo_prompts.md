# 표정 다시 만들기 프롬프트 (question, angry)

입력 그림: `miku_chibi_sprite.png` (원본 그대로 첨부). 결과는 원본과 같은 1312×1199로 받아 주세요.
처음 받은 question·angry는 캐릭터 전체를 다시 그려서(트윈테일 ±35px, angry는 약 10% 커짐) 파츠 위치가 안 맞았어요.

## 공통 (두 프롬프트 앞에 붙임)
```
Edit this exact image. Change ONLY the facial expression (eyes, eyebrows, mouth, and small marks on the face).
Do not redraw the character: keep the same size, position, pose, head angle, hair strands, twin tails,
headset, clothes, outline thickness, colours and white background exactly as they are, pixel for pixel.
Do not zoom, crop, shift or re-centre. Same canvas size as the input.
```

## question (물음표)
```
New expression: puzzled / curious. Eyes open and round, looking slightly up, small mouth (a little "o" or a flat
wavy line), one eyebrow slightly raised. Add a small black "?" mark floating just above the right side of the head,
outside the hair, not covering the face or hair.
```

## angry (화남)
```
New expression: cute chibi anger. Eyes squeezed shut as "> <" or sharp angry eyes, eyebrows angled down toward
the centre, mouth open wide shouting with a small fang. Light red blush on the cheeks. Add a small red anger mark
(cross-shaped vein symbol) on the right side of the head over the hair, small, not covering the eyes.
```

## 확인
- 받은 그림을 `miku_chibi_question.png`, `miku_chibi_angry.png`로 덮어쓰면 다시 검사해요(원본과 겹침 IoU ≥ 0.9 목표, 기존 7장은 0.93~0.94).
- 머리 밖 표시(?, 분노 마크)는 See-through가 headwear나 hair에 섞을 수 있어요. 나오면 따로 떼는 걸 그때 정해요.
