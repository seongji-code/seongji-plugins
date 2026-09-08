# -*- coding: utf-8 -*-
"""[템플릿] 화면별 렌더 스크립트 — 작업 폴더에 복사해서 좌표를 채워 쓴다.

  cp render_template.py <작업폴더>/_작업/render.py
  cd <작업폴더>/_작업 && python3 render.py

여기 있는 좌표는 전부 **원본 화면 이미지에서 measure.py 로 잰 값**으로 바꿔야 한다.
지금 들어있는 숫자는 1179x2556 도라에몽 화면의 실제 값이라, 구조를 읽는 예시로만 쓴다.

좌표 규칙
  - 왼쪽 정렬 글자: x = 잉크 왼쪽 끝, cy = 잉크 세로중심
  - 가운데 정렬 글자: x = 가로중심, cy = 잉크 세로중심
  - 잉크높이(TARGETS) = measure.py 가 찍어 준 박스 높이
"""
import os, sys, glob


def skill_scripts():
    """이 스킬의 scripts 폴더를 찾는다.

    render.py 는 작업 폴더에서 돌기 때문에 textkit 을 스스로 찾아야 하는데,
    설치 위치가 사람마다 다르다(개인 스킬 / 플러그인 / 프로젝트).
    스킬을 실행하는 에이전트는 스킬 폴더 경로를 알고 있으니 그냥 절대경로를 적어도 된다.
    이 블록은 그대로 복사해 쓰라고 남겨 둔 것이다.
    """
    H = os.path.expanduser('~')
    c = [os.environ.get('CREATE_WALLPAPER_SCRIPTS'),
         H + '/.claude/skills/create-wallpaper/scripts']
    c += sorted(glob.glob(H + '/.claude/plugins/cache/*/create-wallpaper/*/skills/create-wallpaper/scripts'))
    c += sorted(glob.glob(H + '/.claude/plugins/marketplaces/*/plugins/create-wallpaper/skills/create-wallpaper/scripts'))
    d = os.getcwd()
    while True:
        c.append(os.path.join(d, '.claude/skills/create-wallpaper/scripts'))
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    for x in c:
        if x and os.path.isfile(os.path.join(x, 'textkit.py')):
            return x
    sys.exit('create-wallpaper 의 scripts 폴더를 못 찾았다. '
             '환경변수로 알려 주면 된다:  export CREATE_WALLPAPER_SCRIPTS=<경로>')


sys.path.insert(0, skill_scripts())
from PIL import Image
import textkit as tk
from content import LOCALES

# ── 원본에서 잰 값 ─────────────────────────────────────────────────────────
# 스타일: 이름 -> (잉크높이, 'bold'|'reg')
TARGETS = dict(weekday=(25, 'reg'), title=(40, 'bold'),
               sub=(29, 'reg'), chip=(22, 'bold'))
DATE_INK, DATE_CX, DATE_CY, DATE_MAXW = 58, 588, 266.5, 880   # 시계 위 날짜 줄

# 폭이 고정된 자리(칩 등)의 언어별 글자크기 보정.
# 목표: 가장 긴 글자가 칸 폭의 80~88%. 다 만든 뒤 그림을 보고 조정한다.
BOOSTS = dict(chip={"ko": 1.18, "ms": 1.05, "en-US": 1.05, "en-GB": 1.05, "fr": 1.05})

COL = dict(date=(62, 60, 58), weekday=(104, 97, 94), title=(24, 20, 17),
           red=(214, 97, 89), gray=(100, 93, 88), header=(124, 117, 112),
           chiptext=(253, 252, 251))

COLX = [128, 281, 435, 588, 742, 895, 1049]     # 요일 7열 가로중심
WEEKDAY_CY = 732
CHIP_W, CHIP_H, CHIP_R = 143, 41, 8
CHIP_Y = [822, 864]                              # 칩 사각형 위쪽 y (1행, 2행)
CHIP_TEXT_CY = [844.5, 886.5]                    # 칩 글자 잉크 세로중심
CHIP_SLOT = [(1, 0), (1, 1), (2, 0), (3, 0), (4, 0), (5, 0), (5, 1), (6, 0)]  # (열, 행)
CHIP_FILL = {(1, 0): (226, 164, 160), (1, 1): (206, 180, 206), (2, 0): (185, 204, 222),
             (3, 0): (209, 183, 209), (4, 0): (228, 167, 162), (5, 0): (226, 131, 178),
             (5, 1): (188, 206, 227), (6, 0): (224, 164, 159)}

TITLE_X, HEAD_X = 134, 101                       # 제목 / 섹션라벨 잉크 왼쪽 끝
OVERDUE = [(1113.5, 1160), (1218.5, 1265), (1323.5, 1369.5)]      # (제목cy, 부제cy)
SECTIONS = [(1465, 1512.5), (1618, 1665.5), (1771, 1818.5), (1924, 1971.5)]  # (라벨cy, 제목cy)
TITLE_MAXW = 660          # 그림에 가리지 않는 위쪽
TITLE_MAXW_LOW = 545      # 캐릭터에 가리는 아래쪽
SUB_MAXW = 575


def render(loc, plate, outpath):
    d8 = LOCALES[loc]
    ctx = tk.Ctx(loc, TARGETS, BOOSTS, date_ink=DATE_INK, date_cy=DATE_CY)
    layer, d = tk.new_layer(plate)

    # 날짜 줄 (iOS 시스템 폰트)
    tk.draw_date(d, ctx, d8['date'], DATE_CX, COL['date'], DATE_MAXW)

    # 요일 헤더
    for cx, w in zip(COLX, d8['wd']):
        tk.draw_text(d, ctx, 'weekday', cx, WEEKDAY_CY, w, COL['weekday'], align='c')

    # 일정 칩 — 한 화면 안에서 크기를 하나로 통일
    chipf = tk.uniform(ctx, 'chip', [(c, CHIP_W - 16) for c in d8['chips']], d)
    for (ci, ri), txt in zip(CHIP_SLOT, d8['chips']):
        x0, y0 = COLX[ci] - CHIP_W // 2, CHIP_Y[ri]
        d.rounded_rectangle([x0 * tk.S, y0 * tk.S, (x0 + CHIP_W) * tk.S, (y0 + CHIP_H) * tk.S],
                            radius=CHIP_R * tk.S, fill=CHIP_FILL[(ci, ri)])
        tk.draw_text(d, ctx, 'chip', COLX[ci], CHIP_TEXT_CY[ri], txt,
                     COL['chiptext'], align='c', force=chipf)

    # 할일 제목도 하나의 크기로 통일
    tw = [(t, TITLE_MAXW) for t, _ in d8['overdue']]
    tw += [(t, TITLE_MAXW if tc < 1700 else TITLE_MAXW_LOW)
           for (_, tc), (_, t) in zip(SECTIONS, d8['sections'])]
    titlef = tk.uniform(ctx, 'title', tw, d)

    for (tc, sc), (title, sub) in zip(OVERDUE, d8['overdue']):
        tk.draw_text(d, ctx, 'title', TITLE_X, tc, title, COL['title'],
                     force=titlef, stroke=ctx.stroke)
        col = COL['red'] if ('·' in sub) else COL['gray']
        tk.draw_text(d, ctx, 'sub', TITLE_X, sc, sub, col, maxw=SUB_MAXW)

    for (hc, tc), (head, title) in zip(SECTIONS, d8['sections']):
        tk.draw_text(d, ctx, 'sub', HEAD_X, hc, head, COL['header'], maxw=500)
        tk.draw_text(d, ctx, 'title', TITLE_X, tc, title, COL['title'],
                     force=titlef, stroke=ctx.stroke)

    return tk.flatten(plate, layer, outpath)


if __name__ == '__main__':
    plate = Image.open('plate.png').convert('RGB')
    outdir = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(outdir, exist_ok=True)
    for loc in (sys.argv[2:] or tk.LANGS):
        p = os.path.join(outdir, f'화면_{loc}.png')
        render(loc, plate, p)
        print('->', p)
