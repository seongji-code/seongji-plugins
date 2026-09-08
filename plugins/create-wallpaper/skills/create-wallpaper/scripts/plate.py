# -*- coding: utf-8 -*-
"""원본 화면에서 글자만 지워 '빈 배경 판(plate)'을 만든다.

배경 그림·캐릭터·상태바 아이콘은 그대로 두고 글자 자리만 인페인트로 메운다.
그 위에 언어별 글자를 새로 얹는 것이 이 작업의 기본 구조다.

사용법
  python3 plate.py 화면.png --rects rects.json --out plate.png
  python3 plate.py 화면.png --rects "124,1080,706,1142; 98,701,1088,760" --out plate.png
  (rects = 지울 사각형 x0,y0,x1,y1 목록. 여백을 글자보다 조금 넉넉히 잡을 것)

주의
  - 불릿·체크 동그라미처럼 **남겨야 하는 것**은 사각형 밖으로 뺀다.
    (도라에몽 건에서는 불릿이 x=99~119 라 지움 영역을 x=124 부터 시작했다)
  - 결과 plate 를 반드시 눈으로 본다. 글자 잔상이 남거나, 배경 무늬가 뭉개졌으면
    사각형을 조정하고 다시 만든다.
"""
import argparse, json, os, sys
import cv2
import numpy as np


def parse_rects(s):
    if os.path.exists(s):
        return json.load(open(s))
    out = []
    for chunk in s.split(';'):
        chunk = chunk.strip()
        if chunk:
            out.append([int(round(float(v))) for v in chunk.split(',')])
    return out


def make_plate(img, rects, radius=9, smooth=9):
    H, W = img.shape[:2]
    mask = np.zeros((H, W), np.uint8)
    for x0, y0, x1, y1 in rects:
        mask[max(0, y0):min(H, y1), max(0, x0):min(W, x1)] = 255
    out = cv2.inpaint(img, mask, radius, cv2.INPAINT_TELEA)
    # 2차: 인페인트가 남기는 줄무늬를 부드럽게 눌러 준다
    blur = cv2.GaussianBlur(out, (0, 0), smooth)
    m3 = cv2.GaussianBlur((mask > 0).astype(np.float32), (0, 0), smooth * 2 / 3)[..., None]
    return (out * (1 - m3) + blur * m3).astype(np.uint8), mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--rects', required=True, help='JSON 파일 경로 또는 "x0,y0,x1,y1; ..."')
    ap.add_argument('--out', default='plate.png')
    ap.add_argument('--radius', type=int, default=9)
    ap.add_argument('--smooth', type=float, default=9)
    a = ap.parse_args()

    img = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"못 읽음: {a.src}")
    rects = parse_rects(a.rects)
    plate, mask = make_plate(img, rects, a.radius, a.smooth)
    cv2.imwrite(a.out, plate)

    v = plate.copy()
    v[mask > 0] = (0.75 * v[mask > 0] + 0.25 * np.array([0, 0, 255])).astype(np.uint8)
    chk = os.path.splitext(a.out)[0] + '_지운영역.png'
    cv2.imwrite(chk, v)
    print(f"plate: {a.out}   (사각형 {len(rects)}개)")
    print(f"확인용: {chk}   ← 빨간 곳이 지운 영역. 눈으로 볼 것")


if __name__ == '__main__':
    main()
