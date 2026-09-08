# -*- coding: utf-8 -*-
"""잠금화면 이미지를 '폰 든 사진' 속 화면에 원근 합성한다.

사진마다 화면 네 귀퉁이를 한 번만 잡아 두면(<사진>.quad.json), 8개 언어를
같은 자리에 자동으로 찍어낸다.

사용법
  1) 귀퉁이 잡기 — 셋 중 하나
     python3 mockup.py --photo 사진.png --detect     # 자동 검출 시도 + 미리보기
     python3 mockup.py --photo 사진.png --grid       # 좌표격자 이미지 → 눈으로 읽어서
     python3 mockup.py --photo 사진.png --quad x1,y1,x2,y2,x3,y3,x4,y4   # 직접 지정
     (순서는 좌상 → 우상 → 우하 → 좌하)
  2) 합성
     python3 mockup.py --photo 사진.png --all        # 8개 언어 전부
     python3 mockup.py --photo 사진.png --lang ko    # 하나만
"""
import argparse, json, os, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, '..'))
LANGS = ["ko", "ja", "zh-TW", "ms", "en-US", "en-GB", "fr", "vi"]

# 아이폰 화면 규격 — 1179x2556(15/16 Pro) 에서 실측한 값.
# 화면 이미지 크기가 다르면 폭 비율로 환산해서 쓴다.
REF_W = 1179
CORNER_R = 175                      # 화면 모서리 반경 (역워프 후 원 피팅 실측)
ISLAND_W, ISLAND_H = 383, 104       # 다이나믹 아일랜드 (스크린샷에는 없다)
ISLAND_TOP = 35                     # 화면 위끝에서 아일랜드까지


def screen_size(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    if im is None:
        sys.exit(f"화면 이미지를 못 읽음: {path}")
    return im.shape[1], im.shape[0]


# ── 귀퉁이 좌표 ──────────────────────────────────────────────────────────────
def quad_path(photo):
    return os.path.splitext(photo)[0] + '.quad.json'


def order_quad(pts):
    """네 점을 좌상 → 우상 → 우하 → 좌하 순서로 정렬."""
    pts = np.array(pts, dtype=np.float32).reshape(4, 2)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def _line_through(pts):
    """점들에 직선을 피팅해 (a, b, c) 형태(ax+by+c=0)로 돌려준다."""
    vx, vy, x0, y0 = cv2.fitLine(pts.astype(np.float32), cv2.DIST_L2, 0, .01, .01).ravel()
    return float(vy), float(-vx), float(vx * y0 - vy * x0)


def _intersect(l1, l2):
    a1, b1, c1 = l1; a2, b2, c2 = l2
    d = a1 * b2 - a2 * b1
    if abs(d) < 1e-9:
        return None
    return np.array([(b1 * c2 - b2 * c1) / d, (c1 * a2 - c2 * a1) / d], np.float32)


def refine_quad(contour, quad, trim=0.18, tol=18.0):
    """둥근 모서리 때문에 안쪽으로 깎인 꼭짓점을, 네 변의 직선 교점으로 되돌린다.

    각 변에서 모서리 쪽 trim 비율을 잘라내고(둥근 부분 제외) 남은 점들로 직선을
    피팅한 뒤, 이웃한 두 직선의 교점을 진짜 꼭짓점으로 삼는다.
    """
    pts = contour.reshape(-1, 2).astype(np.float32)
    lines = []
    for i in range(4):
        p, q = quad[i], quad[(i + 1) % 4]
        d = q - p
        L = np.linalg.norm(d)
        if L < 1:
            return quad
        u = d / L
        n = np.array([-u[1], u[0]], np.float32)
        t = (pts - p) @ u                      # 변 방향 위치
        dist = np.abs((pts - p) @ n)           # 변에서 떨어진 거리
        sel = (t > L * trim) & (t < L * (1 - trim)) & (dist < tol)
        if sel.sum() < 20:
            return quad
        lines.append(_line_through(pts[sel]))
    out = []
    for i in range(4):
        x = _intersect(lines[(i - 1) % 4], lines[i])
        if x is None:
            return quad
        out.append(x)
    return np.array(out, np.float32)


def enclosed(mask):
    """mask(흰색)에 둘러싸여 바깥과 이어지지 않는 영역을 돌려준다.

    사진 모서리가 어두우면 (0,0)에서 시작한 플러드필이 먹히지 않으므로,
    1px 테두리를 덧대고 그 바깥에서 채운다.
    """
    pad = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    ff = pad.copy()
    cv2.floodFill(ff, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 255)
    return cv2.bitwise_not(ff)[1:-1, 1:-1]


def detect_quad(img):
    """검은 베젤에 둘러싸인 화면 사각형을 찾는다. 실패하면 None."""
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = ((g < 70).astype(np.uint8)) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(dark, 8)
    if n < 2:
        return None
    # 그림자·소품도 어두우므로, '가장 큰 덩어리'가 아니라
    # '가장 큰 구멍(=화면)을 감싸는 덩어리'를 베젤로 고른다.
    order = np.argsort(st[1:, 4])[::-1][:6] + 1
    bezel, best_hole = None, 0
    for i in order:
        cand = (lab == i).astype(np.uint8) * 255
        hole = enclosed(cand)
        a = int((hole > 0).sum())
        if a > best_hole:
            bezel, best_hole = cand, a
    if bezel is None or best_hole < img.shape[0] * img.shape[1] * 0.02:
        return None

    holes = enclosed(bezel)                            # 베젤에 둘러싸인 영역 = 화면
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(holes, 8)
    if n2 < 2:
        return None
    screen = (lab2 == 1 + int(np.argmax(st2[1:, 4]))).astype(np.uint8) * 255
    screen = cv2.morphologyEx(screen, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))

    cnts, _ = cv2.findContours(screen, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    for eps in (0.02, 0.03, 0.015, 0.04):
        ap = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
        if len(ap) == 4:
            q = order_quad(ap.reshape(4, 2))
            return order_quad(refine_quad(c, q))
    return None


def match_quad(src_path, photo_path):
    """합성에 쓰인 원본 화면 이미지를 특징점 매칭해 화면 사각형을 구한다.

    자동 검출(detect_quad)보다 훨씬 정확하다. 원본을 알고 있으면 이쪽을 쓸 것.
    돌려주는 값: (inlier 개수, 네 귀퉁이) — inlier가 40 미만이면 신뢰하지 말 것.
    """
    src = cv2.imread(src_path, cv2.IMREAD_GRAYSCALE)
    dst = cv2.imread(photo_path, cv2.IMREAD_GRAYSCALE)
    if src is None or dst is None:
        return 0, None
    sh, sw = src.shape
    sc = 900.0 / sh                                   # 크기 차이를 줄여 매칭률을 높인다
    s = cv2.resize(src, (int(sw * sc), 900), interpolation=cv2.INTER_AREA)
    sift = cv2.SIFT_create(nfeatures=8000)
    k1, d1 = sift.detectAndCompute(s, None)
    k2, d2 = sift.detectAndCompute(dst, None)
    if d1 is None or d2 is None:
        return 0, None
    good = [a for a, b in cv2.BFMatcher().knnMatch(d1, d2, k=2) if a.distance < 0.75 * b.distance]
    if len(good) < 12:
        return 0, None
    p1 = np.float32([k1[g.queryIdx].pt for g in good]).reshape(-1, 1, 2)
    p2 = np.float32([k2[g.trainIdx].pt for g in good]).reshape(-1, 1, 2)
    Hm, mask = cv2.findHomography(p1, p2, cv2.RANSAC, 3.0)
    if Hm is None:
        return 0, None
    S = np.array([[sc, 0, 0], [0, sc, 0], [0, 0, 1]], np.float64)
    corners = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]]).reshape(-1, 1, 2)
    q = cv2.perspectiveTransform(corners, Hm @ S).reshape(4, 2)
    return int(mask.sum()), order_quad(q)


def write_grid(photo, img):
    """좌표를 눈으로 읽을 수 있게 격자를 얹은 이미지를 만든다."""
    v = img.copy()
    H, W = v.shape[:2]
    step = max(50, int(round(max(W, H) / 40 / 50) * 50))
    for x in range(0, W, step):
        thick = 2 if x % (step * 5) == 0 else 1
        cv2.line(v, (x, 0), (x, H), (0, 200, 255), thick)
        if x % (step * 5) == 0:
            cv2.putText(v, str(x), (x + 4, 26), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 255), 2)
    for y in range(0, H, step):
        thick = 2 if y % (step * 5) == 0 else 1
        cv2.line(v, (0, y), (W, y), (0, 200, 255), thick)
        if y % (step * 5) == 0:
            cv2.putText(v, str(y), (6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 255), 2)
    p = os.path.splitext(photo)[0] + '_grid.png'
    cv2.imwrite(p, v)
    return p, step


# ── 합성 ────────────────────────────────────────────────────────────────────
def rounded_mask(w, h, r, ss=4):
    """화면 좌표계에서 둥근 사각형 마스크 (계단 없애려고 4배로 그린 뒤 축소)."""
    m = np.zeros((h * ss, w * ss), np.uint8)
    cv2.rectangle(m, (r*ss, 0), (w*ss - r*ss, h*ss), 255, -1)
    cv2.rectangle(m, (0, r*ss), (w*ss, h*ss - r*ss), 255, -1)
    for cx, cy in [(r, r), (w-r, r), (w-r, h-r), (r, h-r)]:
        cv2.circle(m, (cx*ss, cy*ss), r*ss, 255, -1)
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_AREA)


def add_island(screen):
    """스크린샷에는 없는 다이나믹 아일랜드를 얹는다."""
    out = screen.copy()
    H, W = screen.shape[:2]
    k = W / float(REF_W)
    iw, ih, itop = int(round(ISLAND_W*k)), int(round(ISLAND_H*k)), int(round(ISLAND_TOP*k))
    x0 = (W - iw) // 2
    box = (x0, itop, x0 + iw, itop + ih)
    r = ih // 2
    pill = np.zeros((H, W), np.uint8)
    cv2.rectangle(pill, (box[0]+r, box[1]), (box[2]-r, box[3]), 255, -1)
    cv2.circle(pill, (box[0]+r, box[1]+r), r, 255, -1)
    cv2.circle(pill, (box[2]-r, box[1]+r), r, 255, -1)
    pill = cv2.GaussianBlur(pill, (0, 0), 1.2).astype(np.float32)[..., None] / 255.0
    return (out * (1 - pill)).astype(np.uint8)


def glare_layer(photo_bgr, mask, scale=1.0):
    """사진 화면에 원래 있던 반사광·지문을 뽑아낸다. 붙여넣은 티를 없애는 핵심.

    주의: 그냥 (L - 흐린L) 로 뽑으면 **원래 화면에 있던 글자까지** 딸려 나와
    새 화면 위에 옛 글자가 유령처럼 비친다. 반사광은 넓고 부드럽고, 글자는 가늘다.
    그래서 먼저 글자 굵기만큼 뭉갠 다음(fine) 훨씬 더 흐린 것(base)을 뺀다.
    scale 은 --scale 로 사진을 키운 배율. 흐리는 반경도 같이 키워야 한다.
    """
    lab = cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].astype(np.float32)
    fine = cv2.GaussianBlur(L, (0, 0), 5 * scale)    # 글자·아이콘 지우기
    base = cv2.GaussianBlur(L, (0, 0), 30 * scale)
    hi = np.clip(fine - base, 0, None)               # 넓은 반사광만 남는다
    hi[mask == 0] = 0
    return hi


def composite(photo, screen_png, quad, out_path, island=True,
              glare=0.9, blur=0.0, exposure=1.0, scale=1.0, sharpen=0.0, edge=1.0):
    ph = cv2.imread(photo, cv2.IMREAD_COLOR)
    sc = cv2.imread(screen_png, cv2.IMREAD_COLOR)
    if ph is None or sc is None:
        sys.exit(f"이미지를 못 읽음: {photo if ph is None else screen_png}")
    SCREEN_W, SCREEN_H = sc.shape[1], sc.shape[0]
    corner_r = CORNER_R * SCREEN_W / float(REF_W)
    if island:
        sc = add_island(sc)
    if exposure != 1.0:
        sc = np.clip(sc.astype(np.float32) * exposure, 0, 255).astype(np.uint8)

    q = quad.astype(np.float32) * float(scale)
    if scale != 1.0:                       # 사진을 키워 화면 글자에 픽셀을 더 준다
        ph = cv2.resize(ph, (int(round(ph.shape[1]*scale)), int(round(ph.shape[0]*scale))),
                        interpolation=cv2.INTER_LANCZOS4)
        if sharpen > 0:                    # 확대로 무뎌진 사진만 살짝 살린다
            blurred = cv2.GaussianBlur(ph, (0, 0), 1.2)
            ph = cv2.addWeighted(ph, 1 + sharpen, blurred, -sharpen, 0)
    H, W = ph.shape[:2]

    # 화면이 사진 안에서 실제로 차지하는 크기
    L = lambda a, b: float(np.linalg.norm(q[a] - q[b]))
    tw = (L(0, 1) + L(3, 2)) / 2.0
    th = (L(0, 3) + L(1, 2)) / 2.0

    # 앨리어싱 방지: warpPerspective 는 큰 축소에서 제대로 평균을 내지 못하므로
    # 목표 크기의 1.3배까지 INTER_AREA 로 먼저 줄인 뒤 워프한다.
    f = min(1.0, min(tw * 1.3 / SCREEN_W, th * 1.3 / SCREEN_H))
    if f < 0.95:
        sw, sh = max(2, int(round(SCREEN_W * f))), max(2, int(round(SCREEN_H * f)))
        src_img = cv2.resize(sc, (sw, sh), interpolation=cv2.INTER_AREA)
    else:
        f, sw, sh, src_img = 1.0, SCREEN_W, SCREEN_H, sc

    src = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])
    M = cv2.getPerspectiveTransform(src, q)
    warped = cv2.warpPerspective(src_img, M, (W, H), flags=cv2.INTER_LANCZOS4,
                                 borderMode=cv2.BORDER_REPLICATE)

    m = rounded_mask(sw, sh, max(2, int(round(corner_r * f))))
    wm = cv2.warpPerspective(m, M, (W, H), flags=cv2.INTER_LINEAR)
    # 경계를 베젤 쪽으로 몇 px 밀어 둔다. 이걸 안 하면 부드럽게 흐려지는 구간에
    # **사진에 원래 있던 화면 색이 실오라기처럼 비친다**(이 건은 보라색 선).
    # 밀어낸 만큼 새 화면이 베젤을 덮지만 원본 사진 기준 1px 남짓이라 보이지 않는다.
    e = int(round(edge * max(1.0, scale)))
    if e > 0:
        wm = cv2.dilate(wm, np.ones((2 * e + 1, 2 * e + 1), np.uint8))
    wm = cv2.GaussianBlur(wm, (0, 0), 0.8 * max(1.0, scale))

    if blur > 0:
        warped = cv2.GaussianBlur(warped, (0, 0), blur)

    if glare > 0:
        hi = glare_layer(ph, (wm > 8).astype(np.uint8), scale)
        w = warped.astype(np.float32)
        w = 255 - (255 - w) * (255 - hi[..., None] * glare) / 255.0   # 스크린 블렌드
        warped = np.clip(w, 0, 255).astype(np.uint8)

    a = (wm.astype(np.float32) / 255.0)[..., None]
    out = (ph.astype(np.float32) * (1 - a) + warped.astype(np.float32) * a)
    cv2.imwrite(out_path, np.clip(out, 0, 255).astype(np.uint8),
                [cv2.IMWRITE_PNG_COMPRESSION, 6])
    return out_path, f, (tw, th)


def unwarp(photo, quad, out_path, size=(1179, 2556)):
    """사진 속 화면을 정면으로 펴서 저장한다 — 좌표가 맞는지 눈으로 보는 용도.

    아일랜드와 하단 홈 인디케이터가 온전히 복원되면 좌표가 맞은 것이다.
    매칭 점수·검출 성공 메시지는 정합성의 증거가 아니다. 반드시 이 그림을 본다.
    """
    ph = cv2.imread(photo, cv2.IMREAD_COLOR)
    W, H = size
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    out = cv2.warpPerspective(ph, M, (W, H), flags=cv2.INTER_LANCZOS4)
    cv2.imwrite(out_path, out)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photo', required=True)
    ap.add_argument('--quad', help='x1,y1,x2,y2,x3,y3,x4,y4 (좌상→우상→우하→좌하)')
    ap.add_argument('--detect', action='store_true')
    ap.add_argument('--match', help='합성에 쓰인 원본 화면 이미지 (특징점 매칭으로 좌표 추출)')
    ap.add_argument('--grid', action='store_true')
    ap.add_argument('--lang')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--suffix', default='_합성')
    ap.add_argument('--screens', help='언어별 화면 이미지가 있는 폴더 (기본: 이 스크립트 상위)')
    ap.add_argument('--screen-prefix', default='lockscreen_', help='화면 파일 이름 앞부분')
    ap.add_argument('--out-dir', help='결과를 저장할 폴더 (기본: 사진과 같은 폴더)')
    ap.add_argument('--out-prefix', default='', help='결과 파일 이름 앞부분 (주면 --suffix 대신 씀)')
    ap.add_argument('--unwarp', action='store_true', help='좌표 확인용 역워프 이미지만 만든다')
    ap.add_argument('--no-island', action='store_true')
    ap.add_argument('--glare', type=float, default=0.9)
    ap.add_argument('--blur', type=float, default=0.0)
    ap.add_argument('--exposure', type=float, default=1.0)
    ap.add_argument('--scale', type=float, default=1.0,
                    help='출력 배율. 바탕 사진이 작아 화면 글씨가 뭉개질 때 2~3 을 준다')
    ap.add_argument('--edge', type=float, default=1.0,
                    help='화면 경계를 베젤 쪽으로 미는 양(원본 사진 px). 가장자리에 옛 화면 색이 비치면 키운다')
    ap.add_argument('--sharpen', type=float, default=0.35,
                    help='--scale 로 확대한 사진의 선명도 보정 (0 이면 끔)')
    a = ap.parse_args()

    img = cv2.imread(a.photo, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"사진을 못 읽음: {a.photo}")
    print(f"사진 크기: {img.shape[1]} x {img.shape[0]}")

    if a.grid:
        p, step = write_grid(a.photo, img)
        print(f"격자 이미지: {p}  (칸 {step}px, 굵은 선 {step*5}px)")
        print("화면 네 귀퉁이를 읽어서 --quad 로 넘겨주세요 (좌상→우상→우하→좌하)")
        return

    q = None
    if a.quad:
        q = order_quad([float(v) for v in a.quad.split(',')])
    elif a.match:
        n, q = match_quad(a.match, a.photo)
        print(f"특징점 매칭 inliers = {n}" + ("  (40 미만이면 의심)" if n < 40 else ""))
        if q is None:
            sys.exit("매칭 실패 — 다른 원본 이미지를 지정하거나 --grid 를 쓰세요")
    elif a.detect:
        q = detect_quad(img)
        if q is None:
            sys.exit("자동 검출 실패 — --grid 로 좌표를 직접 읽어주세요")
    elif os.path.exists(quad_path(a.photo)):
        q = np.array(json.load(open(quad_path(a.photo))), np.float32)

    if q is None:
        sys.exit("화면 좌표가 없습니다. --detect 또는 --grid 또는 --quad 를 쓰세요")

    json.dump(q.tolist(), open(quad_path(a.photo), 'w'))
    print("화면 네 귀퉁이:", [[round(x), round(y)] for x, y in q])

    v = img.copy()
    cv2.polylines(v, [q.astype(int)], True, (0, 0, 255), 3)
    for i, (x, y) in enumerate(q):
        cv2.circle(v, (int(x), int(y)), 9, (0, 255, 0), -1)
        cv2.putText(v, str(i+1), (int(x)+12, int(y)), cv2.FONT_HERSHEY_SIMPLEX, .9, (0, 255, 0), 2)
    prev = os.path.splitext(a.photo)[0] + '_quad확인.png'
    cv2.imwrite(prev, v)
    print("좌표 확인용:", prev)

    if a.unwarp:
        scr_dir = os.path.abspath(a.screens) if a.screens else OUT_DIR
        cand = [os.path.join(scr_dir, f'{a.screen_prefix}{L}.png') for L in LANGS]
        cand = [c for c in cand if os.path.exists(c)]
        sz = screen_size(cand[0]) if cand else (1179, 2556)
        p = unwarp(a.photo, q, os.path.splitext(a.photo)[0] + '_역워프.png', sz)
        print("역워프:", p)
        print("  ← 아일랜드와 하단 홈 인디케이터가 온전한지 눈으로 확인할 것")
        return

    langs = LANGS if a.all else ([a.lang] if a.lang else [])
    scr_dir = os.path.abspath(a.screens) if a.screens else OUT_DIR
    out_dir = os.path.abspath(a.out_dir) if a.out_dir else os.path.dirname(os.path.abspath(a.photo))
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.photo))[0]
    for L in langs:
        sp = os.path.join(scr_dir, f'{a.screen_prefix}{L}.png')
        if not os.path.exists(sp):
            print(f"  건너뜀 (없음): {sp}"); continue
        outp = (os.path.join(out_dir, f'{a.out_prefix}{L}.png') if a.out_prefix
                else os.path.join(out_dir, f'{base}{a.suffix}_{L}.png'))
        _, f, (tw, th) = composite(a.photo, sp, q, outp, island=not a.no_island,
                                   glare=a.glare, blur=a.blur, exposure=a.exposure,
                                   scale=a.scale, sharpen=a.sharpen, edge=a.edge)
        print(f"  -> {outp}   화면 {tw:.0f}x{th:.0f}px (원본의 {f*100:.0f}%)")


if __name__ == '__main__':
    main()
