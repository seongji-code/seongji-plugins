# -*- coding: utf-8 -*-
"""화면 이미지에서 '글자 덩어리'와 '색 블록'의 좌표를 재 준다.

눈대중으로 좌표를 찍으면 반드시 틀린다. 이 도구가 잉크 박스를 잡아 주고,
번호를 얹은 확인 이미지를 만들어 준다. 그 이미지를 **직접 보고** 번호를 의미에
연결한 뒤 render.py 상수로 옮긴다.

사용법
  python3 measure.py 화면.png                    # 글자 줄 + 색 블록 측정
  python3 measure.py 화면.png --band 0 800       # y 구간만
  python3 measure.py 화면.png --gap 26           # 줄 병합 간격(기본 자동)
출력
  화면_측정.png   번호가 붙은 확인 이미지 (반드시 눈으로 볼 것)
  화면_측정.json  박스 목록
"""
import argparse, json, os, sys
import cv2
import numpy as np


def ink_mask(img):
    """배경(밝은 판)에서 글자만 남긴다. 국소 배경과의 차이로 뽑는다."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    bg = cv2.medianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 51).astype(np.float32)
    diff = bg - g                       # 배경보다 어두운 곳 = 글자
    m = (diff > 18).astype(np.uint8) * 255
    # 밝은 글자(색 칩 위 흰 글씨)도 잡는다
    m2 = ((g - bg) > 28).astype(np.uint8) * 255
    return m, m2


def boxes_from(mask, gap, minw, minh, vgap=7):
    """가로로 gap 이내면 한 줄로 묶어 글자 줄 박스를 만든다.

    한글·CJK 글자는 획이 떨어져 있어(예: '수' = ㅅ + ㅜ) 세로로도 조금 묶어야
    한 글자로 잡힌다. vgap 이 너무 크면 위아래 줄이 붙으므로 줄 간격보다 작게.
    """
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(2, gap), max(3, vgap)))
    j = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(j, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if w < minw or h < minh or a < 40:
            continue
        sub = mask[y:y+h, x:x+w]        # 실제 잉크만으로 박스를 다시 조인다
        ys, xs = np.nonzero(sub)
        if len(xs) == 0:
            continue
        out.append([int(x+xs.min()), int(y+ys.min()), int(x+xs.max()+1), int(y+ys.max()+1)])
    out.sort(key=lambda b: (b[1], b[0]))
    return out


def color_blocks(img, minarea=1500):
    """채도 높은 덩어리(일정 칩 등)의 위치와 평균 색."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 90)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < minarea:
            continue
        px = img[y:y+h, x:x+w][lab[y:y+h, x:x+w] == i]
        b, g, r = np.median(px, axis=0)
        out.append(dict(box=[int(x), int(y), int(x+w), int(y+h)],
                        rgb=[int(r), int(g), int(b)]))
    out.sort(key=lambda c: (c['box'][1], c['box'][0]))
    return out


def report(name, bs):
    print(f"\n[{name}]")
    print("  #   x0    y0    x1    y1    폭 x 높이    가로중심  세로중심  (높이=잉크높이)")
    for i, b in enumerate(bs):
        x0, y0, x1, y1 = b
        print(f" {i:3d} {x0:5d} {y0:5d} {x1:5d} {y1:5d}   {x1-x0:4d} x {y1-y0:3d}"
              f"    {(x0+x1)/2:7.1f}  {(y0+y1)/2:7.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--band', nargs=2, type=int, help='y0 y1 구간만 본다')
    ap.add_argument('--gap', type=int, default=0, help='한 줄로 묶을 가로 간격 (0=자동)')
    ap.add_argument('--vgap', type=int, default=7, help='한 글자로 묶을 세로 간격 (줄이 붙으면 낮춘다)')
    ap.add_argument('--minw', type=int, default=12)
    ap.add_argument('--minh', type=int, default=10)
    a = ap.parse_args()

    img = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"못 읽음: {a.src}")
    H, W = img.shape[:2]
    print(f"화면 크기: {W} x {H}")
    y0, y1 = (a.band if a.band else (0, H))
    crop = img[y0:y1]
    gap = a.gap or max(14, W // 45)

    dark, light = ink_mask(crop)
    bd = boxes_from(dark, gap, a.minw, a.minh, a.vgap)
    bl = boxes_from(light, gap, a.minw, a.minh, a.vgap)
    for b in bd + bl:
        b[1] += y0; b[3] += y0
    cb = color_blocks(crop)
    for c in cb:
        c['box'][1] += y0; c['box'][3] += y0

    report('어두운 글자', bd)
    if bl:
        report('밝은 글자 (색 위 흰 글씨)', bl)
    if cb:
        print("\n[색 블록]  (칩·버튼 등)")
        print("  #   x0    y0    x1    y1    폭 x 높이   RGB")
        for i, c in enumerate(cb):
            x0_, y0_, x1_, y1_ = c['box']
            print(f" {i:3d} {x0_:5d} {y0_:5d} {x1_:5d} {y1_:5d}   {x1_-x0_:4d} x {y1_-y0_:3d}"
                  f"   {tuple(c['rgb'])}")

    v = img.copy()
    for c in cb:
        x0_, y0_, x1_, y1_ = c['box']
        cv2.rectangle(v, (x0_, y0_), (x1_, y1_), (255, 160, 0), 2)
    for i, (bx0, by0, bx1, by1) in enumerate(bd):
        cv2.rectangle(v, (bx0, by0), (bx1, by1), (0, 0, 255), 2)
        cv2.putText(v, str(i), (bx0, max(14, by0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 255), 1)
    for i, (bx0, by0, bx1, by1) in enumerate(bl):
        cv2.rectangle(v, (bx0, by0), (bx1, by1), (0, 190, 0), 2)
        cv2.putText(v, f"L{i}", (bx0, max(14, by0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 150, 0), 1)
    base = os.path.splitext(a.src)[0]
    cv2.imwrite(base + '_측정.png', v)
    json.dump(dict(size=[W, H], dark=bd, light=bl, color=cb),
              open(base + '_측정.json', 'w'), ensure_ascii=False, indent=1)
    print(f"\n확인 이미지: {base}_측정.png   ← 반드시 눈으로 볼 것")
    print(f"좌표 파일:   {base}_측정.json")


if __name__ == '__main__':
    main()
