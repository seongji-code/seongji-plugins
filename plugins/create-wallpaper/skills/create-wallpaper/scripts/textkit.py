# -*- coding: utf-8 -*-
"""다국어 화면 렌더에 쓰는 폰트·글자 크기 도구 모음.

화면마다 좌표는 다르지만 폰트 세트와 '잉크 높이로 크기를 맞추는' 방식은 같다.
그 공통부만 여기에 모아 두고, 화면별 좌표는 각 작업 폴더의 render.py 가 갖는다.

핵심 개념 — **잉크 높이(ink height)**
  포인트 크기가 아니라 '참조 글자가 실제로 그려지는 세로 픽셀 수'로 크기를 맞춘다.
  원본 스크린샷에서 잰 글자 높이를 그대로 넣으면 언어·폰트가 달라도 같은 크기로 보인다.
  참조 글자는 CJK='書'(또는 '월'), 라틴='H'. 라틴은 대문자 높이라 CJK의 0.85배로 환산한다.
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 2                       # 수퍼샘플링 배율 (2배로 그린 뒤 축소)
HOME = os.path.expanduser('~')
AV2 = '/System/Library/AssetsV2/com_apple_MobileAsset_Font8'

LANGS = ["ko", "ja", "zh-TW", "ms", "en-US", "en-GB", "fr", "vi"]

_apple_cache = {}


def apple(n):
    """macOS 다운로드 폰트 자산에서 이름으로 찾아온다 (PingFang 등)."""
    if n in _apple_cache:
        return _apple_cache[n]
    for r, _, fs in os.walk(AV2):
        if n in fs:
            _apple_cache[n] = os.path.join(r, n)
            return _apple_cache[n]
    raise FileNotFoundError(n)


# ── 본문 폰트: 미피·메타몽·도라에몽 시리즈 공통 둥근고딕 3종 ─────────────────
F_HAN_B = HOME + '/Library/Fonts/ResourceHanRoundedCN-Bold.ttf'    # 번체·라틴·베트남어
F_HAN_R = HOME + '/Library/Fonts/ResourceHanRoundedCN-Medium.ttf'
F_JP_B  = HOME + '/Library/Fonts/ShinRetroMaruGothic-Bold.ttf'     # 일본어
F_JP_R  = HOME + '/Library/Fonts/ShinRetroMaruGothic-Medium.ttf'
F_KR    = HOME + '/Library/Fonts/Griun_Fromsol-Rg.ttf'             # 한국어 — 그리운 프롬솔
F_KR_FB = HOME + '/Library/Fonts/' + '온글잎 행복한맹쿼카체.ttf'    # 프롬솔에 없는 글자(·) 대체
KR_STROKE = 1   # 프롬솔은 단일 웨이트라 제목만 가짜볼드 (2배 렌더 기준 = 실제 0.5px)

FONTS = {
 "ko":    dict(bold=(F_KR, 0, None), reg=(F_KR, 0, None), ref='월',
               stroke=KR_STROKE, fb=(F_KR_FB, 0, None)),
 "ja":    dict(bold=(F_JP_B, 0, None),  reg=(F_JP_R, 0, None),  ref='書'),
 "zh-TW": dict(bold=(F_HAN_B, 0, None), reg=(F_HAN_R, 0, None), ref='書'),
}
_lat = dict(bold=(F_HAN_B, 0, None), reg=(F_HAN_R, 0, None), ref='H')
for _k in ("ms", "en-US", "en-GB", "fr", "vi"):
    FONTS[_k] = _lat

# ── 시계 위 날짜 줄만 iOS 기본 시스템 폰트 (손글씨/둥근고딕 아님) ────────────
SFPRO    = '/Library/Fonts/SF-Pro-Display-Semibold.otf'
SDGOTHIC = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
HIRAGINO = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
DATE_FONTS = {
 "ko":    (SDGOTHIC, 4, None),                # Apple SD Gothic Neo SemiBold
 "ja":    (HIRAGINO, 0, None),                # Hiragino Sans W6
 "zh-TW": (apple('PingFang.ttc'), 10, None),  # PingFang TC Semibold
}
for _k in ("ms", "en-US", "en-GB", "fr", "vi"):
    DATE_FONTS[_k] = (SFPRO, 0, None)
DATE_REF = {"ko": '월', "ja": '書', "zh-TW": '書'}   # 나머지는 'H'

LAT = 0.85          # 라틴 참조 글자('H')는 대문자 높이 → CJK 잉크 높이의 0.85배
STROKE_ON = int(os.environ.get('STROKE', '1'))


# ── 폰트 로드 / 크기 계산 ───────────────────────────────────────────────────
def load(spec, size):
    path, idx, axes = spec
    f = ImageFont.truetype(path, size, index=idx)
    if axes:
        try:
            f.set_variation_by_axes(axes)
        except Exception:
            pass
    return f


def fit(spec, ref, target):
    """참조 글자의 잉크 높이가 target(px)이 되는 폰트 크기를 이분탐색으로 찾는다.

    돌려주는 값: (폰트, 크기, off) — off 는 baseline 기준 잉크 세로중심 오프셋.
    글자를 세로중심 cy 에 놓으려면 baseline = cy - off 로 그린다.
    """
    lo, hi, best = 6, 300, 20
    for _ in range(40):
        mid = (lo + hi) / 2
        f = load(spec, max(1, int(round(mid))))
        b = f.getbbox(ref, anchor='ls')
        if (b[3] - b[1]) < target:
            lo = mid
        else:
            hi = mid
        best = mid
    size = max(1, int(round(best)))
    f = load(spec, size)
    b = f.getbbox(ref, anchor='ls')
    return f, size, (b[1] + b[3]) / 2.0


_cmap = {}


def cmap_of(spec):
    key = (spec[0], spec[1])
    if key not in _cmap:
        from fontTools.ttLib import TTFont, TTCollection
        path, idx = key
        fo = (TTCollection(path).fonts[idx] if path.lower().endswith(('.ttc', '.otc'))
              else TTFont(path, fontNumber=idx, lazy=True))
        _cmap[key] = set(fo.getBestCmap() or {})
    return _cmap[key]


def runs_of(text, spec, fbspec):
    """본문 폰트에 없는 글자만 폴백 폰트로 넘기도록 구간을 나눈다."""
    if not fbspec:
        return [(text, False)]
    cm = cmap_of(spec)
    out = []
    for ch in text:
        fb = ord(ch) not in cm
        if out and out[-1][1] == fb:
            out[-1][0] += ch
        else:
            out.append([ch, fb])
    return [(t, f) for t, f in out]


def is_cjk(s):
    return any('぀' <= ch <= '鿿' for ch in s)


# ── 로케일별 글자 스타일 묶음 ───────────────────────────────────────────────
class Ctx:
    """한 로케일에서 쓸 글자 스타일을 미리 만들어 둔다.

    targets: {스타일이름: (잉크높이, 'bold'|'reg')} — 원본에서 잰 값
    boosts:  {스타일이름: {로케일: 배수}}  — 칩처럼 폭이 고정된 곳의 언어별 보정
    date_cy: 날짜 줄 잉크 세로중심. 주면 'date' 스타일과 date_baseline 을 만든다.
    """

    def __init__(self, loc, targets, boosts=None, date_ink=None, date_cy=None):
        self.loc = loc
        self.fc = FONTS[loc]
        self.stroke = self.fc.get('stroke', 0) * (1 if STROKE_ON else 0)
        self.latin = self.fc['ref'] == 'H'
        self.styles = {}
        boosts = boosts or {}
        for st, (ink, role) in targets.items():
            tgt = ink * LAT if self.latin else ink
            tgt *= boosts.get(st, {}).get(loc, 1.0)
            spec = self.fc[role]
            f, size, off = fit(spec, self.fc['ref'], tgt * S)
            self.styles[st] = (spec, f, size, off)

        self.date_baseline = None
        if date_ink and date_cy is not None:
            # 한국어(Apple SD Gothic Neo)에서 실제 포인트 크기를 역산한 뒤,
            # iOS 가 그러듯 모든 언어에 같은 크기·같은 베이스라인을 적용한다.
            _, size, off_ko = fit(DATE_FONTS['ko'], '월', date_ink * S)
            self.date_baseline = date_cy * S - off_ko
            spec = DATE_FONTS[loc]
            f = load(spec, size)
            b = f.getbbox(DATE_REF.get(loc, 'H'), anchor='ls')
            self.styles['date'] = (spec, f, size, (b[1] + b[3]) / 2.0)

    def get(self, st):
        return self.styles[st]


def draw_text(d, ctx, st, x, cy, text, color, align='l', maxw=None, force=None, stroke=0):
    """x=왼쪽 잉크 끝(align='l') 또는 가로중심(align='c'), cy=잉크 세로중심."""
    spec, f, size, off = ctx.get(st)
    if force:                                   # 로케일 단위로 통일된 크기 사용
        f, size, off = force
    x, cy = x * S, cy * S
    if maxw and not force:
        w = d.textlength(text, font=f)
        if w > maxw * S:
            size = max(8, int(size * (maxw * S) / w))
            f = load(spec, size)
            b = f.getbbox(ctx.fc['ref'], anchor='ls')
            off = (b[1] + b[3]) / 2.0
            print(f'    [줄임] {st}: "{text}"')
    base = cy - off
    kw = dict(stroke_width=stroke, stroke_fill=color) if stroke else {}
    parts = runs_of(text, spec, ctx.fc.get('fb'))
    fonts = [load(ctx.fc['fb'], size) if isfb else f for _, isfb in parts]
    widths = [d.textlength(t, font=ft) for (t, _), ft in zip(parts, fonts)]
    if align == 'c':
        cur = x - sum(widths) / 2.0
    else:
        cur = x - fonts[0].getbbox(parts[0][0], anchor='ls')[0]
    for (t, _), ft, w in zip(parts, fonts, widths):
        d.text((cur, base), t, font=ft, fill=color, anchor='ls', **kw)
        cur += w


def draw_date(d, ctx, text, cx, color, maxw):
    """날짜 줄 — 가로중심 정렬, 로케일 공통 베이스라인."""
    spec, f, size, off = ctx.get('date')
    if d.textlength(text, font=f) > maxw * S:
        size = max(8, int(size * (maxw * S) / d.textlength(text, font=f)))
        f = load(spec, size)
    d.text((cx * S, ctx.date_baseline), text, font=f, fill=color, anchor='ms')


def uniform(ctx, st, items, draw):
    """(문자열, 허용폭) 목록이 전부 들어가는 하나의 크기로 통일.

    한 화면 안에서 줄마다 글자 크기가 들쭉날쭉해 보이지 않게 하는 장치다.
    """
    spec, f, size, off = ctx.get(st)
    ratio = 1.0
    for t, maxw in items:
        w = draw.textlength(t, font=f)
        if w > maxw * S:
            ratio = min(ratio, (maxw * S) / w)
    if ratio >= 0.999:
        return (f, size, off)
    size = max(8, int(size * ratio))
    f = load(spec, size)
    b = f.getbbox(ctx.fc['ref'], anchor='ls')
    return (f, size, (b[1] + b[3]) / 2.0)


# ── 레이어 ─────────────────────────────────────────────────────────────────
def new_layer(plate):
    """plate 크기의 S배 투명 레이어와 그 Draw 를 만든다."""
    W, H = plate.size
    layer = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def flatten(plate, layer, outpath):
    """S배 레이어를 축소해 plate 위에 얹고 저장한다."""
    layer = layer.resize(plate.size, Image.LANCZOS)
    out = plate.convert('RGBA')
    out.alpha_composite(layer)
    out.convert('RGB').save(outpath)
    return outpath
