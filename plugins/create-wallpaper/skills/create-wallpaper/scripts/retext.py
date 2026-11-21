# -*- coding: utf-8 -*-
"""이미 완성된 이미지 위에서 글자만 갈아끼운다.

날짜 하나, 단어 하나만 고치면 되는데 전체를 다시 렌더하고 다시 합성하면
손대지 않은 곳까지 화질이 깎인다. 그럴 때는 그 자리의 픽셀만 바꾸는 쪽이 깨끗하다.
폰이 거의 정면으로 찍힌 사진이면 원근 보정 없이 바로 쓸 수 있다.
(많이 기울어진 사진이면 mockup.py --unwarp 로 편 다음 이 도구를 쓰고 다시 합성한다)

순서
  1) scan  — 고칠 영역의 글자 줄·글자 덩어리 좌표를 잰다
  2) fit   — 그 자리의 **기존 글자**를 다시 그려 보며 폰트·크기·블러·색을 맞춘다
  3) apply — 맞춰진 값으로 지우고 새 글자를 그린다

fit 이 이 도구의 핵심이다. 원본이 어떤 폰트로 몇 px 에 그려졌는지는 눈으로 못 맞춘다.
기존 글자를 재현해 보고 오차가 작은 설정을 고른 뒤 그 설정으로 새 글자를 그려야
원래 있던 글자처럼 보인다. 맥에서 돌리면 진짜 애플 시스템 폰트를 후보로 쓰므로
거의 정확하게 맞는다.

사용법
  python3 retext.py scan 사진.png --region 360,240,790,490
  python3 retext.py fit 사진.png --box 416,258,449,286 --text "18" \\
      --fonts apple-latin --out _작업/fit_18.json
  python3 retext.py apply 사진.png --plan _작업/plan.json --out 결과.png

주의
  - fit 이 내놓는 오차 숫자만 믿지 않는다. 같이 나오는 `*_대조.png` 를 **직접 보고**
    획 굵기와 밝기가 원본과 같은지 확인한다.
  - apply 결과도 100% 확대해서 **직접 본다.** 지운 자리의 이음새와 글자 번짐을 본다.
"""
import argparse, glob, json, os, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features as PILfeatures

SS = 8                      # 슈퍼샘플 배수 — 작은 글자를 부드럽게 뽑기 위해
HAS_RAQM = PILfeatures.check('raqm')    # OpenType 기능(tnum 등) 적용 가능 여부

# ── 폰트 찾기 ────────────────────────────────────────────────────────────────
APPLE_SETS = {
    'apple-latin': ['/Library/Fonts/SF-Pro-Display-*.otf',
                    '/Library/Fonts/SF-Pro-Text-*.otf',
                    '/System/Library/Fonts/SFNS*.ttf'],
    'apple-tc':    ['PingFang.ttc'],
    'apple-ko':    ['/System/Library/Fonts/AppleSDGothicNeo.ttc'],
    'apple-ja':    ['/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'],
}
_AV2 = os.path.expanduser('~/Library/Application Support/Apple/Fonts')


def _find_apple_asset(name):
    """macOS 가 따로 내려받아 두는 폰트(PingFang 등)를 이름으로 찾는다."""
    for root in (_AV2, '/System/Library/AssetsV2', '/System/Library/Fonts'):
        if not os.path.isdir(root):
            continue
        for r, _, fs in os.walk(root):
            if name in fs:
                return os.path.join(r, name)
    return None


def expand_font(spec):
    """폰트 지정 하나를 (경로, 인덱스) 목록으로 펼친다.

    'a.ttf' / 'a.ttc#2' / 'apple-tc' / '/경로/*.otf' 를 모두 받는다.
    .ttc 는 인덱스를 안 주면 안에 든 얼굴을 전부 후보로 쓴다.
    """
    out = []
    if '#' in spec and not spec.startswith('apple-'):
        p, i = spec.rsplit('#', 1)
        return [(p, int(i))]
    pats = APPLE_SETS.get(spec, [spec])
    for pat in pats:
        if os.path.sep not in pat and not pat.startswith('~'):
            hit = _find_apple_asset(pat)
            paths = [hit] if hit else []
        else:
            paths = sorted(glob.glob(os.path.expanduser(pat)))
        for p in paths:
            if not os.path.isfile(p):
                continue
            if p.lower().endswith(('.ttc', '.otc')):
                n = 0
                while True:                      # 안에 든 얼굴 수만큼
                    try:
                        ImageFont.truetype(p, 20, index=n)
                    except Exception:
                        break
                    out.append((p, n)); n += 1
                    if n > 40:
                        break
            else:
                out.append((p, 0))
    return out


def font_label(spec):
    p, i = spec
    return os.path.basename(p) + (f'#{i}' if i else '')


# ── 글자 그리기 ──────────────────────────────────────────────────────────────
_big_cache = {}


def _big(text, spec, size, feats=None):
    """펜 원점을 (pad,pad) 에 두고 크게 그려 둔 알파맵. 같은 설정은 재사용한다."""
    key = (text, spec, round(size * 4), feats)
    if key not in _big_cache:
        path, idx = spec
        f = ImageFont.truetype(path, max(1, int(round(size * SS))), index=idx)
        pad = int(round(size * SS * 3)) + SS * 8
        im = Image.new('L', (pad * 2 + len(text) * int(size * SS * 2) + SS, pad * 2), 0)
        kw = {'features': list(feats)} if (feats and HAS_RAQM) else {}
        ImageDraw.Draw(im).text((pad, pad), text, font=f, fill=255, anchor='ls', **kw)
        if len(_big_cache) > 400:
            _big_cache.clear()
        _big_cache[key] = (np.asarray(im, np.float32) / 255.0, pad)
    return _big_cache[key]


def glyph_alpha(text, spec, size, W, H, penx, peny, blur=0.0, gain=1.0, feats=None):
    """W x H 창에 글자를 그린 알파맵. (penx,peny) 는 창 안에서의 펜 원점(왼쪽·베이스라인).

    펜 오프셋이 패딩을 넘어가도 깨지지 않도록 원본·대상 구간을 둘 다 클리핑한다.
    (여기를 대충 짜면 글자가 소리 없이 창 밖으로 나가 통째로 사라진다)
    """
    big, pad = _big(text, spec, size, feats)
    sx = int(round(pad - penx * SS))
    sy = int(round(pad - peny * SS))
    out = np.zeros((H * SS, W * SS), np.float32)
    dx0, dy0 = max(0, -sx), max(0, -sy)
    sx0, sy0 = max(0, sx), max(0, sy)
    w = min(W * SS - dx0, big.shape[1] - sx0)
    h = min(H * SS - dy0, big.shape[0] - sy0)
    if w > 0 and h > 0:
        out[dy0:dy0 + h, dx0:dx0 + w] = big[sy0:sy0 + h, sx0:sx0 + w]
    a = cv2.resize(out, (W, H), interpolation=cv2.INTER_AREA)
    if blur > 0:
        a = cv2.GaussianBlur(a, (0, 0), blur)
    return np.clip(a * gain, 0, 1)


def ink_box(text, spec, size, feats=None, thr=0.12):
    """그린 글자의 잉크 bbox 를 펜 원점 기준 (dx0, dy0, dx1, dy1) 로. 단위는 실제 px.

    블러를 먹인 뒤 재면 글자마다 경계가 달라져 베이스라인이 1px 씩 튄다.
    그래서 블러 전 슈퍼샘플 원본에서 재고, 1/SS px 정밀도로 돌려준다.
    """
    big, pad = _big(text, spec, size, feats)
    ys, xs = np.where(big > thr)
    if not len(xs):
        return None
    return ((xs.min() - pad) / SS, (ys.min() - pad) / SS,
            (xs.max() + 1 - pad) / SS, (ys.max() + 1 - pad) / SS)


def pen_from_align(text, spec, size, align, feats=None):
    """{center_x, ink_top} 같은 정렬 지시를 펜 원점으로 바꾼다.

    한 줄에 여러 글자를 같은 높이로 앉힐 때는 ink_top 보다 baseline 이 안전하다.
    글자마다 잉크 윗변이 미세하게 달라서(숫자 1 과 0 등) 줄이 들쑥날쑥해질 수 있다.
    fit 이 돌려주는 pen 의 y 값이 곧 그 줄의 베이스라인이다.
    """
    bb = ink_box(text, spec, size, feats)
    if bb is None:
        sys.exit(f'글자가 비었다: {text!r}')
    dx0, dy0, dx1, dy1 = bb
    if 'center_x' in align:
        penx = align['center_x'] - (dx0 + dx1) / 2.0
    elif 'ink_left' in align:
        penx = align['ink_left'] - dx0
    elif 'ink_right' in align:
        penx = align['ink_right'] - dx1
    else:
        sys.exit('align 에 center_x / ink_left / ink_right 중 하나가 있어야 한다')
    if 'ink_top' in align:
        peny = align['ink_top'] - dy0
    elif 'baseline' in align:
        peny = align['baseline']
    elif 'ink_bottom' in align:
        peny = align['ink_bottom'] - dy1
    else:
        sys.exit('align 에 ink_top / ink_bottom / baseline 중 하나가 있어야 한다')
    return float(penx), float(peny)


# ── 배경 지우기 ──────────────────────────────────────────────────────────────
def erase(img, box, above, below, noise=0.0, seed=7):
    """글자 띠를 지우고 위·아래 깨끗한 줄에서 세로로 보간해 메운다.

    배경이 매끈한 그라데이션일 때 인페인트보다 깔끔하다. 배경에 무늬가 있으면
    이 방법 대신 plate.py 의 인페인트를 쓴다.
    """
    H, W = img.shape[:2]
    x0, y0, x1, y1 = box
    if not (0 <= x0 <= x1 < W and 0 <= y0 <= y1 < H):
        sys.exit(f'지울 영역이 이미지({W}x{H}) 밖이다: {box}')
    for nm, r in (('above', above), ('below', below)):
        if not (0 <= r[0] <= r[1] < H):
            sys.exit(f'{nm} 구간이 이미지 밖이다: {r}')
    A = img[above[0]:above[1] + 1, x0:x1 + 1].mean(0)
    B = img[below[0]:below[1] + 1, x0:x1 + 1].mean(0)
    A = cv2.GaussianBlur(A.reshape(1, -1, 3), (0, 0), 2.0).reshape(-1, 3)
    B = cv2.GaussianBlur(B.reshape(1, -1, 3), (0, 0), 2.0).reshape(-1, 3)
    n = y1 - y0 + 1
    for i, y in enumerate(range(y0, y1 + 1)):
        t = (i + 0.5) / n
        img[y, x0:x1 + 1] = A * (1 - t) + B * t
    if noise > 0:
        rng = np.random.default_rng(seed)
        img[y0:y1 + 1, x0:x1 + 1] += rng.normal(
            0, noise, (n, x1 - x0 + 1, 3)).astype(np.float32)


# ── 색 뽑기 ─────────────────────────────────────────────────────────────────
def pick_colors(img, box, pct=0.99):
    """글자 상자에서 배경색(어두운 쪽 중앙값)과 글자색(밝은 쪽 상위)을 추정한다."""
    x0, y0, x1, y1 = box
    s = img[y0:y1 + 1, x0:x1 + 1].reshape(-1, 3)
    lum = s.mean(1)
    o = lum.argsort()
    bg = np.median(s[o[:max(8, int(len(o) * 0.35))]], axis=0)
    fg = s[o[int(len(o) * pct):]].mean(0)
    return bg.astype(np.float32), fg.astype(np.float32)


# ── 1) scan ─────────────────────────────────────────────────────────────────
def cmd_scan(a):
    img = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f'못 읽음: {a.src}')
    H, W = img.shape[:2]
    x0, y0, x1, y1 = ([int(v) for v in a.region.split(',')] if a.region else [0, 0, W - 1, H - 1])
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(float)
    sub = g[y0:y1 + 1, x0:x1 + 1]
    # 자동 임계값: 배경(중앙값)과 글자(상위 0.5%) 사이. 상위값만 쓰면 획이 쪼개진다.
    lo, hi = float(np.median(sub)), float(np.percentile(sub, 99.5))
    thr = a.thr if a.thr else lo + 0.35 * (hi - lo)
    print(f'이미지 {W} x {H}   영역 x {x0}..{x1}  y {y0}..{y1}'
          f'   배경 {lo:.0f} 글자 {hi:.0f} → 임계값 {thr:.0f}')

    rows = (sub > thr).sum(1)
    segs, s = [], None
    for i, v in enumerate(rows):
        if v and s is None:
            s = i
        if not v and s is not None:
            segs.append((y0 + s, y0 + i - 1)); s = None
    if s is not None:
        segs.append((y0 + s, y1))
    segs = [t for t in segs if t[1] - t[0] >= a.minh - 1]

    print(f'\n글자 줄 {len(segs)}개')
    for k, (ya, yb) in enumerate(segs):
        band = g[ya:yb + 1, x0:x1 + 1]
        cols = (band > thr).sum(0)
        gs, st = [], None
        for i, v in enumerate(cols):
            if v and st is None:
                st = i
            if not v and st is not None:
                gs.append((x0 + st, x0 + i - 1)); st = None
        if st is not None:
            gs.append((x0 + st, x1))
        merged = []
        for p, q in gs:
            if merged and p - merged[-1][1] <= a.gap:
                merged[-1] = (merged[-1][0], q)
            else:
                merged.append((p, q))
        print(f'\n  [줄 {k}] y {ya}..{yb}  (높이 {yb-ya+1})   글자 덩어리 {len(merged)}개')
        for j, (p, q) in enumerate(merged):
            print(f'     {j:2d}:  x {p}..{q}   폭 {q-p+1}   중심 {(p+q)/2:.1f}')
        if len(merged) >= 3:
            c = [(p + q) / 2 for p, q in merged]
            d = np.diff(c)
            if d.std() < 1.5:
                print(f'     → 균등 간격으로 보인다: 첫 중심 {c[0]:.1f}, 간격 {d.mean():.2f}')
    print('\n지울 때는 위 y 구간 바깥의 깨끗한 줄을 erase 의 above/below 로 준다.')


# ── 2) fit ──────────────────────────────────────────────────────────────────
def cmd_fit(a):
    img = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f'못 읽음: {a.src}')
    box = [int(v) for v in a.box.split(',')]
    x0, y0, x1, y1 = box
    tgt = img[y0:y1 + 1, x0:x1 + 1].astype(np.float32)
    Hh, Ww = tgt.shape[:2]
    bg, fg = pick_colors(img.astype(np.float32), box)
    if a.bg:
        bg = np.array([float(v) for v in a.bg.split(',')][::-1], np.float32)
    if a.fg:
        fg = np.array([float(v) for v in a.fg.split(',')][::-1], np.float32)
    print(f'상자 {Ww} x {Hh}   배경 RGB {bg[::-1].round(1)}   글자 RGB {fg[::-1].round(1)}')

    specs = []
    for s in a.fonts.split(','):
        specs += expand_font(s.strip())
    if not specs:
        sys.exit(f'폰트를 못 찾았다: {a.fonts}\n'
                 '맥이 아니면 폰트 파일 경로를 직접 줘야 한다 (--fonts /경로/Foo.ttf,/경로/Bar.ttf)')
    print(f'후보 폰트 {len(specs)}개')

    # 목표 글자의 잉크 높이 → 크기 초기값.
    # ink_box 와 **같은 기준**(알파 0.12)으로 재야 한다. 한쪽은 밝은 심지만, 다른 쪽은
    # 가장자리까지 재면 크기 추정이 어긋나고, 최적화가 '글자를 줄이고 농도를 올리는' 쪽으로 샌다.
    INK_THR = 0.12
    lvl = float(bg.mean() + INK_THR * (fg.mean() - bg.mean()))
    ys, xs = np.where(tgt.mean(2) > lvl)
    if not len(ys):
        sys.exit('상자 안에서 글자를 못 찾았다. --box 를 다시 잡아라')
    ink_h = float(ys.max() - ys.min() + 1)
    ink_l, ink_t = x0 + xs.min(), y0 + ys.min()
    print(f'원본 잉크: 높이 {ink_h:.0f}px  왼쪽 x={ink_l}  윗변 y={ink_t}  (밝기 {lvl:.0f} 이상)')

    def err(spec, size, blur, gain, penx, peny, feats):
        al = glyph_alpha(a.text, spec, size, Ww, Hh, penx, peny, blur, gain, feats)[..., None]
        return float(np.abs((bg * (1 - al) + fg * al) - tgt).mean())

    # 숫자는 고정폭(tnum)으로 짜인 경우가 많다 — 달력·시계가 대표적이다.
    # 둘 다 해 보고 맞는 쪽을 고른다. 안 고르면 '1' 이 끼었을 때 폭이 어긋난다.
    featsets = [None]
    if a.features:
        featsets = [tuple(f.strip() for f in a.features.split(',') if f.strip())]
    elif any(c.isdigit() for c in a.text):
        if HAS_RAQM:
            featsets.append(('tnum',))
        else:
            print('⚠️  libraqm 이 없어 고정폭 숫자(tnum)를 시험하지 못한다.'
                  " 1 이 낀 숫자만 폭이 어긋날 수 있다.")

    def search(htol):
        """잉크 높이가 원본과 htol px 이내인 크기만 보고 최적 설정을 찾는다."""
        best = None
        for feats in featsets:
            for spec in specs:
                bb = ink_box(a.text, spec, 100.0, feats)
                if bb is None:
                    continue
                s0 = 100.0 * ink_h / max(1.0, bb[3] - bb[1])      # 잉크 높이로 크기 추정
                for size in np.arange(s0 * 0.86, s0 * 1.16, max(0.2, s0 * 0.02)):
                    bb2 = ink_box(a.text, spec, size, feats)
                    if bb2 is None:
                        continue
                    # 잉크 높이는 믿을 만한 기하 구속이다. 여기서 많이 벗어난 크기는
                    # 농도로 오차를 상쇄할 뿐 실제로는 작은/큰 글자가 되므로 버린다.
                    if abs((bb2[3] - bb2[1]) - ink_h) > htol:
                        continue
                    px0 = (ink_l - x0) - bb2[0]                    # 잉크 왼쪽·윗변 맞춤
                    py0 = (ink_t - y0) - bb2[1]
                    for blur in (0.3, 0.5, 0.7, 0.9, 1.1):
                        for gain in (1.0, 1.12, 1.25):
                            for dy in np.arange(-1.5, 1.51, 0.25):
                                for dx in np.arange(-1.5, 1.51, 0.25):
                                    e = err(spec, size, blur, gain, px0 + dx, py0 + dy, feats)
                                    if best is None or e < best[0]:
                                        best = (e, spec, float(size), blur, gain,
                                                float(px0 + dx), float(py0 + dy), feats)
        return best

    best = search(1.0)
    if best is None:                     # 어느 폰트도 높이가 안 맞으면 제약을 푼다
        print('잉크 높이가 맞는 크기를 못 찾았다 — 제약을 풀고 다시 찾는다')
        best = search(99.0)
    if best is None:
        sys.exit('맞는 설정을 못 찾았다. --fonts 후보를 늘려라')
    e, spec, size, blur, gain, penx, peny, feats = best
    # 상자가 좁으면 평균오차가 커 보인다. 글자-배경 대비로 나눠 상자 크기와 무관하게 본다.
    rel = 100.0 * e / max(1.0, float(np.abs(fg - bg).mean()))
    print(f'\n최적: {font_label(spec)}  크기 {size:.2f}  블러 {blur}  농도 {gain}'
          f"  기능 {','.join(feats) if feats else '없음'}"
          f'  오차 {rel:.1f}% (절대 {e:.2f})')
    print(f'       펜 원점(상자 기준) x={penx:.2f} y={peny:.2f}'
          f'  → 이미지 기준 x={x0+penx:.2f} y={y0+peny:.2f}')

    rec = dict(font=f'{spec[0]}#{spec[1]}', size=size, blur=blur, gain=gain,
               color=[float(v) for v in fg[::-1]], box=box,
               pen=[x0 + penx, y0 + peny], text=a.text,
               features=list(feats) if feats else None,
               error=e, error_pct=rel)
    out = a.out or (os.path.splitext(a.src)[0] + '_fit.json')
    json.dump(rec, open(out, 'w'), ensure_ascii=False, indent=1)

    al = glyph_alpha(a.text, spec, size, Ww, Hh, penx, peny, blur, gain, feats)[..., None]
    rep = bg * (1 - al) + fg * al
    gapc = np.zeros((Hh, 6, 3), np.float32)
    cmp_img = np.hstack([tgt, gapc, rep])
    cmp_path = os.path.splitext(out)[0] + '_대조.png'
    cv2.imwrite(cmp_path, cv2.resize(np.clip(cmp_img, 0, 255).astype(np.uint8),
                                     None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST))
    print(f'\n설정 파일: {out}')
    print(f'대조 이미지: {cmp_path}   ← 왼쪽=원본 오른쪽=재현. **직접 보고** 굵기·밝기를 확인할 것')
    if rel > 12:
        print('오차가 크다. 폰트 후보를 늘리거나 --box 를 다시 잡아라.')


# ── 3) apply ────────────────────────────────────────────────────────────────
def cmd_apply(a):
    img = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f'못 읽음: {a.src}')
    src = img.astype(np.float32)
    out = src.copy()
    plan = json.load(open(a.plan, encoding='utf-8'))

    for b in plan.get('erase', []):
        erase(out, b['box'], b['above'], b['below'], b.get('noise', 0.0))
        print(f"  지움 {b['box']}")

    for t in plan.get('texts', []):
        spec = tuple(t['font'].rsplit('#', 1))
        spec = (spec[0], int(spec[1]) if len(spec) > 1 else 0)
        size, blur, gain = float(t['size']), float(t.get('blur', 0)), float(t.get('gain', 1))
        feats = tuple(t['features']) if t.get('features') else None
        fg = np.array(t['color'][::-1], np.float32)
        if 'pen' in t:
            penx, peny = t['pen']
        else:
            penx, peny = pen_from_align(t['text'], spec, size, t['align'], feats)
        bx = t.get('box')
        if bx is None:                                   # 글자 주위로 넉넉히 잡는다
            pad = int(size * 1.6) + 4
            bx = [int(penx) - pad, int(peny - size * 1.4) - 4,
                  int(penx + size * (len(t['text']) + 1)) + pad, int(peny + size * 0.6) + 4]
        bx = [max(0, bx[0]), max(0, bx[1]),
              min(out.shape[1] - 1, bx[2]), min(out.shape[0] - 1, bx[3])]
        W2, H2 = bx[2] - bx[0] + 1, bx[3] - bx[1] + 1
        al = glyph_alpha(t['text'], spec, size, W2, H2,
                         penx - bx[0], peny - bx[1], blur, gain, feats)[..., None]
        if al.max() < 0.05:
            sys.exit(f"글자가 상자 밖으로 나갔다: {t['text']!r} — box/pen 을 다시 봐라")
        # 가장자리에 잉크가 닿으면 글자가 잘렸다는 뜻이다. 조용히 넘어가면 못 알아챈다.
        e = max(al[0, :, 0].max(), al[-1, :, 0].max(),
                al[:, 0, 0].max(), al[:, -1, 0].max())
        if e > 0.05:
            print(f"     ⚠️  {t['text']!r} 이 상자 가장자리에 닿았다 — box 를 넓혀라")
        reg = out[bx[1]:bx[3] + 1, bx[0]:bx[2] + 1]
        out[bx[1]:bx[3] + 1, bx[0]:bx[2] + 1] = reg * (1 - al) + fg * al
        print(f"  그림 {t['text']!r} 펜 ({penx:.1f}, {peny:.1f})")

    res = np.clip(out, 0, 255).astype(np.uint8)
    cv2.imwrite(a.out, res)

    d = np.abs(src - out).sum(2)
    ys, xs = np.where(d > 12)
    if len(ys):
        print(f'\n바뀐 범위: x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}'
              f'  ({len(ys)}픽셀)')
    print(f'결과: {a.out}   ← 100% 로 확대해서 **직접 볼 것** (이음새·번짐)')


def main():
    ap = argparse.ArgumentParser(description='완성된 이미지 위에서 글자만 갈아끼운다')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('scan', help='글자 줄·덩어리 좌표를 잰다')
    p.add_argument('src')
    p.add_argument('--region', help='x0,y0,x1,y1 (생략하면 전체)')
    p.add_argument('--thr', type=float, default=0, help='밝기 임계값 (0=자동)')
    p.add_argument('--gap', type=int, default=4, help='한 덩어리로 묶을 가로 간격 (한자 획이 쪼개지면 올린다)')
    p.add_argument('--minh', type=int, default=4, help='줄로 칠 최소 높이')
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser('fit', help='기존 글자를 재현해 폰트·크기·색을 맞춘다')
    p.add_argument('src')
    p.add_argument('--box', required=True, help='기존 글자를 감싸는 x0,y0,x1,y1')
    p.add_argument('--text', required=True, help='그 자리에 지금 있는 글자')
    p.add_argument('--fonts', required=True,
                   help='폰트 후보. apple-latin / apple-tc / apple-ko / apple-ja 또는 경로·와일드카드')
    p.add_argument('--features', help="OpenType 기능 (예: tnum). 생략하면 숫자일 때 tnum 도 자동으로 시험한다")
    p.add_argument('--bg', help='배경색 R,G,B (생략하면 자동)')
    p.add_argument('--fg', help='글자색 R,G,B (생략하면 자동)')
    p.add_argument('--out', help='설정 JSON 경로')
    p.set_defaults(fn=cmd_fit)

    p = sub.add_parser('apply', help='계획대로 지우고 새 글자를 그린다')
    p.add_argument('src')
    p.add_argument('--plan', required=True, help='erase/texts 가 든 JSON')
    p.add_argument('--out', required=True)
    p.set_defaults(fn=cmd_apply)

    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
