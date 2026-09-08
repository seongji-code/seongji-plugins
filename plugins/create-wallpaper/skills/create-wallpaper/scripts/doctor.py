# -*- coding: utf-8 -*-
"""환경 점검 — 처음 쓰기 전에 한 번 돌린다.

    python3 doctor.py

폰트가 하나라도 없으면 글자가 네모로 나오거나 스크립트가 죽는다.
라이선스 때문에 폰트 파일을 같이 배포할 수 없어서, 여기서 없는 것만 알려 준다.
"""
import os, shutil, subprocess, sys

H = os.path.expanduser('~')
OK, NG = '  ✅', '  ❌'

# (표시 이름, 경로, 받는 곳, 라이선스 한 줄)
BODY_FONTS = [
    ('그리운 프롬솔 (한국어 본문)', f'{H}/Library/Fonts/Griun_Fromsol-Rg.ttf',
     'https://www.griun.co.kr/fonts/fromsol', '상업적 사용 O / 폰트파일 재배포·수정 X'),
    ('온글잎 행복한맹쿼카체 (한국어 폴백)', f'{H}/Library/Fonts/온글잎 행복한맹쿼카체.ttf',
     'https://noonnu.cc  에서 "온글잎 행복한맹쿼카체" 검색', 'VoyagerX 자체 라이선스 / 수정·판매 X'),
    ('Shin Retro Maru Gothic Bold (일본어)', f'{H}/Library/Fonts/ShinRetroMaruGothic-Bold.ttf',
     'https://typographish.booth.pm/items/4607768', 'SIL OFL 1.1'),
    ('Shin Retro Maru Gothic Medium (일본어)', f'{H}/Library/Fonts/ShinRetroMaruGothic-Medium.ttf',
     'https://typographish.booth.pm/items/4607768', 'SIL OFL 1.1'),
    ('Resource Han Rounded CN Bold (번체·라틴·베트남어)',
     f'{H}/Library/Fonts/ResourceHanRoundedCN-Bold.ttf',
     'https://github.com/CyanoHao/Resource-Han-Rounded/releases', 'SIL OFL 1.1'),
    ('Resource Han Rounded CN Medium (번체·라틴·베트남어)',
     f'{H}/Library/Fonts/ResourceHanRoundedCN-Medium.ttf',
     'https://github.com/CyanoHao/Resource-Han-Rounded/releases', 'SIL OFL 1.1'),
]

SYS_FONTS = [
    ('SF Pro Display Semibold (날짜 줄·라틴)', '/Library/Fonts/SF-Pro-Display-Semibold.otf',
     'https://developer.apple.com/fonts/  (SF Pro 받아서 설치)',
     '재배포 X / 용도는 애플 OS UI 목업으로 한정 — 홍보물 사용은 각자 확인'),
    ('Apple SD Gothic Neo (날짜 줄·한국어)', '/System/Library/Fonts/AppleSDGothicNeo.ttc',
     'macOS 기본', ''),
    ('히라기노 각고딕 W6 (날짜 줄·일본어)', '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc',
     'macOS 기본', ''),
]

PKGS = [('cv2', 'opencv-python'), ('PIL', 'Pillow'),
        ('numpy', 'numpy'), ('fontTools', 'fonttools')]


def head(t):
    print(f'\n── {t} ' + '─' * max(0, 58 - len(t)))


def main():
    bad = []

    head('운영체제')
    if sys.platform == 'darwin':
        print(f'{OK} macOS')
    else:
        print(f'{NG} macOS 전용이다 (시스템 폰트·swift 날짜 검증). 지금: {sys.platform}')
        bad.append('os')

    head('파이썬 패키지')
    for mod, pip in PKGS:
        try:
            __import__(mod)
            print(f'{OK} {pip}')
        except ImportError:
            print(f'{NG} {pip}   →  python3 -m pip install {pip}')
            bad.append(pip)

    head('날짜 표기 검증 (CLDR)')
    if shutil.which('swift'):
        print(f'{OK} swift')
    else:
        print(f'{NG} swift 없음  →  Xcode 또는 Command Line Tools 설치 (xcode-select --install)')
        bad.append('swift')

    head('본문 폰트 — 각자 설치해야 한다 (라이선스상 같이 배포 못 함)')
    for name, path, url, lic in BODY_FONTS:
        if os.path.isfile(path):
            print(f'{OK} {name}')
        else:
            print(f'{NG} {name}')
            print(f'      받는 곳: {url}')
            print(f'      라이선스: {lic}')
            print(f'      넣을 곳: {os.path.dirname(path)}/')
            bad.append(name)

    head('시스템 폰트')
    for name, path, url, lic in SYS_FONTS:
        if os.path.isfile(path):
            print(f'{OK} {name}')
        else:
            print(f'{NG} {name}   →  {url}')
            if lic:
                print(f'      {lic}')
            bad.append(name)

    head('PingFang TC (번체 날짜 줄)')
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import textkit
        print(f'{OK} {textkit.apple("PingFang.ttc")}')
    except Exception:
        print(f'{NG} PingFang.ttc 없음 — 시스템 설정 > 일반 > 언어 및 지역에서'
              ' 중국어(번체)를 한 번 추가하면 macOS 가 내려받는다')
        bad.append('PingFang')

    print()
    if bad:
        print(f'▶ {len(bad)}개가 빠졌다. 위 안내대로 채우고 다시 돌려라.')
        sys.exit(1)
    print('▶ 전부 준비됐다.')


if __name__ == '__main__':
    main()
